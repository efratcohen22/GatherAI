"""Unauthenticated participant routes. They expose only public event fields and the caller's own record."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.models import Event, Participant
from app.schemas.schemas import (
    ManagedRegistrationOut,
    ManagedRegistrationUpdate,
    PublicEventOut,
    RegisterIn,
    RegisterOut,
)
from app.services.common import audit, track
from app.services.participants import cancel_participant, hash_token, initial_status, new_manage_token, seats_taken

router = APIRouter(prefix="/api/public", tags=["public"])
Db = Annotated[Session, Depends(get_db)]


def _event(db: Session, slug: str) -> Event:
    event = db.scalar(select(Event).where(Event.slug == slug, Event.archived_at.is_(None), Event.event_status != "draft"))
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    return event


def _availability(db: Session, event: Event) -> str:
    if event.capacity is None:
        return "open"
    left = event.capacity - seats_taken(db, event.id)
    if left <= 0:
        return "full"
    return "limited" if left <= max(2, event.capacity // 10) else "open"


@router.get("/events/{slug}", response_model=PublicEventOut, dependencies=[Depends(rate_limit("public_event", 120))])
def public_event(slug: str, db: Db) -> PublicEventOut:
    e = _event(db, slug)
    return PublicEventOut(
        slug=e.slug, name=e.name, description=e.description, event_type=e.event_type, location=e.location, timezone=e.timezone,
        start_at=e.start_at, end_at=e.end_at, registration_open=e.registration_status == "open",
        availability=_availability(db, e), transportation_enabled=e.transportation_enabled,
        accommodation_enabled=e.accommodation_enabled,
    )


@router.post("/events/{slug}/register", response_model=RegisterOut, status_code=201, dependencies=[Depends(rate_limit("register", 20))])
def register(slug: str, body: RegisterIn, db: Db) -> RegisterOut:
    event = _event(db, slug)
    if body.website:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Registration could not be processed")
    if event.registration_status != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, "Registration is not open")
    token, token_hash = new_manage_token()
    person = Participant(
        event_id=event.id, name=body.name.strip(), email=body.email.lower(), phone=body.phone,
        registration_status=initial_status(db, event),
        transportation_required=body.transportation_required and event.transportation_enabled,
        pickup_location=body.pickup_location,
        accommodation_required=body.accommodation_required and event.accommodation_enabled,
        dietary_preferences=body.dietary_preferences, update_token_hash=token_hash,
    )
    db.add(person)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This email is already registered. Contact the organizer for changes.") from exc
    audit(db, event, None, "participant.registered", "participant", person.id, {"channel": "form"})
    track(db, "registration_completed", event.id)
    db.commit()
    return RegisterOut(registration_status=person.registration_status, manage_token=token)


def _by_token(db: Session, token: str) -> tuple[Participant, Event]:
    person = db.scalar(select(Participant).where(Participant.update_token_hash == hash_token(token)))
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Registration not found")
    return person, db.get(Event, person.event_id)


def _managed(person: Participant, event: Event) -> ManagedRegistrationOut:
    return ManagedRegistrationOut(
        event_name=event.name, name=person.name, registration_status=person.registration_status,
        transportation_required=person.transportation_required, pickup_location=person.pickup_location,
        accommodation_required=person.accommodation_required, dietary_preferences=person.dietary_preferences,
    )


limit = rate_limit("manage", 60)


@router.get("/registrations/{token}", response_model=ManagedRegistrationOut, dependencies=[Depends(limit)])
def get_registration(token: str, db: Db) -> ManagedRegistrationOut:
    return _managed(*_by_token(db, token))


@router.patch("/registrations/{token}", response_model=ManagedRegistrationOut, dependencies=[Depends(limit)])
def update_registration(token: str, body: ManagedRegistrationUpdate, db: Db) -> ManagedRegistrationOut:
    person, event = _by_token(db, token)
    if person.registration_status == "cancelled":
        raise HTTPException(status.HTTP_409_CONFLICT, "This registration was cancelled")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(person, key, value)
    audit(db, event, None, "participant.self_updated", "participant", person.id)
    db.commit()
    return _managed(person, event)


@router.post("/registrations/{token}/cancel", response_model=ManagedRegistrationOut, dependencies=[Depends(limit)])
def cancel_registration(token: str, db: Db) -> ManagedRegistrationOut:
    person, event = _by_token(db, token)
    if person.registration_status != "cancelled":
        cancel_participant(db, event, person, None)
        db.commit()
    return _managed(person, event)
