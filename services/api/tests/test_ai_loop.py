"""Accommodation and task proposals, and the Anthropic loop against a fake client.

The fake verifies our loop handling only. It says nothing about the live API.
"""
import anthropic
import httpx

from app.agents import organizer
from app.core.config import Settings
from app.tools.registry import execute_tool
from tests.test_security_ai import _ctx, ask


def test_accommodation_proposal_respects_restrictions(owner):
    eid = owner.event()["id"]
    owner.post(f"/api/events/{eid}/accommodations", json={"host_name": "Pet Free", "capacity": 2, "excluded_tags": ["has_pet"]})
    owner.person(eid, "Pet Owner", accommodation_required=True, tags=["has_pet"])
    owner.person(eid, "Guest", accommodation_required=True)
    proposal = ask(owner, eid, "Can you suggest an accommodation arrangement?")["proposals"][0]
    assert [a["participant_name"] for a in proposal["proposed_payload"]["assignments"]] == ["Guest"]
    unresolved = proposal["proposed_payload"]["unresolved"][0]
    assert unresolved["name"] == "Pet Owner" and "No compatible bed" in unresolved["reason"]
    assert owner.post(f"/api/events/{eid}/ai/proposals/{proposal['id']}/approve").json()["approval_status"] == "executed"
    assert owner.get(f"/api/events/{eid}/accommodations").json()["accommodations"][0]["beds_remaining"] == 1


def test_task_proposal_applies_only_after_approval(owner, db):
    eid = owner.event()["id"]
    result, ok = execute_tool(_ctx(db, owner, eid), "propose_task_creation", {"tasks": [{"title": "Call caterer"}], "summary": "Add task"})
    db.commit()
    assert ok and owner.get(f"/api/events/{eid}/tasks").json() == []
    owner.post(f"/api/events/{eid}/ai/proposals/{result['proposal_id']}/approve")
    assert owner.get(f"/api/events/{eid}/tasks").json()[0]["title"] == "Call caterer"


class Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeAnthropic:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.beta = Block(messages=Block(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.script.pop(0)


def use_client(monkeypatch, client):
    monkeypatch.setattr(organizer, "get_settings", lambda: Settings(anthropic_api_key="test", app_env="test"))
    monkeypatch.setattr(organizer.anthropic, "Anthropic", lambda **_: client)


def tool_use(name, args):
    return Block(stop_reason="tool_use", content=[Block(type="tool_use", id="t1", name=name, input=args)])


def final(text):
    return Block(stop_reason="end_turn", content=[Block(type="text", text=text)])


def test_live_loop_runs_tool_and_returns_text(owner, monkeypatch):
    eid = owner.event()["id"]
    client = FakeAnthropic([tool_use("get_event_summary", {}), final("All good")])
    use_client(monkeypatch, client)
    result = ask(owner, eid, "summary")
    assert result["mode"] == "live" and result["reply"] == "All good"
    assert result["tool_calls"] == [{"name": "get_event_summary", "ok": True}]
    sent = client.calls[1]["messages"][-1]["content"][0]
    assert sent["type"] == "tool_result" and sent["is_error"] is False


def test_live_invalid_tool_args_returned_as_error(owner, monkeypatch):
    eid = owner.event()["id"]
    client = FakeAnthropic([tool_use("propose_ride_assignments", {"bad": 1}), final("Sorry")])
    use_client(monkeypatch, client)
    assert ask(owner, eid, "x")["tool_calls"][0]["ok"] is False
    assert client.calls[1]["messages"][-1]["content"][0]["is_error"] is True


def test_live_loop_is_budgeted(owner, monkeypatch):
    eid = owner.event()["id"]
    client = FakeAnthropic([tool_use("list_tasks", {}) for _ in range(20)])
    use_client(monkeypatch, client)
    result = ask(owner, eid, "x")
    assert len(client.calls) == 8 and "too many steps" in result["reply"]


def test_ai_outage_is_reported_safely(owner, monkeypatch):
    eid = owner.event()["id"]

    class Down(FakeAnthropic):
        def create(self, **kwargs):
            raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://example.test"))

    use_client(monkeypatch, Down([]))
    result = ask(owner, eid, "x")
    assert result["mode"] == "unavailable" and "No changes were made" in result["reply"]
