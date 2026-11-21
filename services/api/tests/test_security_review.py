"""Regressions for the M7 independent security review findings (see docs/SECURITY.md)."""
import pytest
from pydantic import ValidationError

from app.api.participants import _csv_safe
from app.core.config import Settings
from tests.conftest import Org
from tests.test_security_ai import ask


def co_organizer(client, owner, eid, permissions=None):
    co = Org(client, "co")
    body = {"email": co.email} if permissions is None else {"email": co.email, "permissions": permissions}
    assert owner.post(f"/api/events/{eid}/members", json=body).status_code == 201
    return co


# H1
def test_local_auth_requires_explicit_dev_env_and_strong_secret(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("LOCAL_JWT_SECRET", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, auth_mode="local")  # APP_ENV now defaults to production
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="development", auth_mode="local", local_jwt_secret="short")
    assert Settings(_env_file=None, app_env="development", auth_mode="local", local_jwt_secret="x" * 32).auth_mode == "local"


# M1
def test_simulator_needs_participant_management(client, owner):
    eid = owner.event()["id"]
    owner.person(eid, "Victim", phone="+1-555-7777")
    co = co_organizer(client, owner, eid)  # default co-organizer: manage_messages, not manage_participants
    assert co.post("/api/simulator/conversations", json={"event_id": eid, "phone": "+1-555-7777"}).status_code == 404
    assert co.get(f"/api/simulator/conversations?event_id={eid}").status_code == 404


# M2
def test_search_does_not_match_masked_email(client, owner):
    eid = owner.event()["id"]
    owner.person(eid, "Victim", email="secret.person@hidden.example")
    co = co_organizer(client, owner, eid)
    assert co.get(f"/api/events/{eid}/participants", params={"search": "secret.person"}).json()["total"] == 0
    assert owner.get(f"/api/events/{eid}/participants", params={"search": "secret.person"}).json()["total"] == 1


# M3
def test_host_address_hidden_without_logistics_permission(client, owner):
    eid = owner.event()["id"]
    owner.post(f"/api/events/{eid}/accommodations", json={"host_name": "Host", "location": "12 Private St", "capacity": 2,
                                                         "restrictions": "No pets"})
    viewer = co_organizer(client, owner, eid, ["view"])
    stay = viewer.get(f"/api/events/{eid}/accommodations").json()["accommodations"][0]
    assert stay["location"] is None and stay["restrictions"] is None and stay["host_contact"] is None
    assert owner.get(f"/api/events/{eid}/accommodations").json()["accommodations"][0]["location"] == "12 Private St"


def test_proposal_labels_do_not_carry_host_address(owner):
    eid = owner.event()["id"]
    owner.post(f"/api/events/{eid}/accommodations", json={"host_name": "Host", "location": "12 Private St", "capacity": 2})
    owner.person(eid, "Guest", accommodation_required=True)
    proposal = ask(owner, eid, "Can you suggest an accommodation arrangement?")["proposals"][0]
    assert "Private St" not in str(proposal)


# L3
def test_task_assignee_must_be_on_event_team(client, owner, other):
    eid = owner.event()["id"]
    stranger = other.get("/api/auth/me").json()["id"]
    assert owner.post(f"/api/events/{eid}/tasks", json={"title": "T", "assigned_to": stranger}).status_code == 422
    me = owner.get("/api/auth/me").json()["id"]
    assert owner.post(f"/api/events/{eid}/tasks", json={"title": "T", "assigned_to": me}).status_code == 201


# L5
def test_rule_based_reminder_without_message_permission(client, owner):
    eid = owner.event()["id"]
    owner.person(eid, "Pending Person", status="pending")
    co = co_organizer(client, owner, eid, ["view", "use_assistant"])
    r = co.post(f"/api/events/{eid}/ai/chat", json={"message": "Draft a reminder for participants who have not confirmed"})
    assert r.status_code == 200 and "could not draft" in r.json()["reply"]


# L6
def test_self_update_respects_disabled_modules(client, owner):
    event = owner.event()
    owner.patch(f"/api/events/{event['id']}", json={"registration_status": "open", "event_status": "registration_open",
                                                    "accommodation_enabled": False})
    token = client.post(f"/api/public/events/{event['slug']}/register",
                        json={"name": "A", "email": "a@example.com", "consent": True}).json()["manage_token"]
    assert client.patch(f"/api/public/registrations/{token}", json={"accommodation_required": True}).json()["accommodation_required"] is False


# L7
def test_csv_guard_covers_whitespace_and_pipes():
    assert _csv_safe(" =1+1").startswith("'")
    assert _csv_safe("|cmd").startswith("'")
    assert _csv_safe("%x").startswith("'")


# L8
def test_cannot_remove_member_with_more_permissions(client, owner):
    eid = owner.event()["id"]
    manager = co_organizer(client, owner, eid, ["view", "manage_event"])
    approver = co_organizer(client, owner, eid, ["view", "approve_proposals"])
    approver_id = approver.get("/api/auth/me").json()["id"]
    assert manager.delete(f"/api/events/{eid}/members/{approver_id}").status_code == 403
    assert owner.delete(f"/api/events/{eid}/members/{approver_id}").status_code == 204
