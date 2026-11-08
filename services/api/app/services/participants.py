import hashlib
import secrets
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.models import (
    Accommodation,
    AccommodationAssignment,
    Event,
    Participant,
    RegistrationRequest,
    RideAssignment,
    Vehicle,
)
from app.schemas.schemas import ParticipantOut
from app.services.common import audit


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_manage_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def seats_taken(db: Session, event_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count()).select_from(Participant).where(
            Participant.event_id == event_id, Participant.registration_status.in_(("pending", "confirmed"))
        )
    ) or 0


def confirmed_count(db: Session, event_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count()).select_from(Participant).where(
            Participant.event_id == event_id, Participant.registration_status == "confirmed"
        )
    ) or 0


def initial_status(db: Session, event: Event) -> str:
    if event.capacity is not None and seats_taken(db, event.id) >= event.capacity:
        return "waitlisted"
    return "pending"


def cancel_participant(db: Session, event: Event, person: Participant, actor_id: uuid.UUID | None) -> None:
    """Release a cancelled person's places. A driver's vehicle becomes driver_cancelled for review."""
    person.registration_status = "cancelled"
    for model in (RideAssignment, AccommodationAssignment):
        db.execute(
            update(model).where(model.participant_id == person.id, model.status != "removed").values(status="removed")
        )
    db.execute(
        update(Vehicle)
        .where(Vehicle.driver_participant_id == person.id, Vehicle.status == "active")
        .values(status="driver_cancelled")
    )
    db.execute(
        update(RegistrationRequest)
        .where(RegistrationRequest.participant_id == person.id, RegistrationRequest.status == "open")
        .values(status="dismissed")
    )
    audit(db, event, actor_id, "participant.cancelled", "participant", person.id)


def logistics_maps(db: Session, event_id: uuid.UUID) -> tuple[dict, dict, dict]:
    rides = dict(
        db.execute(
            select(RideAssignment.participant_id, RideAssignment.status)
            .join(Vehicle, RideAssignment.vehicle_id == Vehicle.id)
            .where(Vehicle.event_id == event_id, RideAssignment.status != "removed")
        ).all()
    )
    stays = dict(
        db.execute(
            select(AccommodationAssignment.participant_id, AccommodationAssignment.status)
            .join(Accommodation, AccommodationAssignment.accommodation_id == Accommodation.id)
            .where(Accommodation.event_id == event_id, AccommodationAssignment.status != "removed")
        ).all()
    )
    requests = dict(
        db.execute(
            select(RegistrationRequest.participant_id, func.count())
            .where(RegistrationRequest.event_id == event_id, RegistrationRequest.status == "open")
            .group_by(RegistrationRequest.participant_id)
        ).all()
    )
    return rides, stays, requests


def _logistics_status(required: bool, current: str | None) -> str:
    if current:
        return current
    return "needed" if required else "not_needed"


def to_out(person: Participant, rides: dict, stays: dict, requests: dict) -> ParticipantOut:
    out = ParticipantOut.model_validate(person)
    out.ride_status = _logistics_status(person.transportation_required, rides.get(person.id))
    out.stay_status = _logistics_status(person.accommodation_required, stays.get(person.id))
    out.open_requests = requests.get(person.id, 0)
    return out
