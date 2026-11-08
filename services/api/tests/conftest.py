import os
import tempfile
import uuid
from datetime import UTC, datetime, timedelta

_tmp = tempfile.mkdtemp()
os.environ.update(
    APP_ENV="test", AUTH_MODE="local", ANTHROPIC_API_KEY="", DATABASE_URL=f"sqlite:///{_tmp}/test.db",
)

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import reset_rate_limits
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.models import Base


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    reset_rate_limits()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


class Org:
    def __init__(self, client: TestClient, name: str = "owner"):
        self.client = client
        self.email = f"{name}-{uuid.uuid4().hex[:6]}@example.com"
        r = client.post("/api/auth/local/signup", json={"email": self.email, "password": "password123", "display_name": name})
        assert r.status_code == 201, r.text
        self.headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    def get(self, url, **kw):
        return self.client.get(url, headers=self.headers, **kw)

    def post(self, url, **kw):
        return self.client.post(url, headers=self.headers, **kw)

    def patch(self, url, **kw):
        return self.client.patch(url, headers=self.headers, **kw)

    def delete(self, url, **kw):
        return self.client.delete(url, headers=self.headers, **kw)

    def event(self, **overrides):
        start = datetime.now(UTC) + timedelta(days=10)
        body = {"name": "Test Event", "start_at": start.isoformat(), "end_at": (start + timedelta(days=1)).isoformat(), **overrides}
        r = self.post("/api/events", json=body)
        assert r.status_code == 201, r.text
        return r.json()

    def person(self, event_id, name="Person", status="confirmed", **extra):
        r = self.post(f"/api/events/{event_id}/participants", json={"name": name, "registration_status": status, **extra})
        assert r.status_code == 201, r.text
        return r.json()

    def vehicle(self, event_id, seats=2, driver=None, **extra):
        r = self.post(f"/api/events/{event_id}/vehicles", json={"available_passenger_seats": seats, "driver_participant_id": driver, **extra})
        assert r.status_code == 201, r.text
        return r.json()


@pytest.fixture
def owner(client):
    return Org(client, "owner")


@pytest.fixture
def other(client):
    return Org(client, "other")
