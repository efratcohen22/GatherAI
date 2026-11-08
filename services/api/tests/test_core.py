from app.api.participants import _csv_safe


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_event_vertical_slice(owner):
    event = owner.event(name="Retreat", capacity=20)
    assert event["id"] in [e["id"] for e in owner.get("/api/events").json()]
    assert owner.get(f"/api/events/{event['id']}").json()["name"] == "Retreat"


def test_event_dates_validated(owner):
    r = owner.post("/api/events", json={"name": "x", "start_at": "2030-01-02T00:00:00Z", "end_at": "2030-01-01T00:00:00Z"})
    assert r.status_code == 422


def test_overview_reflects_data(owner):
    eid = owner.event(capacity=10)["id"]
    owner.person(eid, "A", transportation_required=True, pickup_location="X")
    owner.person(eid, "B", status="waitlisted")
    m = owner.get(f"/api/events/{eid}/overview").json()["metrics"]
    assert (m["confirmed"], m["waitlisted"], m["without_rides"], m["available_capacity"]) == (1, 1, 1, 9)


def test_public_registration_and_duplicate(client, owner):
    event = owner.event(capacity=1)
    owner.patch(f"/api/events/{event['id']}", json={"registration_status": "open", "event_status": "registration_open"})
    body = {"name": "A", "email": "a@example.com", "consent": True}
    first = client.post(f"/api/public/events/{event['slug']}/register", json=body)
    assert first.status_code == 201 and first.json()["registration_status"] == "pending"
    assert client.post(f"/api/public/events/{event['slug']}/register", json=body).status_code == 409
    waitlisted = client.post(f"/api/public/events/{event['slug']}/register", json={**body, "email": "b@example.com"})
    assert waitlisted.json()["registration_status"] == "waitlisted"


def test_registration_requires_consent_and_empty_honeypot(client, owner):
    event = owner.event()
    owner.patch(f"/api/events/{event['id']}", json={"registration_status": "open", "event_status": "registration_open"})
    url = f"/api/public/events/{event['slug']}/register"
    assert client.post(url, json={"name": "A", "email": "a@example.com", "consent": False}).status_code == 422
    assert client.post(url, json={"name": "A", "email": "a@example.com", "consent": True, "website": "spam"}).status_code == 400


def test_draft_event_not_public(client, owner):
    assert client.get(f"/api/public/events/{owner.event()['slug']}").status_code == 404


def test_manage_token_flow(client, owner):
    event = owner.event()
    owner.patch(f"/api/events/{event['id']}", json={"registration_status": "open", "event_status": "registration_open"})
    token = client.post(
        f"/api/public/events/{event['slug']}/register", json={"name": "A", "email": "a@example.com", "consent": True}
    ).json()["manage_token"]
    assert client.patch(f"/api/public/registrations/{token}", json={"pickup_location": "Y"}).json()["pickup_location"] == "Y"
    assert client.post(f"/api/public/registrations/{token}/cancel").json()["registration_status"] == "cancelled"
    assert client.get("/api/public/registrations/wrong-token").status_code == 404


def test_confirm_blocked_at_capacity(owner):
    eid = owner.event(capacity=1)["id"]
    owner.person(eid, "A")
    person = owner.person(eid, "B", status="waitlisted")
    assert owner.patch(f"/api/events/{eid}/participants/{person['id']}", json={"registration_status": "confirmed"}).status_code == 409


def test_ride_capacity_enforced(owner):
    eid = owner.event()["id"]
    vehicle = owner.vehicle(eid, seats=1)
    a, b = owner.person(eid, "A"), owner.person(eid, "B")
    url = f"/api/events/{eid}/ride-assignments"
    assert owner.post(url, json={"participant_id": a["id"], "vehicle_id": vehicle["id"]}).status_code == 201
    r = owner.post(url, json={"participant_id": b["id"], "vehicle_id": vehicle["id"]})
    assert r.status_code == 409 and "capacity" in r.json()["detail"]


def test_no_conflicting_ride_and_no_cancelled(owner):
    eid = owner.event()["id"]
    v1, v2 = owner.vehicle(eid), owner.vehicle(eid)
    a, gone = owner.person(eid, "A"), owner.person(eid, "Gone", status="cancelled")
    url = f"/api/events/{eid}/ride-assignments"
    owner.post(url, json={"participant_id": a["id"], "vehicle_id": v1["id"]})
    assert owner.post(url, json={"participant_id": a["id"], "vehicle_id": v2["id"]}).status_code == 409
    assert owner.post(url, json={"participant_id": gone["id"], "vehicle_id": v2["id"]}).status_code == 409


def test_accommodation_capacity_and_restrictions(owner):
    eid = owner.event()["id"]
    host = owner.post(f"/api/events/{eid}/accommodations", json={"host_name": "H", "capacity": 1, "excluded_tags": ["has_pet"]}).json()
    pet, a, b = owner.person(eid, "P", tags=["has_pet"]), owner.person(eid, "A"), owner.person(eid, "B")
    url = f"/api/events/{eid}/accommodation-assignments"
    assert owner.post(url, json={"participant_id": pet["id"], "accommodation_id": host["id"]}).status_code == 409
    assert owner.post(url, json={"participant_id": a["id"], "accommodation_id": host["id"]}).status_code == 201
    assert owner.post(url, json={"participant_id": b["id"], "accommodation_id": host["id"]}).status_code == 409


def test_cancelling_driver_flags_vehicle_and_frees_seat(owner):
    eid = owner.event()["id"]
    driver, rider = owner.person(eid, "D"), owner.person(eid, "R")
    vehicle = owner.vehicle(eid, driver=driver["id"])
    owner.post(f"/api/events/{eid}/ride-assignments", json={"participant_id": rider["id"], "vehicle_id": vehicle["id"]})
    owner.patch(f"/api/events/{eid}/participants/{driver['id']}", json={"registration_status": "cancelled"})
    data = owner.get(f"/api/events/{eid}/transportation").json()
    assert data["vehicles"][0]["status"] == "driver_cancelled"
    assert "driver_cancelled" in [a["code"] for a in owner.get(f"/api/events/{eid}/overview").json()["alerts"]]


def test_ride_confirmation_requires_source(owner):
    eid = owner.event()["id"]
    v, a = owner.vehicle(eid), owner.person(eid, "A")
    aid = owner.post(f"/api/events/{eid}/ride-assignments", json={"participant_id": a["id"], "vehicle_id": v["id"]}).json()["id"]
    assert owner.post(f"/api/events/{eid}/ride-assignments/{aid}/confirm", json={}).status_code == 422
    assert owner.post(f"/api/events/{eid}/ride-assignments/{aid}/confirm", json={"confirmation_source": "Phone call"}).json()["status"] == "confirmed"


def test_task_workflow(owner):
    eid = owner.event()["id"]
    task = owner.post(f"/api/events/{eid}/tasks", json={"title": "T", "priority": "urgent"}).json()
    owner.patch(f"/api/events/{eid}/tasks/{task['id']}", json={"status": "completed"})
    assert owner.get(f"/api/events/{eid}/tasks", params={"status": "completed"}).json()[0]["id"] == task["id"]
    assert owner.get(f"/api/events/{eid}/tasks", params={"status": "todo"}).json() == []


def test_message_send_once_and_simulated(owner):
    eid = owner.event()["id"]
    m = owner.post(f"/api/events/{eid}/messages", json={"content": "Hi"}).json()
    assert m["status"] == "draft"
    assert owner.post(f"/api/events/{eid}/messages/{m['id']}/send").json()["status"] == "simulated_delivered"
    assert owner.post(f"/api/events/{eid}/messages/{m['id']}/send").status_code == 409


def test_csv_neutralizes_formulas():
    assert _csv_safe("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert _csv_safe("Avi") == "Avi"
