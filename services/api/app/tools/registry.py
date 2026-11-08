"""Organizer assistant tools. Each one is permission-checked and validated without the model."""
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.access import EventAccess
from app.models.models import AIActionProposal, EventMessage, EventTask, Participant
from app.services.participants import logistics_maps
from app.services.planning import build_plan, overview, people_needing, resource_label
from app.services.validation import RIDE, STAY, Kind, active_assignments, validate_plan
from app.workflows.proposals import create_proposal


@dataclass
class ToolContext:
    db: Session
    access: EventAccess
    proposals: list[AIActionProposal] = field(default_factory=list)

    @property
    def event_id(self) -> uuid.UUID:
        return self.access.event.id


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Empty(Input):
    pass


class ListParticipantsIn(Input):
    status: Literal["pending", "confirmed", "waitlisted", "cancelled"] | None = None


class ParticipantIdIn(Input):
    participant_id: uuid.UUID


class PlanIn(Input):
    release_resource_id: uuid.UUID | None = Field(default=None, description="Vehicle or host being vacated, if any")


class Pair(Input):
    participant_id: uuid.UUID
    resource_id: uuid.UUID = Field(description="Vehicle id or accommodation id")


class ValidateIn(Input):
    assignments: list[Pair] = Field(min_length=1, max_length=200)
    release_resource_id: uuid.UUID | None = None


class UnresolvedIn(Input):
    participant_id: uuid.UUID
    reason: str = Field(default="Not placed by this plan.", max_length=300)


class ProposeIn(ValidateIn):
    summary: str = Field(min_length=1, max_length=500)
    rationale: str = Field(default="", max_length=2000)
    unresolved: list[UnresolvedIn] = Field(default_factory=list, max_length=200)


class TaskDraft(Input):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=2000)
    priority: Literal["low", "medium", "high", "urgent"] = "medium"


class ProposeTasksIn(Input):
    tasks: list[TaskDraft] = Field(min_length=1, max_length=20)
    summary: str = Field(min_length=1, max_length=500)
    rationale: str = Field(default="", max_length=2000)


class DraftMessageIn(Input):
    participant_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=2000)


def _person_brief(p: Participant, rides: dict, stays: dict) -> dict:
    return {
        "id": str(p.id), "name": p.name, "registration_status": p.registration_status,
        "needs_ride": p.transportation_required, "ride_assignment": rides.get(p.id),
        "needs_accommodation": p.accommodation_required, "accommodation_assignment": stays.get(p.id),
    }


def get_event_summary(ctx: ToolContext, _: Empty) -> dict:
    e = ctx.access.event
    return {
        "name": e.name, "location": e.location, "start_at": e.start_at.isoformat(), "end_at": e.end_at.isoformat(),
        "capacity": e.capacity, "status": e.event_status, **overview(ctx.db, e),
    }


def list_participants(ctx: ToolContext, data: ListParticipantsIn) -> dict:
    query = select(Participant).where(Participant.event_id == ctx.event_id).order_by(Participant.name)
    if data.status:
        query = query.where(Participant.registration_status == data.status)
    rides, stays, _ = logistics_maps(ctx.db, ctx.event_id)
    return {"participants": [_person_brief(p, rides, stays) for p in ctx.db.scalars(query)]}


def get_participant(ctx: ToolContext, data: ParticipantIdIn) -> dict:
    p = ctx.db.scalar(select(Participant).where(Participant.id == data.participant_id, Participant.event_id == ctx.event_id))
    if p is None:
        return {"error": "Participant not found in this event"}
    rides, stays, _ = logistics_maps(ctx.db, ctx.event_id)
    return {
        **_person_brief(p, rides, stays), "pickup_location": p.pickup_location, "dietary_preferences": p.dietary_preferences,
        "tags": p.tags, "organizer_notes_untrusted": p.notes,
    }


def _waiting(ctx: ToolContext, kind: Kind) -> list[dict]:
    return [
        {"id": str(p.id), "name": p.name, "registration_status": p.registration_status, "pickup_location": p.pickup_location}
        for p in people_needing(ctx.db, kind, ctx.event_id)
    ]


def _resources(ctx: ToolContext, kind: Kind) -> list[dict]:
    db = ctx.db
    active = active_assignments(db, kind, ctx.event_id)
    names = dict(db.execute(select(Participant.id, Participant.name).where(Participant.event_id == ctx.event_id)).all())
    out = []
    for r in db.scalars(select(kind.resource_model).where(kind.resource_model.event_id == ctx.event_id)):
        occupants = [a.participant_id for a in active if getattr(a, kind.resource_fk) == r.id]
        out.append(
            {
                "id": str(r.id), "label": resource_label(kind, r, names), "status": r.status,
                "capacity": getattr(r, kind.capacity_attr),
                "remaining": max(getattr(r, kind.capacity_attr) - len(occupants), 0),
                "excluded_tags": r.excluded_tags, "occupants": [names.get(o) for o in occupants],
            }
        )
    return out


def _plan(ctx: ToolContext, kind: Kind, data: PlanIn) -> dict:
    plan = build_plan(ctx.db, kind, ctx.event_id, data.release_resource_id)
    return {"note": "Suggestion only. Nothing has been changed.", "assignments": plan.assignments, "unresolved": plan.unresolved}


def _validate(ctx: ToolContext, kind: Kind, data: ValidateIn) -> dict:
    pairs = [(a.participant_id, a.resource_id) for a in data.assignments]
    issues = validate_plan(ctx.db, kind, ctx.event_id, pairs, data.release_resource_id)
    return {"valid": not issues, "issues": [i.dict() for i in issues]}


def _propose(ctx: ToolContext, kind: Kind, proposal_type: str, data: ProposeIn) -> dict:
    db = ctx.db
    pairs = [(a.participant_id, a.resource_id) for a in data.assignments]
    issues = validate_plan(db, kind, ctx.event_id, pairs, data.release_resource_id)
    if issues:
        return {"created": False, "issues": [i.dict() for i in issues]}
    names = dict(db.execute(select(Participant.id, Participant.name).where(Participant.event_id == ctx.event_id)).all())
    resources = {r.id: r for r in db.scalars(select(kind.resource_model).where(kind.resource_model.event_id == ctx.event_id))}
    unresolved = [
        {"participant_id": str(u.participant_id), "name": names[u.participant_id], "reason": u.reason}
        for u in data.unresolved if u.participant_id in names
    ]
    return _save(ctx, proposal_type, {
        "assignments": [
            {"participant_id": str(pid), "resource_id": str(rid), "participant_name": names[pid],
             "resource_label": resource_label(kind, resources[rid], names)}
            for pid, rid in pairs
        ],
        "release_resource_id": str(data.release_resource_id) if data.release_resource_id else None,
        "unresolved": unresolved,
    }, data.summary, data.rationale)


def _save(ctx: ToolContext, proposal_type: str, payload: dict, summary: str, rationale: str) -> dict:
    user = ctx.access.user
    proposal = create_proposal(ctx.db, ctx.access.event, proposal_type, payload, summary, rationale, user.id)
    ctx.proposals.append(proposal)
    return {"created": True, "proposal_id": str(proposal.id), "status": "pending_organizer_approval"}


def list_tasks(ctx: ToolContext, _: Empty) -> dict:
    tasks = ctx.db.scalars(select(EventTask).where(EventTask.event_id == ctx.event_id, EventTask.status != "completed"))
    return {"open_tasks": [
        {"title": t.title, "status": t.status, "priority": t.priority, "due_at": t.due_at.isoformat() if t.due_at else None}
        for t in tasks
    ]}


def propose_task_creation(ctx: ToolContext, data: ProposeTasksIn) -> dict:
    return _save(ctx, "task_creation", {"tasks": [t.model_dump() for t in data.tasks]}, data.summary, data.rationale)


def draft_participant_message(ctx: ToolContext, data: DraftMessageIn) -> dict:
    valid = set(
        ctx.db.scalars(
            select(Participant.id).where(Participant.event_id == ctx.event_id, Participant.id.in_(data.participant_ids))
        )
    )
    for pid in valid:
        ctx.db.add(EventMessage(event_id=ctx.event_id, participant_id=pid, content=data.content, status="draft"))
    return {"drafted": len(valid), "skipped": len(set(data.participant_ids)) - len(valid), "status": "draft_not_sent"}


def get_pending_proposals(ctx: ToolContext, _: Empty) -> dict:
    rows = ctx.db.scalars(
        select(AIActionProposal).where(AIActionProposal.event_id == ctx.event_id, AIActionProposal.approval_status == "pending")
    )
    return {"pending": [{"id": str(p.id), "type": p.proposal_type, "summary": p.summary} for p in rows]}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: type[Input]
    handler: Callable[[ToolContext, Input], dict]
    permission: str = "use_assistant"


TOOLS = {
    t.name: t
    for t in [
        Tool("get_event_summary", "Live counts and open alerts for this event.", Empty, get_event_summary),
        Tool("list_participants", "List participants, optionally by status.", ListParticipantsIn, list_participants),
        Tool("get_participant", "Details for one participant in this event.", ParticipantIdIn, get_participant),
        Tool("list_transportation_requests", "People who still need a ride.", Empty, lambda c, _: {"waiting": _waiting(c, RIDE)}),
        Tool("list_available_vehicles", "All vehicles with status and remaining seats.", Empty, lambda c, _: {"vehicles": _resources(c, RIDE)}),
        Tool("suggest_ride_plan", "Compute a valid ride plan. Set release_resource_id to rehouse a cancelled vehicle's passengers. Changes nothing.", PlanIn, lambda c, d: _plan(c, RIDE, d)),
        Tool("validate_ride_assignment", "Check ride assignments against all rules.", ValidateIn, lambda c, d: _validate(c, RIDE, d)),
        Tool("propose_ride_assignments", "Create a ride proposal for organizer approval. Does not apply it.", ProposeIn, lambda c, d: _propose(c, RIDE, "ride_assignments", d), "manage_logistics"),
        Tool("list_accommodation_requests", "People who still need accommodation.", Empty, lambda c, _: {"waiting": _waiting(c, STAY)}),
        Tool("list_available_accommodations", "All hosts with remaining beds.", Empty, lambda c, _: {"accommodations": _resources(c, STAY)}),
        Tool("suggest_accommodation_plan", "Compute a valid accommodation plan. Changes nothing.", PlanIn, lambda c, d: _plan(c, STAY, d)),
        Tool("validate_accommodation_assignment", "Check accommodation assignments against all rules.", ValidateIn, lambda c, d: _validate(c, STAY, d)),
        Tool("propose_accommodation_assignments", "Create an accommodation proposal for organizer approval. Does not apply it.", ProposeIn, lambda c, d: _propose(c, STAY, "accommodation_assignments", d), "manage_logistics"),
        Tool("list_tasks", "Open tasks for this event.", Empty, list_tasks),
        Tool("propose_task_creation", "Propose new tasks for organizer approval.", ProposeTasksIn, propose_task_creation, "manage_tasks"),
        Tool("draft_participant_message", "Save a message as a draft. Never sends it.", DraftMessageIn, draft_participant_message, "manage_messages"),
        Tool("get_pending_proposals", "Proposals awaiting approval.", Empty, get_pending_proposals),
    ]
}


def execute_tool(ctx: ToolContext, name: str, raw_input: object) -> tuple[dict, bool]:
    """Returns (result, ok). Never raises for bad model output."""
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": f"Unknown tool: {name}"}, False
    if not ctx.access.can(tool.permission):
        return {"error": f"You do not have the {tool.permission} permission."}, False
    try:
        data = tool.input_model.model_validate(raw_input)
    except ValidationError as exc:
        return {"error": "Invalid input", "details": exc.errors(include_url=False, include_context=False, include_input=False)}, False
    result = tool.handler(ctx, data)
    return result, "error" not in result and result.get("created") is not False


def anthropic_tool_definitions(access: EventAccess) -> list[dict]:
    return [
        {"name": t.name, "description": t.description, "input_schema": t.input_model.model_json_schema()}
        for t in TOOLS.values() if access.can(t.permission)
    ]
