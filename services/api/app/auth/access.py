"""Event authorization. Unauthorized events return 404 so their existence is not disclosed."""
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.service import CurrentUser
from app.db.session import get_db
from app.models.models import Event, EventMember, OrganizationMember, User

ALL_PERMISSIONS = frozenset(
    {
        "view",
        "manage_event",
        "manage_participants",
        "manage_logistics",
        "manage_tasks",
        "manage_messages",
        "use_assistant",
        "approve_proposals",
    }
)
DEFAULT_CO_ORGANIZER = ["view", "manage_logistics", "manage_tasks", "manage_messages", "use_assistant"]


@dataclass
class EventAccess:
    event: Event
    user: User
    role: str
    permissions: frozenset[str]

    def can(self, permission: str) -> bool:
        return permission in self.permissions


def resolve_access(db: Session, user: User, event_id: uuid.UUID) -> EventAccess | None:
    event = db.get(Event, event_id)
    if event is None:
        return None
    org_member = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == event.organization_id,
            OrganizationMember.user_id == user.id,
            OrganizationMember.status == "active",
        )
    )
    if org_member and org_member.role in ("organization_owner", "organizer"):
        return EventAccess(event, user, org_member.role, ALL_PERMISSIONS)
    member = db.scalar(select(EventMember).where(EventMember.event_id == event_id, EventMember.user_id == user.id))
    if member is None:
        return None
    # Stored permissions are intersected with known ones and always include view.
    return EventAccess(event, user, member.role, frozenset(member.permissions) & ALL_PERMISSIONS | {"view"})


def require_event(permission: str = "view") -> Callable[..., EventAccess]:
    def dependency(
        event_id: uuid.UUID, user: CurrentUser, db: Annotated[Session, Depends(get_db)]
    ) -> EventAccess:
        access = resolve_access(db, user, event_id)
        if access is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
        if not access.can(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Missing permission: {permission}")
        return access

    return dependency
