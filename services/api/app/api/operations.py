"""Tasks, messages, AI and simulator routes."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.agents import organizer, participant
from app.auth.access import EventAccess, require_event, resolve_access
from app.auth.service import CurrentUser
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.messaging.providers import get_provider
from app.models.models import AIActionProposal, AIConversation, AIMessage, Event, EventMessage, EventTask, Participant
from app.schemas.schemas import (
    ChatIn,
    ChatOut,
    MessageCreate,
    MessageOut,
    MessageUpdate,
    ProposalOut,
    SimConversationOut,
    SimMessage,
    SimMessageIn,
    SimStart,
    TaskCreate,
    TaskOut,
    TaskPriority,
    TaskStatus,
    TaskUpdate,
)
from app.services.common import audit
from app.workflows import proposals as workflow

router = APIRouter(prefix="/api/events/{event_id}", tags=["operations"])
simulator = APIRouter(prefix="/api/simulator", tags=["simulator"])
Db = Annotated[Session, Depends(get_db)]
Viewer = Annotated[EventAccess, Depends(require_event())]
TaskManager = Annotated[EventAccess, Depends(require_event("manage_tasks"))]
MessageManager = Annotated[EventAccess, Depends(require_event("manage_messages"))]
Assistant = Annotated[EventAccess, Depends(require_event("use_assistant"))]
Approver = Annotated[EventAccess, Depends(require_event("approve_proposals"))]


# Tasks
def _task(db: Session, event_id: uuid.UUID, task_id: uuid.UUID) -> EventTask:
    task = db.scalar(select(EventTask).where(EventTask.id == task_id, EventTask.event_id == event_id))
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return task


def _check_task_links(db: Session, event_id: uuid.UUID, participant_id: uuid.UUID | None) -> None:
    if participant_id and not db.scalar(
        select(Participant.id).where(Participant.id == participant_id, Participant.event_id == event_id)
    ):
        raise HTTPException(422, "Participant is not part of this event")


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(
    access: Viewer, db: Db, status_filter: TaskStatus | None = Query(default=None, alias="status"),
    priority: TaskPriority | None = None,
) -> list:
    query = select(EventTask).where(EventTask.event_id == access.event.id)
    if status_filter:
        query = query.where(EventTask.status == status_filter)
    if priority:
        query = query.where(EventTask.priority == priority)
    return list(db.scalars(query.order_by(EventTask.due_at.is_(None), EventTask.due_at, EventTask.created_at)))


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(body: TaskCreate, access: TaskManager, db: Db) -> EventTask:
    _check_task_links(db, access.event.id, body.participant_id)
    task = EventTask(event_id=access.event.id, **body.model_dump())
    db.add(task)
    db.flush()
    audit(db, access.event, access.user.id, "task.created", "task", task.id)
    db.commit()
    return task


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: uuid.UUID, body: TaskUpdate, access: TaskManager, db: Db) -> EventTask:
    task = _task(db, access.event.id, task_id)
    changes = body.model_dump(exclude_unset=True)
    _check_task_links(db, access.event.id, changes.get("participant_id"))
    for key, value in changes.items():
        setattr(task, key, value)
    audit(db, access.event, access.user.id, "task.updated", "task", task.id, {"fields": sorted(changes)})
    db.commit()
    return task


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: uuid.UUID, access: TaskManager, db: Db) -> None:
    db.delete(_task(db, access.event.id, task_id))
    audit(db, access.event, access.user.id, "task.deleted", "task", task_id)
    db.commit()


# Messages
def _message_out(message: EventMessage, names: dict) -> MessageOut:
    out = MessageOut.model_validate(message)
    out.participant_name = names.get(message.participant_id)
    return out


def _names(db: Session, event_id: uuid.UUID) -> dict:
    return dict(db.execute(select(Participant.id, Participant.name).where(Participant.event_id == event_id)).all())


def _message(db: Session, event_id: uuid.UUID, message_id: uuid.UUID) -> EventMessage:
    message = db.scalar(select(EventMessage).where(EventMessage.id == message_id, EventMessage.event_id == event_id))
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    return message


@router.get("/messages", response_model=list[MessageOut])
def list_messages(access: Viewer, db: Db, limit: int = Query(default=200, le=500)) -> list[MessageOut]:
    names = _names(db, access.event.id)
    rows = db.scalars(
        select(EventMessage).where(EventMessage.event_id == access.event.id).order_by(EventMessage.created_at.desc()).limit(limit)
    )
    return [_message_out(m, names) for m in rows]


@router.post("/messages", response_model=MessageOut, status_code=201)
def create_message(body: MessageCreate, access: MessageManager, db: Db) -> MessageOut:
    names = _names(db, access.event.id)
    if body.participant_id and body.participant_id not in names:
        raise HTTPException(422, "Participant is not part of this event")
    message = EventMessage(event_id=access.event.id, participant_id=body.participant_id, content=body.content, status="draft")
    db.add(message)
    db.commit()
    return _message_out(message, names)


@router.patch("/messages/{message_id}", response_model=MessageOut)
def edit_message(message_id: uuid.UUID, body: MessageUpdate, access: MessageManager, db: Db) -> MessageOut:
    message = _message(db, access.event.id, message_id)
    if message.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only drafts can be edited")
    message.content = body.content
    db.commit()
    return _message_out(message, _names(db, access.event.id))


@router.post("/messages/{message_id}/send", response_model=MessageOut)
def send_message(message_id: uuid.UUID, access: MessageManager, db: Db) -> MessageOut:
    """Explicit human action. Today this reaches only the simulator."""
    message = _message(db, access.event.id, message_id)
    claimed = db.execute(
        update(EventMessage)
        .where(EventMessage.id == message_id, EventMessage.status == "draft")
        .values(status="simulated_sent")
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This message was already sent")
    result = get_provider().send_message(None, message.content)
    db.refresh(message)
    message.status = result.status
    audit(db, access.event, access.user.id, "message.sent_simulated", "message", message.id)
    db.commit()
    return _message_out(message, _names(db, access.event.id))


@router.delete("/messages/{message_id}", status_code=204)
def delete_draft(message_id: uuid.UUID, access: MessageManager, db: Db) -> None:
    message = _message(db, access.event.id, message_id)
    if message.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only drafts can be deleted")
    db.delete(message)
    db.commit()


# AI assistant
@router.post("/ai/chat", response_model=ChatOut, dependencies=[Depends(rate_limit("ai", 30))])
def chat(body: ChatIn, access: Assistant, db: Db) -> ChatOut:
    conversation = None
    if body.conversation_id:
        conversation = db.scalar(
            select(AIConversation).where(
                AIConversation.id == body.conversation_id, AIConversation.event_id == access.event.id,
                AIConversation.actor_id == access.user.id, AIConversation.conversation_type == "organizer",
            )
        )
        if conversation is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    if conversation is None:
        conversation = AIConversation(event_id=access.event.id, actor_id=access.user.id, conversation_type="organizer")
        db.add(conversation)
        db.flush()
    result = organizer.respond(db, access, conversation, body.message)
    db.add(AIMessage(conversation_id=conversation.id, role="user", content=body.message))
    db.flush()
    db.add(AIMessage(conversation_id=conversation.id, role="assistant", content=result.reply, meta={"mode": result.mode}))
    db.commit()
    return ChatOut(
        conversation_id=conversation.id, reply=result.reply, mode=result.mode, tool_calls=result.tool_calls,
        proposals=[ProposalOut.model_validate(p) for p in result.proposals],
    )


@router.get("/ai/proposals", response_model=list[ProposalOut])
def list_proposals(access: Viewer, db: Db, status_filter: str | None = Query(default=None, alias="status", max_length=20)) -> list:
    query = select(AIActionProposal).where(AIActionProposal.event_id == access.event.id)
    if status_filter:
        query = query.where(AIActionProposal.approval_status == status_filter)
    return list(db.scalars(query.order_by(AIActionProposal.created_at.desc())))


@router.post("/ai/proposals/{proposal_id}/approve", response_model=ProposalOut)
def approve_proposal(proposal_id: uuid.UUID, access: Approver, db: Db) -> AIActionProposal:
    return workflow.approve(db, access, proposal_id)


@router.post("/ai/proposals/{proposal_id}/reject", response_model=ProposalOut)
def reject_proposal(proposal_id: uuid.UUID, access: Approver, db: Db) -> AIActionProposal:
    return workflow.reject(db, access, proposal_id)


# Simulator
def _sim_access(db: Session, user, event_id: uuid.UUID) -> Event:
    access = resolve_access(db, user, event_id)
    if access is None or not access.can("manage_messages"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    return access.event


def _sim_out(db: Session, convo: AIConversation) -> SimConversationOut:
    messages = db.scalars(select(AIMessage).where(AIMessage.conversation_id == convo.id).order_by(AIMessage.created_at, AIMessage.role.desc()))
    person = db.get(Participant, convo.participant_id) if convo.participant_id else None
    return SimConversationOut(
        id=convo.id, event_id=convo.event_id, phone=convo.simulated_phone, participant_name=person.name if person else None,
        step=(convo.state or {}).get("step"), messages=[SimMessage.model_validate(m) for m in messages],
    )


def _sim_convo(db: Session, user, conversation_id: uuid.UUID) -> tuple[AIConversation, Event]:
    convo = db.get(AIConversation, conversation_id)
    if convo is None or convo.conversation_type != "participant_simulator":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return convo, _sim_access(db, user, convo.event_id)


@simulator.get("/conversations", response_model=list[SimConversationOut])
def sim_list(event_id: uuid.UUID, user: CurrentUser, db: Db) -> list[SimConversationOut]:
    _sim_access(db, user, event_id)
    rows = db.scalars(
        select(AIConversation).where(AIConversation.event_id == event_id, AIConversation.conversation_type == "participant_simulator")
    )
    return [_sim_out(db, c) for c in rows]


@simulator.post("/conversations", response_model=SimConversationOut, status_code=201)
def sim_start(body: SimStart, user: CurrentUser, db: Db) -> SimConversationOut:
    _sim_access(db, user, body.event_id)
    existing = db.scalar(
        select(AIConversation).where(
            AIConversation.event_id == body.event_id, AIConversation.simulated_phone == body.phone,
            AIConversation.conversation_type == "participant_simulator",
        )
    )
    if existing:
        return _sim_out(db, existing)
    person = participant.find_participant_by_phone(db, body.event_id, body.phone)
    convo = AIConversation(
        event_id=body.event_id, conversation_type="participant_simulator", simulated_phone=body.phone,
        participant_id=person.id if person else None, state={},
    )
    db.add(convo)
    db.commit()
    return _sim_out(db, convo)


@simulator.post(
    "/conversations/{conversation_id}/messages", response_model=SimConversationOut,
    dependencies=[Depends(rate_limit("simulator", 60))],
)
def sim_message(conversation_id: uuid.UUID, body: SimMessageIn, user: CurrentUser, db: Db) -> SimConversationOut:
    convo, event = _sim_convo(db, user, conversation_id)
    participant.handle_message(db, event, convo, body.message)
    return _sim_out(db, convo)
