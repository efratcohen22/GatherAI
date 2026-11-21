import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError("Datetime must include a timezone")
    return value


# Auth
class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)


class TokenOut(BaseModel):
    access_token: str


class OrganizationOut(ORM):
    id: uuid.UUID
    name: str
    role: str | None = None


class MeOut(ORM):
    id: uuid.UUID
    email: str
    display_name: str
    organizations: list[OrganizationOut]


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str
    role: str
    permissions: list[str] = []


class AddOrgMemberIn(BaseModel):
    email: EmailStr
    role: Literal["organizer", "co_organizer"]


class AddEventMemberIn(BaseModel):
    email: EmailStr
    permissions: list[str] | None = None


# Events
class EventBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    event_type: str = Field(default="custom", max_length=60)
    location: str = Field(default="", max_length=300)
    timezone: str = Field(default="UTC", max_length=60)
    start_at: datetime
    end_at: datetime
    capacity: int | None = Field(default=None, gt=0, le=100000)
    transportation_enabled: bool = True
    accommodation_enabled: bool = True

    _tz = field_validator("start_at", "end_at")(_aware)

    @model_validator(mode="after")
    def _dates(self) -> "EventBase":
        if self.end_at < self.start_at:
            raise ValueError("End must be on or after start")
        return self


class EventCreate(EventBase):
    organization_id: uuid.UUID | None = None


class EventUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    event_type: str | None = Field(default=None, max_length=60)
    location: str | None = Field(default=None, max_length=300)
    timezone: str | None = Field(default=None, max_length=60)
    start_at: datetime | None = None
    end_at: datetime | None = None
    capacity: int | None = Field(default=None, gt=0, le=100000)
    registration_status: Literal["not_open", "open", "closed"] | None = None
    event_status: (
        Literal["draft", "registration_open", "registration_closed", "in_progress", "completed", "cancelled"] | None
    ) = None
    transportation_enabled: bool | None = None
    accommodation_enabled: bool | None = None

    _tz = field_validator("start_at", "end_at")(_aware)


class EventOut(ORM):
    id: uuid.UUID
    organization_id: uuid.UUID
    slug: str
    name: str
    description: str
    event_type: str
    location: str
    timezone: str
    start_at: datetime
    end_at: datetime
    capacity: int | None
    registration_status: str
    event_status: str
    transportation_enabled: bool
    accommodation_enabled: bool
    archived_at: datetime | None
    created_at: datetime


class EventDetailOut(EventOut):
    role: str
    permissions: list[str]


class AlertOut(BaseModel):
    severity: Literal["info", "warning", "critical"]
    code: str
    title: str
    link: str


class OverviewOut(BaseModel):
    metrics: dict[str, int | None]
    alerts: list[AlertOut]


class AuditOut(ORM):
    id: uuid.UUID
    action: str
    entity_type: str
    entity_id: str | None
    changes: dict
    created_at: datetime


# Participants
RegStatus = Literal["pending", "confirmed", "waitlisted", "cancelled"]


class ParticipantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    transportation_required: bool = False
    pickup_location: str | None = Field(default=None, max_length=300)
    accommodation_required: bool = False
    dietary_preferences: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    registration_status: RegStatus | None = None


class ParticipantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    transportation_required: bool | None = None
    pickup_location: str | None = Field(default=None, max_length=300)
    accommodation_required: bool | None = None
    dietary_preferences: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=5000)
    tags: list[str] | None = Field(default=None, max_length=20)
    registration_status: RegStatus | None = None


class RequestOut(ORM):
    id: uuid.UUID
    participant_id: uuid.UUID
    request_type: str
    request_details: str
    status: str
    created_at: datetime


class ParticipantOut(ORM):
    id: uuid.UUID
    name: str
    email: str | None
    phone: str | None
    registration_status: str
    transportation_required: bool
    pickup_location: str | None
    accommodation_required: bool
    dietary_preferences: str | None
    notes: str | None
    tags: list[str]
    created_at: datetime
    ride_status: str = "not_needed"
    stay_status: str = "not_needed"
    open_requests: int = 0


class ParticipantPage(BaseModel):
    items: list[ParticipantOut]
    total: int
    page: int
    page_size: int


# Public registration
class PublicEventOut(BaseModel):
    slug: str
    name: str
    description: str
    event_type: str
    location: str
    timezone: str
    start_at: datetime
    end_at: datetime
    registration_open: bool
    availability: Literal["open", "limited", "full"]
    transportation_enabled: bool
    accommodation_enabled: bool


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    transportation_required: bool = False
    pickup_location: str | None = Field(default=None, max_length=300)
    accommodation_required: bool = False
    dietary_preferences: str | None = Field(default=None, max_length=500)
    consent: Literal[True]
    website: str = Field(default="", max_length=200, description="Honeypot; must stay empty")


class RegisterOut(BaseModel):
    registration_status: str
    manage_token: str


class ManagedRegistrationOut(BaseModel):
    event_name: str
    name: str
    registration_status: str
    transportation_required: bool
    pickup_location: str | None
    accommodation_required: bool
    dietary_preferences: str | None


class ManagedRegistrationUpdate(BaseModel):
    transportation_required: bool | None = None
    pickup_location: str | None = Field(default=None, max_length=300)
    accommodation_required: bool | None = None
    dietary_preferences: str | None = Field(default=None, max_length=500)


# Logistics
class VehicleCreate(BaseModel):
    driver_participant_id: uuid.UUID | None = None
    available_passenger_seats: int = Field(ge=0, le=100)
    departure_location: str = Field(default="", max_length=300)
    departure_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)
    excluded_tags: list[str] = Field(default_factory=list, max_length=20)

    _tz = field_validator("departure_at")(_aware)


class VehicleUpdate(BaseModel):
    available_passenger_seats: int | None = Field(default=None, ge=0, le=100)
    departure_location: str | None = Field(default=None, max_length=300)
    departure_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)
    status: Literal["active", "driver_cancelled", "retired"] | None = None

    _tz = field_validator("departure_at")(_aware)


class PersonRef(BaseModel):
    assignment_id: uuid.UUID
    participant_id: uuid.UUID
    name: str
    status: str


class VehicleOut(ORM):
    id: uuid.UUID
    driver_participant_id: uuid.UUID | None
    driver_name: str | None = None
    available_passenger_seats: int
    departure_location: str
    departure_at: datetime | None
    notes: str | None
    status: str
    seats_remaining: int = 0
    passengers: list[PersonRef] = []


class WaitingPerson(BaseModel):
    participant_id: uuid.UUID
    name: str
    registration_status: str
    detail: str | None = None
    has_conflict: bool = False


class TransportationOut(BaseModel):
    vehicles: list[VehicleOut]
    unassigned: list[WaitingPerson]
    total_open_seats: int
    shortage: int


class AssignIn(BaseModel):
    participant_id: uuid.UUID
    vehicle_id: uuid.UUID


class ConfirmIn(BaseModel):
    confirmation_source: str = Field(min_length=3, max_length=300)


class AccommodationCreate(BaseModel):
    host_name: str = Field(min_length=1, max_length=200)
    host_contact: str | None = Field(default=None, max_length=200)
    location: str = Field(default="", max_length=300)
    capacity: int = Field(ge=0, le=1000)
    restrictions: str | None = Field(default=None, max_length=2000)
    excluded_tags: list[str] = Field(default_factory=list, max_length=20)


class AccommodationUpdate(BaseModel):
    host_name: str | None = Field(default=None, min_length=1, max_length=200)
    host_contact: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=300)
    capacity: int | None = Field(default=None, ge=0, le=1000)
    restrictions: str | None = Field(default=None, max_length=2000)
    status: Literal["active", "driver_cancelled", "retired"] | None = None


class AccommodationOut(ORM):
    id: uuid.UUID
    host_name: str
    host_contact: str | None
    location: str | None
    capacity: int
    restrictions: str | None
    status: str
    beds_remaining: int = 0
    guests: list[PersonRef] = []


class AccommodationsOut(BaseModel):
    accommodations: list[AccommodationOut]
    unassigned: list[WaitingPerson]
    total_open_beds: int
    shortage: int


class StayAssignIn(BaseModel):
    participant_id: uuid.UUID
    accommodation_id: uuid.UUID


# Tasks
TaskStatus = Literal["todo", "in_progress", "blocked", "completed"]
TaskPriority = Literal["low", "medium", "high", "urgent"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=5000)
    status: TaskStatus = "todo"
    priority: TaskPriority = "medium"
    assigned_to: uuid.UUID | None = None
    participant_id: uuid.UUID | None = None
    due_at: datetime | None = None

    _tz = field_validator("due_at")(_aware)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assigned_to: uuid.UUID | None = None
    participant_id: uuid.UUID | None = None
    due_at: datetime | None = None

    _tz = field_validator("due_at")(_aware)


class TaskOut(ORM):
    id: uuid.UUID
    title: str
    description: str
    status: str
    priority: str
    assigned_to: uuid.UUID | None
    participant_id: uuid.UUID | None
    due_at: datetime | None
    created_at: datetime


# Messages
class MessageCreate(BaseModel):
    participant_id: uuid.UUID | None = None
    content: str = Field(min_length=1, max_length=4000)


class MessageUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class MessageOut(ORM):
    id: uuid.UUID
    participant_id: uuid.UUID | None
    participant_name: str | None = None
    channel: str
    direction: str
    content: str
    status: str
    created_at: datetime


# AI
class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None


class ToolCallOut(BaseModel):
    name: str
    ok: bool


class ProposalOut(ORM):
    id: uuid.UUID
    proposal_type: str
    proposed_payload: dict
    summary: str
    rationale: str
    validation_status: str
    approval_status: str
    failure_reason: str | None
    expires_at: datetime
    created_at: datetime


class ChatOut(BaseModel):
    conversation_id: uuid.UUID
    reply: str
    mode: Literal["live", "demo", "unavailable"]
    tool_calls: list[ToolCallOut]
    proposals: list[ProposalOut]


# Simulator
class SimStart(BaseModel):
    event_id: uuid.UUID
    phone: str = Field(min_length=5, max_length=40)


class SimMessageIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class SimMessage(ORM):
    role: str
    content: str
    created_at: datetime


class SimConversationOut(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    phone: str | None
    participant_name: str | None
    step: str | None
    messages: list[SimMessage]
