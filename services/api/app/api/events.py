import re
import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth.access import ALL_PERMISSIONS, DEFAULT_CO_ORGANIZER, EventAccess, require_event, resolve_access
from app.auth.service import CurrentUser
from app.db.session import get_db
from app.models.models import AuditLog, Event, EventMember, OrganizationMember, User, utcnow
from app.schemas.schemas import (
    AddEventMemberIn,
    AuditOut,
    EventCreate,
    EventDetailOut,
    EventOut,
    EventUpdate,
    MemberOut,
    OverviewOut,
)
from app.services.common import audit, track
from app.services.planning import overview as build_overview

router = APIRouter(prefix="/api/events", tags=["events"])
Db = Annotated[Session, Depends(get_db)]


def _slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80] or "event"
    return f"{base}-{secrets.token_hex(3)}"


def _detail(access: EventAccess) -> EventDetailOut:
    data = EventOut.model_validate(access.event).model_dump()
    return EventDetailOut(**data, role=access.role, permissions=sorted(access.permissions))


@router.get("", response_model=list[EventOut])
def list_events(user: CurrentUser, db: Db, include_archived: bool = Query(default=False)) -> list[Event]:
    managed_orgs = select(OrganizationMember.organization_id).where(
        OrganizationMember.user_id == user.id, OrganizationMember.status == "active",
        OrganizationMember.role.in_(("organization_owner", "organizer")),
    )
    assigned = select(EventMember.event_id).where(EventMember.user_id == user.id)
    query = select(Event).where(or_(Event.organization_id.in_(managed_orgs), Event.id.in_(assigned)))
    if not include_archived:
        query = query.where(Event.archived_at.is_(None))
    return list(db.scalars(query.order_by(Event.start_at)))


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(body: EventCreate, user: CurrentUser, db: Db) -> Event:
    query = select(OrganizationMember).where(
        OrganizationMember.user_id == user.id, OrganizationMember.status == "active",
        OrganizationMember.role.in_(("organization_owner", "organizer")),
    )
    if body.organization_id:
        query = query.where(OrganizationMember.organization_id == body.organization_id)
    member = db.scalars(query).first()
    if member is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot create events in this organization")
    event = Event(
        **body.model_dump(exclude={"organization_id"}), organization_id=member.organization_id,
        slug=_slug(body.name), created_by=user.id,
    )
    db.add(event)
    db.flush()
    audit(db, event, user.id, "event.created", "event", event.id)
    track(db, "event_created", event.id)
    db.commit()
    return event


@router.get("/{event_id}", response_model=EventDetailOut)
def get_event(access: Annotated[EventAccess, Depends(require_event())]) -> EventDetailOut:
    return _detail(access)


@router.patch("/{event_id}", response_model=EventDetailOut)
def update_event(body: EventUpdate, access: Annotated[EventAccess, Depends(require_event("manage_event"))], db: Db) -> EventDetailOut:
    changes = body.model_dump(exclude_unset=True)
    event = access.event
    start, end = changes.get("start_at", event.start_at), changes.get("end_at", event.end_at)
    if start is None or end is None or end < start:
        raise HTTPException(422, "End must be on or after start")
    for key, value in changes.items():
        setattr(event, key, value)
    audit(db, event, access.user.id, "event.updated", "event", event.id, {"fields": sorted(changes)})
    db.commit()
    return _detail(access)


@router.post("/{event_id}/archive", response_model=EventDetailOut)
def archive_event(access: Annotated[EventAccess, Depends(require_event("manage_event"))], db: Db) -> EventDetailOut:
    access.event.archived_at = utcnow()
    audit(db, access.event, access.user.id, "event.archived", "event", access.event.id)
    db.commit()
    return _detail(access)


@router.get("/{event_id}/overview", response_model=OverviewOut)
def event_overview(access: Annotated[EventAccess, Depends(require_event())], db: Db) -> dict:
    return build_overview(db, access.event)


@router.get("/{event_id}/activity", response_model=list[AuditOut])
def activity(access: Annotated[EventAccess, Depends(require_event())], db: Db, limit: int = Query(default=30, le=100)) -> list:
    return list(
        db.scalars(select(AuditLog).where(AuditLog.event_id == access.event.id).order_by(AuditLog.created_at.desc()).limit(limit))
    )


@router.get("/{event_id}/members", response_model=list[MemberOut])
def event_members(access: Annotated[EventAccess, Depends(require_event())], db: Db) -> list[MemberOut]:
    rows = db.execute(
        select(User, EventMember).join(EventMember, EventMember.user_id == User.id).where(EventMember.event_id == access.event.id)
    ).all()
    return [
        MemberOut(user_id=u.id, email=u.email, display_name=u.display_name, role=m.role, permissions=m.permissions)
        for u, m in rows
    ]


@router.post("/{event_id}/members", response_model=MemberOut, status_code=201)
def add_event_member(body: AddEventMemberIn, access: Annotated[EventAccess, Depends(require_event("manage_event"))], db: Db) -> MemberOut:
    target = db.scalar(select(User).where(User.email == body.email.lower()))
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No GatherAI account uses this email yet")
    if resolve_access(db, target, access.event.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This person already has access")
    permissions = body.permissions if body.permissions is not None else DEFAULT_CO_ORGANIZER
    if not set(permissions) <= ALL_PERMISSIONS:
        raise HTTPException(422, "Unknown permission")
    if not set(permissions) <= access.permissions:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot grant permissions you do not hold")
    db.add(EventMember(event_id=access.event.id, user_id=target.id, role="co_organizer", permissions=permissions))
    audit(db, access.event, access.user.id, "event.member_added", "user", target.id, {"permissions": permissions})
    db.commit()
    return MemberOut(user_id=target.id, email=target.email, display_name=target.display_name, role="co_organizer", permissions=permissions)


@router.delete("/{event_id}/members/{user_id}", status_code=204)
def remove_event_member(user_id: uuid.UUID, access: Annotated[EventAccess, Depends(require_event("manage_event"))], db: Db) -> None:
    member = db.get(EventMember, (access.event.id, user_id))
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    if not set(member.permissions) & ALL_PERMISSIONS <= access.permissions:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot remove a member with permissions you do not hold")
    db.delete(member)
    audit(db, access.event, access.user.id, "event.member_removed", "user", user_id)
    db.commit()
