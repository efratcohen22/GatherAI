import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.access import EventAccess, require_event
from app.db.session import get_db
from app.models.models import Accommodation, Participant, Vehicle
from app.schemas.schemas import (
    AccommodationCreate,
    AccommodationOut,
    AccommodationsOut,
    AccommodationUpdate,
    AssignIn,
    ConfirmIn,
    PersonRef,
    StayAssignIn,
    TransportationOut,
    VehicleCreate,
    VehicleOut,
    VehicleUpdate,
    WaitingPerson,
)
from app.services.common import audit
from app.services.planning import people_needing
from app.services.validation import RIDE, STAY, Kind, active_assignments, validate_plan

router = APIRouter(prefix="/api/events/{event_id}", tags=["logistics"])
Db = Annotated[Session, Depends(get_db)]
Viewer = Annotated[EventAccess, Depends(require_event())]
Manager = Annotated[EventAccess, Depends(require_event("manage_logistics"))]


def _names(db: Session, event_id: uuid.UUID) -> dict:
    return dict(db.execute(select(Participant.id, Participant.name).where(Participant.event_id == event_id)).all())


def _occupants(db: Session, kind: Kind, event_id: uuid.UUID, names: dict) -> dict[uuid.UUID, list[PersonRef]]:
    grouped: dict[uuid.UUID, list[PersonRef]] = {}
    for a in active_assignments(db, kind, event_id):
        grouped.setdefault(getattr(a, kind.resource_fk), []).append(
            PersonRef(assignment_id=a.id, participant_id=a.participant_id, name=names.get(a.participant_id, ""), status=a.status)
        )
    return grouped


def _resource(db: Session, kind: Kind, event_id: uuid.UUID, resource_id: uuid.UUID):
    row = db.scalar(select(kind.resource_model).where(kind.resource_model.id == resource_id, kind.resource_model.event_id == event_id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{kind.label.capitalize()} not found")
    return row


def _assignment(db: Session, kind: Kind, event_id: uuid.UUID, assignment_id: uuid.UUID):
    match = next((a for a in active_assignments(db, kind, event_id) if a.id == assignment_id), None)
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")
    return match


def _assign(db: Session, kind: Kind, access: EventAccess, participant_id: uuid.UUID, resource_id: uuid.UUID) -> dict:
    issues = validate_plan(db, kind, access.event.id, [(participant_id, resource_id)], lock=True)
    if issues:
        raise HTTPException(status.HTTP_409_CONFLICT, issues[0].message)
    row = kind.assignment_model(participant_id=participant_id, **{kind.resource_fk: resource_id})
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This person already has an active assignment") from exc
    audit(db, access.event, access.user.id, f"{kind.label}.assigned", kind.label, resource_id, {"participant": str(participant_id)})
    db.commit()
    return {"id": str(row.id), "status": row.status}


def _remove(db: Session, kind: Kind, access: EventAccess, assignment_id: uuid.UUID) -> None:
    row = _assignment(db, kind, access.event.id, assignment_id)
    row.status = "removed"
    audit(db, access.event, access.user.id, f"{kind.label}.unassigned", kind.label, assignment_id)
    db.commit()


def _confirm(db: Session, kind: Kind, access: EventAccess, assignment_id: uuid.UUID, body: ConfirmIn) -> dict:
    row = _assignment(db, kind, access.event.id, assignment_id)
    row.status = "confirmed"
    row.confirmation_source = body.confirmation_source
    audit(db, access.event, access.user.id, f"{kind.label}.confirmed", kind.label, assignment_id)
    db.commit()
    return {"id": str(row.id), "status": row.status}


@router.get("/transportation", response_model=TransportationOut)
def transportation(access: Viewer, db: Db) -> TransportationOut:
    event_id = access.event.id
    names = _names(db, event_id)
    occupants = _occupants(db, RIDE, event_id, names)
    vehicles = []
    for v in db.scalars(select(Vehicle).where(Vehicle.event_id == event_id, Vehicle.status != "retired")):
        out = VehicleOut.model_validate(v)
        out.driver_name = names.get(v.driver_participant_id)
        out.passengers = occupants.get(v.id, [])
        out.seats_remaining = max(v.available_passenger_seats - len(out.passengers), 0) if v.status == "active" else 0
        vehicles.append(out)
    waiting = people_needing(db, RIDE, event_id)
    open_seats = sum(v.seats_remaining for v in vehicles)
    return TransportationOut(
        vehicles=vehicles,
        unassigned=[
            WaitingPerson(participant_id=p.id, name=p.name, registration_status=p.registration_status, detail=p.pickup_location)
            for p in waiting
        ],
        total_open_seats=open_seats, shortage=max(len(waiting) - open_seats, 0),
    )


@router.post("/vehicles", response_model=VehicleOut, status_code=201)
def create_vehicle(body: VehicleCreate, access: Manager, db: Db) -> VehicleOut:
    event_id = access.event.id
    if body.driver_participant_id and body.driver_participant_id not in _names(db, event_id):
        raise HTTPException(422, "Driver must be a participant in this event")
    vehicle = Vehicle(event_id=event_id, **body.model_dump())
    db.add(vehicle)
    db.flush()
    audit(db, access.event, access.user.id, "vehicle.created", "vehicle", vehicle.id)
    db.commit()
    out = VehicleOut.model_validate(vehicle)
    out.driver_name = _names(db, event_id).get(vehicle.driver_participant_id)
    out.seats_remaining = vehicle.available_passenger_seats
    return out


@router.patch("/vehicles/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(vehicle_id: uuid.UUID, body: VehicleUpdate, access: Manager, db: Db) -> VehicleOut:
    vehicle = _resource(db, RIDE, access.event.id, vehicle_id)
    changes = body.model_dump(exclude_unset=True)
    occupied = len(_occupants(db, RIDE, access.event.id, {}).get(vehicle_id, []))
    if "available_passenger_seats" in changes and changes["available_passenger_seats"] < occupied:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{occupied} passengers are assigned to this vehicle")
    for key, value in changes.items():
        setattr(vehicle, key, value)
    audit(db, access.event, access.user.id, "vehicle.updated", "vehicle", vehicle_id, {"fields": sorted(changes)})
    db.commit()
    out = VehicleOut.model_validate(vehicle)
    out.seats_remaining = max(vehicle.available_passenger_seats - occupied, 0)
    return out


@router.post("/ride-assignments", status_code=201)
def assign_ride(body: AssignIn, access: Manager, db: Db) -> dict:
    return _assign(db, RIDE, access, body.participant_id, body.vehicle_id)


@router.post("/ride-assignments/{assignment_id}/confirm")
def confirm_ride(assignment_id: uuid.UUID, body: ConfirmIn, access: Manager, db: Db) -> dict:
    return _confirm(db, RIDE, access, assignment_id, body)


@router.delete("/ride-assignments/{assignment_id}", status_code=204)
def remove_ride(assignment_id: uuid.UUID, access: Manager, db: Db) -> None:
    _remove(db, RIDE, access, assignment_id)


def _accommodation_out(a: Accommodation, guests: list[PersonRef], access: EventAccess) -> AccommodationOut:
    out = AccommodationOut.model_validate(a)
    out.guests = guests
    out.beds_remaining = max(a.capacity - len(guests), 0) if a.status == "active" else 0
    if not access.can("manage_logistics"):
        out.host_contact = None
    return out


@router.get("/accommodations", response_model=AccommodationsOut)
def accommodations(access: Viewer, db: Db) -> AccommodationsOut:
    event_id = access.event.id
    guests = _occupants(db, STAY, event_id, _names(db, event_id))
    rows = [
        _accommodation_out(a, guests.get(a.id, []), access)
        for a in db.scalars(select(Accommodation).where(Accommodation.event_id == event_id, Accommodation.status != "retired"))
    ]
    waiting = people_needing(db, STAY, event_id)
    open_beds = sum(a.beds_remaining for a in rows)
    return AccommodationsOut(
        accommodations=rows,
        unassigned=[WaitingPerson(participant_id=p.id, name=p.name, registration_status=p.registration_status) for p in waiting],
        total_open_beds=open_beds, shortage=max(len(waiting) - open_beds, 0),
    )


@router.post("/accommodations", response_model=AccommodationOut, status_code=201)
def create_accommodation(body: AccommodationCreate, access: Manager, db: Db) -> AccommodationOut:
    row = Accommodation(event_id=access.event.id, **body.model_dump())
    db.add(row)
    db.flush()
    audit(db, access.event, access.user.id, "accommodation.created", "accommodation", row.id)
    db.commit()
    return _accommodation_out(row, [], access)


@router.patch("/accommodations/{accommodation_id}", response_model=AccommodationOut)
def update_accommodation(accommodation_id: uuid.UUID, body: AccommodationUpdate, access: Manager, db: Db) -> AccommodationOut:
    row = _resource(db, STAY, access.event.id, accommodation_id)
    changes = body.model_dump(exclude_unset=True)
    guests = _occupants(db, STAY, access.event.id, _names(db, access.event.id)).get(accommodation_id, [])
    if "capacity" in changes and changes["capacity"] < len(guests):
        raise HTTPException(status.HTTP_409_CONFLICT, f"{len(guests)} guests are assigned to this host")
    for key, value in changes.items():
        setattr(row, key, value)
    audit(db, access.event, access.user.id, "accommodation.updated", "accommodation", accommodation_id, {"fields": sorted(changes)})
    db.commit()
    return _accommodation_out(row, guests, access)


@router.post("/accommodation-assignments", status_code=201)
def assign_stay(body: StayAssignIn, access: Manager, db: Db) -> dict:
    return _assign(db, STAY, access, body.participant_id, body.accommodation_id)


@router.post("/accommodation-assignments/{assignment_id}/confirm")
def confirm_stay(assignment_id: uuid.UUID, body: ConfirmIn, access: Manager, db: Db) -> dict:
    return _confirm(db, STAY, access, assignment_id, body)


@router.delete("/accommodation-assignments/{assignment_id}", status_code=204)
def remove_stay(assignment_id: uuid.UUID, access: Manager, db: Db) -> None:
    _remove(db, STAY, access, assignment_id)
