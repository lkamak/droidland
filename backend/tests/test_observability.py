import pytest

from app.experts import sync_experts
from app.models import NormalizedEvent
from app.observability import Observability
from app.sse import Broadcaster
from app.triggers import ActivationService, find_matching_triggers, upsert_trigger
from tests.conftest import EXPERTS_DIR


def _event():
    return NormalizedEvent(
        source="github",
        event_type="pull_request",
        external_ref="acme/widgets#5",
        payload={"action": "opened"},
    )


@pytest.mark.asyncio
async def test_refresh_filters_by_droidland_tag(db, fake_client, settings):
    # A session WITHOUT the droidland tag must be ignored.
    fake_client.sessions.append({"sessionId": "external-1", "status": "idle", "tags": []})

    sync_experts(db, EXPERTS_DIR)
    upsert_trigger(db, {
        "source": "github", "event_type": "pull_request",
        "condition": {"action": "opened"}, "expert_slug": "code-reviewer",
    })
    from app.experts import get_expert
    trigger = find_matching_triggers(db, _event())[0]
    svc = ActivationService(db, fake_client, settings)
    await svc.activate(trigger, get_expert(db, "code-reviewer"), _event(), "comp-123")

    obs = Observability(db, fake_client, Broadcaster(), settings)
    count = await obs.refresh_once()

    assert count == 1  # only the tagged droidland session
    cached = db.query("SELECT * FROM session_cache WHERE factory_session_id = 'sess-1'")
    assert cached and cached[0]["expert_slug"] == "code-reviewer"
    assert db.query_one(
        "SELECT 1 FROM session_cache WHERE factory_session_id = 'external-1'"
    ) is None


@pytest.mark.asyncio
async def test_refresh_stores_computers(db, fake_client, settings):
    # Mock computers response
    async def mock_list_computers():
        return {
            "data": [
                {
                    "id": "comp-1",
                    "provider": "e2b",
                    "state": "running",
                    "repos": ["acme/widgets"],
                    "lastSeen": "2026-01-01T12:00:00Z",
                }
            ]
        }
    fake_client.list_computers = mock_list_computers

    obs = Observability(db, fake_client, Broadcaster(), settings)
    await obs.refresh_once()

    computers = db.query("SELECT * FROM computers WHERE factory_computer_id = 'comp-1'")
    assert len(computers) == 1
    assert computers[0]["provider"] == "e2b"
    assert computers[0]["state"] == "running"
