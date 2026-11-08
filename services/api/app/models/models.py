"""Relational model. Portable between SQLite (development) and PostgreSQL (production)."""
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """Always timezone-aware UTC in Python, including on SQLite."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetimes are not allowed")
        return value.astimezone(UTC)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    pass


def _in(column: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    joined = ",".join(f"'{v}'" for v in values)
    return CheckConstraint(f"{column} IN ({joined})", name=name)


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(UTCDateTime(), default=utcnow, nullable=False)


def _fk(target: str, nullable: bool = False, ondelete: str = "CASCADE") -> Mapped[Any]:
    return mapped_column(Uuid, ForeignKey(target, ondelete=ondelete), nullable=nullable, index=True)


ORG_ROLES = ("organization_owner", "organizer", "co_organizer")
EVENT_STATUSES = ("draft", "registration_open", "registration_closed", "in_progress", "completed", "cancelled")
REGISTRATION_WINDOW = ("not_open", "open", "closed")
PARTICIPANT_STATUSES = ("pending", "confirmed", "waitlisted", "cancelled")
ASSIGNMENT_STATUSES = ("assigned", "confirmed", "removed")
RESOURCE_STATUSES = ("active", "driver_cancelled", "retired")
TASK_STATUSES = ("todo", "in_progress", "blocked", "completed")
TASK_PRIORITIES = ("low", "medium", "high", "urgent")
MESSAGE_STATUSES = ("draft", "simulated_sent", "simulated_delivered", "received", "failed")
PROPOSAL_STATUSES = ("pending", "approved", "rejected", "expired", "executed", "failed")
REQUEST_STATUSES = ("open", "resolved", "dismissed")


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(1000))
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = _created()


class LocalCredential(Base):
    """Development-only password store. Unused when AUTH_MODE=supabase."""

    __tablename__ = "local_credentials"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(300), nullable=False)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = _fk("users.id", ondelete="RESTRICT")
    created_at: Mapped[datetime] = _created()


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = (_in("role", ORG_ROLES, "ck_org_member_role"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        _in("event_status", EVENT_STATUSES, "ck_event_status"),
        _in("registration_status", REGISTRATION_WINDOW, "ck_event_registration"),
        CheckConstraint("capacity IS NULL OR capacity > 0", name="ck_event_capacity"),
        CheckConstraint("end_at >= start_at", name="ck_event_dates"),
    )
    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = _fk("organizations.id")
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), default="custom", nullable=False)
    location: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    timezone: Mapped[str] = mapped_column(String(60), default="UTC", nullable=False)
    start_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    end_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    capacity: Mapped[int | None] = mapped_column(Integer)
    registration_status: Mapped[str] = mapped_column(String(20), default="not_open", nullable=False)
    event_status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    transportation_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    accommodation_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_by: Mapped[uuid.UUID] = _fk("users.id", ondelete="RESTRICT")
    created_at: Mapped[datetime] = _created()


class EventMember(Base):
    __tablename__ = "event_members"
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(40), default="co_organizer", nullable=False)
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (
        _in("registration_status", PARTICIPANT_STATUSES, "ck_participant_status"),
        Index(
            "uq_participant_active_email",
            "event_id",
            "email",
            unique=True,
            sqlite_where=text("registration_status != 'cancelled' AND email IS NOT NULL"),
            postgresql_where=text("registration_status != 'cancelled' AND email IS NOT NULL"),
        ),
        Index("ix_participant_event_status", "event_id", "registration_status"),
    )
    id: Mapped[uuid.UUID] = _pk()
    event_id: Mapped[uuid.UUID] = _fk("events.id")
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    registration_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    transportation_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pickup_location: Mapped[str | None] = mapped_column(String(300))
    accommodation_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dietary_preferences: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    update_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = _created()


class RegistrationRequest(Base):
    __tablename__ = "registration_requests"
    __table_args__ = (_in("status", REQUEST_STATUSES, "ck_request_status"),)
    id: Mapped[uuid.UUID] = _pk()
    event_id: Mapped[uuid.UUID] = _fk("events.id")
    participant_id: Mapped[uuid.UUID] = _fk("participants.id")
    request_type: Mapped[str] = mapped_column(String(60), nullable=False)
    request_details: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    created_at: Mapped[datetime] = _created()


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        _in("status", RESOURCE_STATUSES, "ck_vehicle_status"),
        CheckConstraint("available_passenger_seats >= 0", name="ck_vehicle_seats"),
    )
    id: Mapped[uuid.UUID] = _pk()
    event_id: Mapped[uuid.UUID] = _fk("events.id")
    driver_participant_id: Mapped[uuid.UUID | None] = _fk("participants.id", nullable=True, ondelete="SET NULL")
    available_passenger_seats: Mapped[int] = mapped_column(Integer, nullable=False)
    departure_location: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    departure_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    notes: Mapped[str | None] = mapped_column(Text)
    excluded_tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)


class RideAssignment(Base):
    __tablename__ = "ride_assignments"
    __table_args__ = (
        _in("status", ASSIGNMENT_STATUSES, "ck_ride_status"),
        Index(
            "uq_ride_active_participant",
            "participant_id",
            unique=True,
            sqlite_where=text("status != 'removed'"),
            postgresql_where=text("status != 'removed'"),
        ),
    )
    id: Mapped[uuid.UUID] = _pk()
    vehicle_id: Mapped[uuid.UUID] = _fk("vehicles.id")
    participant_id: Mapped[uuid.UUID] = _fk("participants.id")
    status: Mapped[str] = mapped_column(String(20), default="assigned", nullable=False)
    confirmation_source: Mapped[str | None] = mapped_column(String(300))


class Accommodation(Base):
    __tablename__ = "accommodations"
    __table_args__ = (
        _in("status", RESOURCE_STATUSES, "ck_accommodation_status"),
        CheckConstraint("capacity >= 0", name="ck_accommodation_capacity"),
    )
    id: Mapped[uuid.UUID] = _pk()
    event_id: Mapped[uuid.UUID] = _fk("events.id")
    host_name: Mapped[str] = mapped_column(String(200), nullable=False)
    host_contact: Mapped[str | None] = mapped_column(String(200))
    location: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    restrictions: Mapped[str | None] = mapped_column(Text)
    excluded_tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)


class AccommodationAssignment(Base):
    __tablename__ = "accommodation_assignments"
    __table_args__ = (
        _in("status", ASSIGNMENT_STATUSES, "ck_stay_status"),
        Index(
            "uq_stay_active_participant",
            "participant_id",
            unique=True,
            sqlite_where=text("status != 'removed'"),
            postgresql_where=text("status != 'removed'"),
        ),
    )
    id: Mapped[uuid.UUID] = _pk()
    accommodation_id: Mapped[uuid.UUID] = _fk("accommodations.id")
    participant_id: Mapped[uuid.UUID] = _fk("participants.id")
    status: Mapped[str] = mapped_column(String(20), default="assigned", nullable=False)
    confirmation_source: Mapped[str | None] = mapped_column(String(300))


class EventTask(Base):
    __tablename__ = "event_tasks"
    __table_args__ = (
        _in("status", TASK_STATUSES, "ck_task_status"),
        _in("priority", TASK_PRIORITIES, "ck_task_priority"),
    )
    id: Mapped[uuid.UUID] = _pk()
    event_id: Mapped[uuid.UUID] = _fk("events.id")
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="todo", nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    assigned_to: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True, ondelete="SET NULL")
    participant_id: Mapped[uuid.UUID | None] = _fk("participants.id", nullable=True, ondelete="SET NULL")
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = _created()


class EventMessage(Base):
    __tablename__ = "event_messages"
    __table_args__ = (
        _in("status", MESSAGE_STATUSES, "ck_message_status"),
        _in("direction", ("outbound", "inbound"), "ck_message_direction"),
    )
    id: Mapped[uuid.UUID] = _pk()
    event_id: Mapped[uuid.UUID] = _fk("events.id")
    participant_id: Mapped[uuid.UUID | None] = _fk("participants.id", nullable=True)
    channel: Mapped[str] = mapped_column(String(30), default="simulator", nullable=False)
    direction: Mapped[str] = mapped_column(String(10), default="outbound", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    created_at: Mapped[datetime] = _created()


class AIConversation(Base):
    __tablename__ = "ai_conversations"
    id: Mapped[uuid.UUID] = _pk()
    event_id: Mapped[uuid.UUID] = _fk("events.id")
    actor_id: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True, ondelete="SET NULL")
    conversation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    simulated_phone: Mapped[str | None] = mapped_column(String(40))
    participant_id: Mapped[uuid.UUID | None] = _fk("participants.id", nullable=True, ondelete="SET NULL")
    state: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = _created()


class AIMessage(Base):
    __tablename__ = "ai_messages"
    id: Mapped[uuid.UUID] = _pk()
    conversation_id: Mapped[uuid.UUID] = _fk("ai_conversations.id")
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = _created()


class AIActionProposal(Base):
    __tablename__ = "ai_action_proposals"
    __table_args__ = (_in("approval_status", PROPOSAL_STATUSES, "ck_proposal_status"),)
    id: Mapped[uuid.UUID] = _pk()
    event_id: Mapped[uuid.UUID] = _fk("events.id")
    proposal_type: Mapped[str] = mapped_column(String(40), nullable=False)
    proposed_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    validation_status: Mapped[str] = mapped_column(String(20), default="valid", nullable=False)
    approval_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    state_fingerprint: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    created_by: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True, ondelete="SET NULL")
    approved_by: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True, ondelete="SET NULL")
    created_at: Mapped[datetime] = _created()


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = _fk("organizations.id")
    event_id: Mapped[uuid.UUID | None] = _fk("events.id", nullable=True)
    actor_id: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True, ondelete="SET NULL")
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(60))
    changes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = _created()


class AnalyticsEvent(Base):
    """Counts product actions. Stores no personal data."""

    __tablename__ = "analytics_events"
    id: Mapped[uuid.UUID] = _pk()
    event_id: Mapped[uuid.UUID | None] = _fk("events.id", nullable=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    created_at: Mapped[datetime] = _created()
