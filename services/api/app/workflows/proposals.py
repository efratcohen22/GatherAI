"""Human approval workflow. This is the only code path that applies AI-originated changes."""
import logging
import uuid
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth.access import EventAccess
from app.core.config import get_settings
from app.models.models import (
    AIActionProposal,
    Event,
    EventMessage,
    EventTask,
    Participant,
    Vehicle,
    utcnow,
)
from app.services.common import audit, track
from app.services.validation import RIDE, STAY, Kind, active_assignments, state_fingerprint, validate_plan

log = logging.getLogger(__name__)
KINDS: dict[str, Kind] = {"ride_assignments": RIDE, "accommodation_assignments": STAY}


class ProposalRejected(Exception):
    """Plan no longer applies. Nothing was written."""


def _pairs(payload: dict) -> list[tuple[uuid.UUID, uuid.UUID]]:
    return [(uuid.UUID(a["participant_id"]), uuid.UUID(a["resource_id"])) for a in payload["assignments"]]


def _release(payload: dict) -> uuid.UUID | None:
    value = payload.get("release_resource_id")
    return uuid.UUID(value) if value else None


def create_proposal(
    db: Session, event: Event, proposal_type: str, payload: dict, summary: str, rationale: str, actor_id: uuid.UUID | None
) -> AIActionProposal:
    kind = KINDS.get(proposal_type)
    proposal = AIActionProposal(
        event_id=event.id, proposal_type=proposal_type, proposed_payload=payload, summary=summary, rationale=rationale,
        state_fingerprint=state_fingerprint(db, kind, event.id) if kind else "",
        expires_at=utcnow() + timedelta(hours=get_settings().proposal_ttl_hours), created_by=actor_id,
    )
    db.add(proposal)
    db.flush()
    audit(db, event, actor_id, "proposal.created", "ai_action_proposal", proposal.id, {"type": proposal_type})
    track(db, "ai_proposal_created", event.id)
    return proposal


def _apply_assignments(db: Session, event: Event, proposal: AIActionProposal, kind: Kind) -> None:
    payload = proposal.proposed_payload
    if proposal.state_fingerprint != state_fingerprint(db, kind, event.id):
        raise ProposalRejected("Event data changed after this proposal was created. Ask for a new proposal.")
    pairs, release = _pairs(payload), _release(payload)
    issues = validate_plan(db, kind, event.id, pairs, release, lock=True)
    if issues:
        raise ProposalRejected("; ".join(i.message for i in issues))

    moved: list[uuid.UUID] = []
    if release:
        for assignment in active_assignments(db, kind, event.id):
            if getattr(assignment, kind.resource_fk) == release:
                assignment.status = "removed"
                moved.append(assignment.participant_id)
        db.flush()
        resource = db.get(kind.resource_model, release)
        resource.status = "retired"

    for participant_id, resource_id in pairs:
        db.add(kind.assignment_model(participant_id=participant_id, status="assigned", **{kind.resource_fk: resource_id}))
    db.flush()

    # Notifications are drafts only; a person must send them.
    placed = {pid: rid for pid, rid in pairs}
    labels = {a["participant_id"]: a.get("resource_label", "") for a in payload["assignments"]}
    unresolved = {uuid.UUID(u["participant_id"]) for u in payload.get("unresolved", [])}
    noun = "ride" if kind is RIDE else "accommodation"
    for participant_id in set(moved) | set(placed) | unresolved:
        if participant_id in placed:
            text = (
                f"Your {noun} for {event.name} has been updated: {labels.get(str(participant_id), 'see details')}. "
                "Please reply to confirm this works for you."
            )
        else:
            text = f"We are still working on your {noun} for {event.name} and will update you as soon as we can."
        db.add(EventMessage(event_id=event.id, participant_id=participant_id, content=text, status="draft"))


def _apply_tasks(db: Session, event: Event, proposal: AIActionProposal) -> None:
    for task in proposal.proposed_payload["tasks"]:
        db.add(
            EventTask(
                event_id=event.id, title=task["title"], description=task.get("description", ""),
                priority=task.get("priority", "medium"),
            )
        )


def _execute(db: Session, event: Event, proposal: AIActionProposal) -> None:
    kind = KINDS.get(proposal.proposal_type)
    if kind:
        _apply_assignments(db, event, proposal, kind)
    elif proposal.proposal_type == "task_creation":
        _apply_tasks(db, event, proposal)
    else:
        raise ProposalRejected(f"Unsupported proposal type: {proposal.proposal_type}")


def _get(db: Session, event_id: uuid.UUID, proposal_id: uuid.UUID) -> AIActionProposal:
    proposal = db.scalar(
        select(AIActionProposal).where(AIActionProposal.id == proposal_id, AIActionProposal.event_id == event_id)
    )
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
    return proposal


def _claim(db: Session, access: EventAccess, proposal_id: uuid.UUID, new_status: str) -> bool:
    """Atomically move pending to new_status. Exactly one concurrent caller can win."""
    result = db.execute(
        update(AIActionProposal)
        .where(
            AIActionProposal.id == proposal_id,
            AIActionProposal.event_id == access.event.id,
            AIActionProposal.approval_status == "pending",
        )
        .values(approval_status=new_status, approved_by=access.user.id)
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return result.rowcount == 1


def approve(db: Session, access: EventAccess, proposal_id: uuid.UUID) -> AIActionProposal:
    event = access.event
    proposal = _get(db, event.id, proposal_id)
    if proposal.approval_status == "pending" and proposal.expires_at <= utcnow():
        if _claim(db, access, proposal_id, "expired"):
            audit(db, event, access.user.id, "proposal.expired", "ai_action_proposal", proposal_id)
            db.commit()
        db.refresh(proposal)
        return proposal
    if not _claim(db, access, proposal_id, "approved"):
        raise HTTPException(status.HTTP_409_CONFLICT, "This proposal has already been handled")
    db.refresh(proposal)

    try:
        _execute(db, event, proposal)
        proposal.approval_status = "executed"
        audit(db, event, access.user.id, "proposal.executed", "ai_action_proposal", proposal_id,
              {"type": proposal.proposal_type})
        track(db, "ai_proposal_approved", event.id)
        db.commit()
    except ProposalRejected as exc:
        db.rollback()
        _fail(db, event, access, proposal, str(exc))
    except Exception:
        db.rollback()
        log.exception("Proposal execution failed: %s", proposal_id)
        _fail(db, event, access, proposal, "The change could not be applied. Nothing was modified.")
    db.refresh(proposal)
    return proposal


def _fail(db: Session, event: Event, access: EventAccess, proposal: AIActionProposal, reason: str) -> None:
    proposal = db.get(AIActionProposal, proposal.id)
    proposal.approval_status = "failed"
    proposal.failure_reason = reason
    audit(db, event, access.user.id, "proposal.failed", "ai_action_proposal", proposal.id)
    db.commit()


def reject(db: Session, access: EventAccess, proposal_id: uuid.UUID) -> AIActionProposal:
    proposal = _get(db, access.event.id, proposal_id)
    if not _claim(db, access, proposal_id, "rejected"):
        raise HTTPException(status.HTTP_409_CONFLICT, "This proposal has already been handled")
    audit(db, access.event, access.user.id, "proposal.rejected", "ai_action_proposal", proposal_id)
    track(db, "ai_proposal_rejected", access.event.id)
    db.commit()
    db.refresh(proposal)
    return proposal


__all__ = ["Participant", "Vehicle", "approve", "create_proposal", "reject"]
