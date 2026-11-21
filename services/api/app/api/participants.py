import csv
import io
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.access import EventAccess, require_event
from app.db.session import get_db
from app.models.models import Event, Participant, RegistrationRequest
from app.schemas.schemas import (
    ParticipantCreate,
    ParticipantOut,
    ParticipantPage,
    ParticipantUpdate,
    RegStatus,
    RequestOut,
)
from app.services.common import audit
from app.services.participants import cancel_participant, confirmed_count, initial_status, logistics_maps, to_out

router = APIRouter(prefix="/api/events/{event_id}/participants", tags=["participants"])
Db = Annotated[Session, Depends(get_db)]
Viewer = Annotated[EventAccess, Depends(require_event())]
Manager = Annotated[EventAccess, Depends(require_event("manage_participants"))]


def _get(db: Session, event_id: uuid.UUID, participant_id: uuid.UUID) -> Participant:
    person = db.scalar(select(Participant).where(Participant.id == participant_id, Participant.event_id == event_id))
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Participant not found")
    return person


def _present(out: ParticipantOut, access: EventAccess) -> ParticipantOut:
    if not access.can("manage_participants"):
        out.email = out.phone = None
    return out


def _check_capacity(db: Session, event: Event) -> None:
    if event.capacity is not None and confirmed_count(db, event.id) >= event.capacity:
        raise HTTPException(status.HTTP_409_CONFLICT, "The event is at capacity")


def _filtered(event_id: uuid.UUID, search: str | None, reg_status: str | None, include_email: bool = False):
    query = select(Participant).where(Participant.event_id == event_id)
    if reg_status:
        query = query.where(Participant.registration_status == reg_status)
    if search:
        pattern = f"%{search.lower()}%"
        name_match = func.lower(Participant.name).like(pattern)
        # Matching on a masked field would leak it one character at a time.
        query = query.where(or_(name_match, func.lower(Participant.email).like(pattern)) if include_email else name_match)
    return query


@router.get("", response_model=ParticipantPage)
def list_participants(
    access: Viewer, db: Db, search: str | None = Query(default=None, max_length=100),
    status_filter: RegStatus | None = Query(default=None, alias="status"),
    needs: str | None = Query(default=None, pattern="^(ride|stay)$"),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=200),
) -> ParticipantPage:
    query = _filtered(access.event.id, search, status_filter, access.can("manage_participants"))
    rides, stays, requests = logistics_maps(db, access.event.id)
    if needs == "ride":
        query = query.where(Participant.transportation_required.is_(True), Participant.id.not_in(rides or [uuid.uuid4()]))
    elif needs == "stay":
        query = query.where(Participant.accommodation_required.is_(True), Participant.id.not_in(stays or [uuid.uuid4()]))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(Participant.name).offset((page - 1) * page_size).limit(page_size))
    return ParticipantPage(
        items=[_present(to_out(p, rides, stays, requests), access) for p in rows], total=total, page=page, page_size=page_size
    )


def _csv_safe(value: object) -> str:
    """Neutralize spreadsheet formula injection in participant-supplied text."""
    text = "" if value is None else str(value)
    return f"'{text}" if text.lstrip()[:1] in ("=", "+", "-", "@", "|", "%") or text[:1] in ("\t", "\r") else text


@router.get("/export.csv")
def export_csv(access: Manager, db: Db) -> StreamingResponse:
    rides, stays, _ = logistics_maps(db, access.event.id)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Name", "Email", "Phone", "Registration", "Ride", "Accommodation", "Pickup", "Dietary"])
    rows = db.scalars(select(Participant).where(Participant.event_id == access.event.id).order_by(Participant.name))
    for p in rows:
        out = to_out(p, rides, stays, {})
        writer.writerow([_csv_safe(v) for v in (
            p.name, p.email, p.phone, p.registration_status, out.ride_status, out.stay_status, p.pickup_location, p.dietary_preferences,
        )])
    audit(db, access.event, access.user.id, "participants.exported", "event", access.event.id)
    db.commit()
    return StreamingResponse(
        iter([buffer.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="participants.csv"'},
    )


@router.post("", response_model=ParticipantOut, status_code=201)
def create_participant(body: ParticipantCreate, access: Manager, db: Db) -> ParticipantOut:
    data = body.model_dump()
    requested = data.pop("registration_status")
    if data["email"]:
        data["email"] = data["email"].lower()
    if requested == "confirmed":
        _check_capacity(db, access.event)
    person = Participant(event_id=access.event.id, registration_status=requested or initial_status(db, access.event), **data)
    db.add(person)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This email is already registered for this event") from exc
    audit(db, access.event, access.user.id, "participant.created", "participant", person.id)
    db.commit()
    return to_out(person, {}, {}, {})


@router.get("/{participant_id}", response_model=ParticipantOut)
def get_participant(participant_id: uuid.UUID, access: Viewer, db: Db) -> ParticipantOut:
    person = _get(db, access.event.id, participant_id)
    return _present(to_out(person, *logistics_maps(db, access.event.id)), access)


@router.get("/{participant_id}/requests", response_model=list[RequestOut])
def participant_requests(participant_id: uuid.UUID, access: Viewer, db: Db) -> list:
    _get(db, access.event.id, participant_id)
    return list(db.scalars(select(RegistrationRequest).where(RegistrationRequest.participant_id == participant_id)))


@router.post("/{participant_id}/requests/{request_id}/resolve", response_model=RequestOut)
def resolve_request(participant_id: uuid.UUID, request_id: uuid.UUID, access: Manager, db: Db) -> RegistrationRequest:
    _get(db, access.event.id, participant_id)
    item = db.scalar(
        select(RegistrationRequest).where(
            RegistrationRequest.id == request_id, RegistrationRequest.participant_id == participant_id
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    item.status = "resolved"
    audit(db, access.event, access.user.id, "request.resolved", "registration_request", item.id)
    db.commit()
    return item


@router.patch("/{participant_id}", response_model=ParticipantOut)
def update_participant(participant_id: uuid.UUID, body: ParticipantUpdate, access: Manager, db: Db) -> ParticipantOut:
    person = _get(db, access.event.id, participant_id)
    changes = body.model_dump(exclude_unset=True)
    new_status = changes.pop("registration_status", None)
    if changes.get("email"):
        changes["email"] = changes["email"].lower()
    for key, value in changes.items():
        setattr(person, key, value)
    if new_status and new_status != person.registration_status:
        if new_status == "cancelled":
            cancel_participant(db, access.event, person, access.user.id)
        else:
            if new_status == "confirmed":
                _check_capacity(db, access.event)
            person.registration_status = new_status
            audit(db, access.event, access.user.id, "participant.status_changed", "participant", person.id, {"status": new_status})
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This email is already registered for this event") from exc
    return to_out(person, *logistics_maps(db, access.event.id))


@router.delete("/{participant_id}", status_code=204)
def delete_participant(participant_id: uuid.UUID, access: Manager, db: Db) -> None:
    """Permanently erases a participant's record (data deletion requests)."""
    person = _get(db, access.event.id, participant_id)
    db.delete(person)
    audit(db, access.event, access.user.id, "participant.deleted", "participant", participant_id)
    db.commit()
