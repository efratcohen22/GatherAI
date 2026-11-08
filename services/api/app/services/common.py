import uuid

from sqlalchemy.orm import Session

from app.models.models import AnalyticsEvent, AuditLog, Event


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
