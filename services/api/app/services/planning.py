"""Deterministic overview metrics and assignment planning."""
import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.models import (
    AIActionProposal,
    Event,
    EventTask,
    Participant,
    Vehicle,
)
from app.services.participants import logistics_maps
from app.services.validation import RIDE, STAY, Kind, active_assignments

ACTIVE_PEOPLE = ("pending", "confirmed")


@dataclass
class Plan:
    assignments: list[dict] = field(default_factory=list)  # participant_id, resource_id, participant_name, resource_label
    unresolved: list[dict] = field(default_factory=list)  # participant_id, name, reason


def _people(db: Session, event_id: uuid.UUID) -> list[Participant]:
    return list(db.scalars(select(Participant).where(Participant.event_id == event_id).order_by(Participant.name)))


def _driver_ids(db: Session, event_id: uuid.UUID) -> set:
    return set(
        db.scalars(select(Vehicle.driver_participant_id).where(Vehicle.event_id == event_id, Vehicle.status == "active"))
    )


def people_needing(db: Session, kind: Kind, event_id: uuid.UUID) -> list[Participant]:
    rides, stays, _ = logistics_maps(db, event_id)
    held, attr = (rides, "transportation_required") if kind is RIDE else (stays, "accommodation_required")
    drivers = _driver_ids(db, event_id) if kind is RIDE else set()
    return [
        p for p in _people(db, event_id)
        if getattr(p, attr) and p.registration_status in ACTIVE_PEOPLE and p.id not in held and p.id not in drivers
    ]


def resource_label(kind: Kind, resource: object, names: dict) -> str:
    if kind is RIDE:
        driver = names.get(resource.driver_participant_id, "Unassigned driver")
        return f"{driver} from {resource.departure_location or 'unspecified location'}"
    # Proposal payloads are visible to view-only members, so no private address here.
    return resource.host_name


def build_plan(db: Session, kind: Kind, event_id: uuid.UUID, release_resource_id: uuid.UUID | None = None) -> Plan:
    """Greedy, repeatable plan. Prefers a matching pickup area, then the most remaining room."""
    people = {p.id: p for p in _people(db, event_id)}
    names = {pid: p.name for pid, p in people.items()}
    resources = list(db.scalars(select(kind.resource_model).where(kind.resource_model.event_id == event_id)))
    active = active_assignments(db, kind, event_id)
    moved = [a.participant_id for a in active if getattr(a, kind.resource_fk) == release_resource_id]

    load: dict[uuid.UUID, int] = {}
    for a in active:
        if a.participant_id not in moved:
            rid = getattr(a, kind.resource_fk)
            load[rid] = load.get(rid, 0) + 1

    # Affected people come first, then confirmed people, then pending.
    queue = [people[pid] for pid in moved if people[pid].registration_status in ACTIVE_PEOPLE]
    queue += sorted(
        people_needing(db, kind, event_id), key=lambda p: (p.registration_status != "confirmed", p.name)
    )
    open_resources = [r for r in resources if r.status == "active" and r.id != release_resource_id]

    plan = Plan()
    for person in queue:
        candidates = [
            r for r in open_resources
            if load.get(r.id, 0) < getattr(r, kind.capacity_attr)
            and not (set(person.tags or []) & set(r.excluded_tags or []))
        ]
        if not candidates:
            reason = "No compatible seat is available." if kind is RIDE else "No compatible bed is available."
            plan.unresolved.append({"participant_id": str(person.id), "name": person.name, "reason": reason})
            continue

        def score(r: object, person: Participant = person) -> tuple[int, int]:
            match = 0
            if kind is RIDE and person.pickup_location:
                match = int(person.pickup_location.lower() in (r.departure_location or "").lower())
            return (match, getattr(r, kind.capacity_attr) - load.get(r.id, 0))

        chosen = max(candidates, key=score)
        load[chosen.id] = load.get(chosen.id, 0) + 1
        plan.assignments.append(
            {
                "participant_id": str(person.id),
                "resource_id": str(chosen.id),
                "participant_name": person.name,
                "resource_label": resource_label(kind, chosen, names),
            }
        )
    return plan


def overview(db: Session, event: Event) -> dict:
    people = _people(db, event.id)
    count = lambda status: sum(1 for p in people if p.registration_status == status)
    live = [p for p in people if p.registration_status in ACTIVE_PEOPLE]
    rides, stays, _ = logistics_maps(db, event.id)
    drivers = _driver_ids(db, event.id)
    ride_requests = [p for p in live if p.transportation_required and p.id not in drivers]
    stay_requests = [p for p in live if p.accommodation_required]
    no_ride = [p for p in ride_requests if p.id not in rides]
    no_stay = [p for p in stay_requests if p.id not in stays]
    missing = [p for p in no_ride if not p.pickup_location]
    open_tasks = db.scalar(
        select(func.count()).select_from(EventTask).where(EventTask.event_id == event.id, EventTask.status != "completed")
    ) or 0
    pending_proposals = db.scalar(
        select(func.count()).select_from(AIActionProposal).where(
            AIActionProposal.event_id == event.id, AIActionProposal.approval_status == "pending"
        )
    ) or 0
    cancelled_drivers = db.scalar(
        select(func.count()).select_from(Vehicle).where(Vehicle.event_id == event.id, Vehicle.status == "driver_cancelled")
    ) or 0
    available = None if event.capacity is None else max(event.capacity - len(live), 0)

    metrics = {
        "total_participants": len(people) - count("cancelled"),
        "confirmed": count("confirmed"),
        "pending": count("pending"),
        "waitlisted": count("waitlisted"),
        "available_capacity": available,
        "requesting_rides": len(ride_requests),
        "without_rides": len(no_ride),
        "requesting_accommodation": len(stay_requests),
        "without_accommodation": len(no_stay),
        "open_tasks": open_tasks,
        "pending_proposals": pending_proposals,
    }

    base = f"/app/events/{event.id}"
    alerts: list[dict] = []

    def add(condition: object, severity: str, code: str, title: str, link: str) -> None:
        if condition:
            alerts.append({"severity": severity, "code": code, "title": title, "link": f"{base}/{link}"})

    def plural(n: int, one: str, many: str) -> str:
        return f"{n} {one if n == 1 else many}"

    add(cancelled_drivers, "critical", "driver_cancelled",
        f"{plural(cancelled_drivers, 'driver', 'drivers')} cancelled", "transportation")
    if event.transportation_enabled:
        add(no_ride, "warning", "needs_rides", f"{plural(len(no_ride), 'participant', 'participants')} still need rides",
            "transportation")
    if event.accommodation_enabled:
        add(no_stay, "warning", "needs_stay", f"{plural(len(no_stay), 'participant', 'participants')} need accommodation",
            "accommodations")
    add(available is not None and event.capacity and 0 < available <= max(2, event.capacity // 10), "info",
        "capacity_near", "Registration capacity nearly reached", "participants")
    add(missing, "info", "missing_info", f"{plural(len(missing), 'participant is', 'participants are')} missing a pickup location",
        "participants")
    add(pending_proposals, "warning", "proposals",
        f"{plural(pending_proposals, 'AI proposal is', 'AI proposals are')} awaiting approval", "assistant")
    return {"metrics": metrics, "alerts": alerts}


__all__ = ["RIDE", "STAY", "Plan", "build_plan", "overview", "people_needing", "resource_label"]
