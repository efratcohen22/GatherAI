import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.models import AnalyticsEvent, AuditLog, Event, utcnow

LIVE_AI_EVENTS = ("ai_live_call",)


def audit(
    db: Session, event: Event, actor_id: uuid.UUID | None, action: str, entity_type: str,
    entity_id: object = None, changes: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            organization_id=event.organization_id, event_id=event.id, actor_id=actor_id, action=action,
            entity_type=entity_type, entity_id=str(entity_id) if entity_id else None, changes=changes or {},
        )
    )


def track(db: Session, name: str, event_id: uuid.UUID | None = None) -> None:
    db.add(AnalyticsEvent(name=name, event_id=event_id))


def ai_budget_available(db: Session, organization_id: uuid.UUID) -> bool:
    """True while the organization is under its rolling 24-hour live model budget."""
    limit = get_settings().ai_daily_request_limit
    if limit <= 0:
        return False
    used = db.scalar(
        select(func.count(AnalyticsEvent.id))
        .join(Event, Event.id == AnalyticsEvent.event_id)
        .where(
            Event.organization_id == organization_id,
            AnalyticsEvent.name.in_(LIVE_AI_EVENTS),
            AnalyticsEvent.created_at >= utcnow() - timedelta(hours=24),
        )
    )
    return (used or 0) < limit
