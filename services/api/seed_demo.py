"""Loads the fictional Monsey demo into a development database. Idempotent: replaces the demo account."""
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.auth.service import create_user_with_org, hash_password
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.models import (
    Accommodation,
    AccommodationAssignment,
    AIConversation,
    AIMessage,
    Event,
    EventMessage,
    EventTask,
    LocalCredential,
    Organization,
    OrganizationMember,
    Participant,
    RegistrationRequest,
    RideAssignment,
    User,
    Vehicle,
)

DEMO_EMAIL = "demo@gatherai.example"
DEMO_PASSWORD = "demo-organizer-2026"

# name, status, needs ride, pickup, needs stay
PEOPLE = [
    ("Avi Rosen", "confirmed", False, None, False),          # driver 0
    ("Dina Halpern", "confirmed", False, None, False),       # driver 1
    ("Eitan Marcus", "confirmed", False, None, True),        # driver 2
    ("Noa Feld", "confirmed", False, None, False),           # driver 3
    ("Yoni Sasson", "confirmed", False, None, False),        # driver 4
    ("Tamar Levin", "confirmed", True, "Crown Heights", True),
    ("Shira Adler", "confirmed", True, "Crown Heights", True),
    ("Maya Stein", "confirmed", True, "Crown Heights", False),
    ("Ari Weiss", "confirmed", True, "Flatbush", True),
    ("Leah Cohen", "confirmed", True, "Flatbush", False),
    ("Gil Baruch", "confirmed", True, "Flatbush", True),
    ("Rina Katz", "confirmed", True, "Teaneck", False),
    ("Oren Shalev", "confirmed", True, "Teaneck", True),
    ("Hila Ben-Ami", "confirmed", True, "Teaneck", True),
    ("Dov Klein", "confirmed", True, "Passaic", False),
    ("Michal Peretz", "confirmed", True, "Passaic", True),
    ("Asher Green", "confirmed", True, "Passaic", True),
    ("Yael Mizrahi", "confirmed", True, "Crown Heights", True),
    ("Natan Oz", "confirmed", True, "Flatbush", False),
    ("Ruth Amsel", "confirmed", False, None, True),
    ("Boaz Tal", "confirmed", False, None, False),
    ("Sara Dayan", "confirmed", True, None, True),
    ("Ilan Vered", "confirmed", False, None, True),
    ("Gali Nir", "confirmed", True, "Teaneck", False),
    ("Tomer Lavi", "pending", True, "Crown Heights", True),
    ("Adi Harel", "pending", True, "Flatbush", False),
    ("Keren Solomon", "pending", False, None, True),
    ("Uri Bloch", "pending", False, None, False),
    ("Neta Shani", "waitlisted", True, "Teaneck", False),
    ("Roi Elkin", "waitlisted", False, None, True),
]
VEHICLES = [(0, 4, "Crown Heights"), (1, 3, "Flatbush"), (2, 3, "Teaneck"), (3, 3, "Passaic"), (4, 4, "Crown Heights")]
# Passenger indexes per vehicle. Vehicle 3 (Noa Feld) is the demo's cancelled driver.
RIDES = {0: [5, 6, 7], 1: [8, 9], 2: [11, 12], 3: [14, 15, 16], 4: [17]}
HOSTS = [
    ("The Rosenfeld Home", "Maple Avenue, Monsey", 5, None, []),
    ("The Azoulay Home", "Remsen Avenue, Monsey", 4, "No pets in the house.", ["has_pet"]),
    ("The Friedman Apartment", "Route 306, Monsey", 3, "Upstairs only; no step-free access.", ["step_free_required"]),
    ("The Gross Guest Suite", "College Road, Monsey", 2, None, []),
]
STAYS = {0: [5, 6, 8, 10], 1: [12, 13, 15], 2: [16, 17], 3: [2]}
TASKS = [
    ("Confirm Friday transportation", "high", "in_progress", 2),
    ("Contact accommodation hosts about arrival times", "high", "todo", 3),
    ("Finalize participant list", "urgent", "todo", 2),
    ("Prepare welcome messages", "medium", "todo", 4),
    ("Verify dietary requirements with caterer", "high", "blocked", 3),
    ("Confirm event schedule", "medium", "todo", 5),
    ("Find a replacement vehicle for Passaic", "urgent", "todo", 1),
    ("Print name tags", "low", "todo", 6),
    ("Assign greeters", "medium", "completed", 4),
    ("Collect missing pickup locations", "medium", "todo", 2),
]


def seed() -> None:
    if get_settings().app_env != "development":
        sys.exit("Demo data can only be loaded in development.")
    db = SessionLocal()
    old = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if old:
        org_ids = list(db.scalars(select(Organization.id).where(Organization.owner_user_id == old.id)))
        for org_id in org_ids:
            db.delete(db.get(Organization, org_id))
        db.flush()
        db.delete(old)
        db.commit()

    user = create_user_with_org(db, DEMO_EMAIL, "Demo Organizer")
    db.add(LocalCredential(user_id=user.id, password_hash=hash_password(DEMO_PASSWORD)))
    db.flush()
    org_id = db.scalar(select(OrganizationMember.organization_id).where(OrganizationMember.user_id == user.id))

    today = datetime.now(UTC).replace(hour=20, minute=0, second=0, microsecond=0)
    days_to_friday = ((4 - today.weekday()) % 7) or 7
    start = today + timedelta(days=days_to_friday + 7)
    event = Event(
        organization_id=org_id, slug="monsey-community-shabbat-weekend", name="Monsey Community Shabbat Weekend",
        description="A fictional community weekend used to demonstrate GatherAI.", event_type="shabbat_weekend",
        location="Monsey, New York", timezone="America/New_York", start_at=start, end_at=start + timedelta(days=1, hours=5),
        capacity=28, registration_status="open", event_status="registration_open", created_by=user.id,
    )
    db.add(event)
    db.flush()

    people = []
    for index, (name, status, ride, pickup, stay) in enumerate(PEOPLE):
        email_name = name.lower().replace(" ", ".").replace("-", "")
        people.append(
            Participant(
                event_id=event.id, name=name, email=f"{email_name}@example.com", phone=f"+1-555-01{index:02d}",
                registration_status=status, transportation_required=ride, pickup_location=pickup, accommodation_required=stay,
                dietary_preferences="Vegetarian" if index % 7 == 0 else None,
            )
        )
    db.add_all(people)
    db.flush()

    vehicles = []
    for index, (driver, seats, origin) in enumerate(VEHICLES):
        vehicles.append(
            Vehicle(
                event_id=event.id, driver_participant_id=people[driver].id, available_passenger_seats=seats,
                departure_location=origin, departure_at=start - timedelta(hours=5),
                status="driver_cancelled" if index == 3 else "active",
                notes="Driver told the organizers the car is unavailable." if index == 3 else None,
            )
        )
    db.add_all(vehicles)
    db.flush()
    for vehicle_index, riders in RIDES.items():
        db.add_all(RideAssignment(vehicle_id=vehicles[vehicle_index].id, participant_id=people[i].id) for i in riders)

    hosts = [
        Accommodation(event_id=event.id, host_name=n, host_contact="+1-555-0199", location=l, capacity=c, restrictions=r, excluded_tags=t)
        for n, l, c, r, t in HOSTS
    ]
    db.add_all(hosts)
    db.flush()
    for host_index, guests in STAYS.items():
        db.add_all(AccommodationAssignment(accommodation_id=hosts[host_index].id, participant_id=people[i].id) for i in guests)

    for title, priority, status, days in TASKS:
        db.add(EventTask(event_id=event.id, title=title, priority=priority, status=status, due_at=datetime.now(UTC) + timedelta(days=days)))
    db.add(RegistrationRequest(event_id=event.id, participant_id=people[21].id, request_type="transportation", request_details="Needs a ride; pickup not given yet"))
    db.add(EventMessage(event_id=event.id, participant_id=people[24].id, content="Hi Tomer, we received your registration and will confirm your place soon.", status="draft"))
    db.add(EventMessage(event_id=event.id, participant_id=people[25].id, content="Hi Adi, we received your registration and will confirm your place soon.", status="draft"))

    convo = AIConversation(event_id=event.id, conversation_type="participant_simulator", simulated_phone=people[7].phone, participant_id=people[7].id, state={})
    db.add(convo)
    db.flush()
    db.add(AIMessage(conversation_id=convo.id, role="user", content="Hi, am I confirmed?"))
    db.flush()
    db.add(AIMessage(conversation_id=convo.id, role="assistant", content="Your registration status is confirmed."))
    db.commit()
    print(f"Demo loaded. Sign in with {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    seed()
