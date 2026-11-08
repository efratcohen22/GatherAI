"""Deterministic assignment rules. Every manual, AI and approval path goes through here."""
import hashlib
import json
import uuid
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import (
    Accommodation,
    AccommodationAssignment,
    Participant,
    RideAssignment,
    Vehicle,
)

ELIGIBLE_STATUSES = ("pending", "confirmed")


@dataclass
class Issue:
    code: str
    message: str
    participant_id: str | None = None
    resource_id: str | None = None

    def dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Kind:
    label: str
    resource_model: type
    assignment_model: type
    resource_fk: str
    capacity_attr: str


RIDE = Kind("vehicle", Vehicle, RideAssignment, "vehicle_id", "available_passenger_seats")
STAY = Kind("accommodation", Accommodation, AccommodationAssignment, "accommodation_id", "capacity")


def active_assignments(db: Session, kind: Kind, event_id: uuid.UUID) -> list:
    model = kind.assignment_model
    return list(
        db.scalars(
            select(model)
            .join(kind.resource_model, getattr(model, kind.resource_fk) == kind.resource_model.id)
            .where(kind.resource_model.event_id == event_id, model.status != "removed")
        )
    )


def validate_plan(
    db: Session,
    kind: Kind,
    event_id: uuid.UUID,
    assignments: list[tuple[uuid.UUID, uuid.UUID]],
    release_resource_id: uuid.UUID | None = None,
    lock: bool = False,
) -> list[Issue]:
    """Validate (participant_id, resource_id) pairs against current state.

    `release_resource_id` names a resource whose active assignments the plan will clear.
    `lock` takes row locks on PostgreSQL so capacity cannot change before commit.
    """
    query = select(kind.resource_model).where(kind.resource_model.event_id == event_id)
    if lock:
        query = query.with_for_update()
    resources = {r.id: r for r in db.scalars(query)}
    participants = {p.id: p for p in db.scalars(select(Participant).where(Participant.event_id == event_id))}
    active = active_assignments(db, kind, event_id)
    released = {a.participant_id for a in active if getattr(a, kind.resource_fk) == release_resource_id}
    occupied = {pid: getattr(a, kind.resource_fk) for a in active for pid in [a.participant_id] if pid not in released}
    load: dict[uuid.UUID, int] = {}
    for resource_id in occupied.values():
        load[resource_id] = load.get(resource_id, 0) + 1
    drivers = {v.driver_participant_id for v in resources.values() if kind is RIDE and v.status == "active"}

    issues: list[Issue] = []
    seen: set[uuid.UUID] = set()
    if release_resource_id is not None and release_resource_id not in resources:
        issues.append(Issue("unknown_resource", f"The {kind.label} to release is not part of this event."))

    for participant_id, resource_id in assignments:
        pid, rid = str(participant_id), str(resource_id)
        person = participants.get(participant_id)
        resource = resources.get(resource_id)
        if person is None:
            issues.append(Issue("unknown_participant", "Participant is not part of this event.", pid, rid))
            continue
        if resource is None:
            issues.append(Issue("unknown_resource", f"This {kind.label} is not part of this event.", pid, rid))
            continue
        if participant_id in seen:
            issues.append(Issue("duplicate_in_plan", f"{person.name} appears twice in this plan.", pid, rid))
            continue
        seen.add(participant_id)
        if person.registration_status not in ELIGIBLE_STATUSES:
            issues.append(Issue("ineligible", f"{person.name} is {person.registration_status}.", pid, rid))
            continue
        if resource.status != "active" or resource_id == release_resource_id:
            issues.append(Issue("resource_unavailable", f"This {kind.label} is not available.", pid, rid))
            continue
        if participant_id in occupied:
            issues.append(Issue("already_assigned", f"{person.name} already has an active assignment.", pid, rid))
            continue
        if kind is RIDE and participant_id in drivers:
            issues.append(Issue("is_driver", f"{person.name} is driving a vehicle.", pid, rid))
            continue
        blocked = set(person.tags or []) & set(resource.excluded_tags or [])
        if blocked:
            issues.append(
                Issue("incompatible", f"{person.name} conflicts with a restriction: {', '.join(sorted(blocked))}.", pid, rid)
            )
            continue
        load[resource_id] = load.get(resource_id, 0) + 1
        if load[resource_id] > getattr(resource, kind.capacity_attr):
            load[resource_id] -= 1
            issues.append(Issue("over_capacity", f"No capacity left for {person.name}.", pid, rid))
    return issues


def state_fingerprint(db: Session, kind: Kind, event_id: uuid.UUID) -> str:
    """Hash of everything a plan depends on. Any change makes a pending proposal stale."""
    resources = db.scalars(select(kind.resource_model).where(kind.resource_model.event_id == event_id))
    participants = db.execute(
        select(Participant.id, Participant.registration_status).where(Participant.event_id == event_id)
    )
    state = {
        "resources": sorted(
            [str(r.id), r.status, getattr(r, kind.capacity_attr), sorted(r.excluded_tags or [])] for r in resources
        ),
        "assignments": sorted(
            [str(a.participant_id), str(getattr(a, kind.resource_fk)), a.status]
            for a in active_assignments(db, kind, event_id)
        ),
        "participants": sorted([str(pid), status] for pid, status in participants),
    }
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
