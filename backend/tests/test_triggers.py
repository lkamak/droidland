import pytest

from app.experts import get_expert, sync_experts
from app.models import NormalizedEvent
from app.triggers import (
    ActivationService,
    find_matching_triggers,
    match_condition,
    render_template,
    upsert_trigger,
)
from tests.conftest import EXPERTS_DIR


def _pr_event(action="opened", number=7):
    return NormalizedEvent(
        source="github",
        event_type="pull_request",
        external_ref=f"acme/widgets#{number}",
        title="Add feature",
        url="https://github.com/acme/widgets/pull/7",
        payload={"action": action, "number": number, "labels": ["needs-review"]},
    )


def test_match_condition_scalar():
    assert match_condition({"action": "opened"}, _pr_event("opened"))
    assert not match_condition({"action": "opened"}, _pr_event("synchronize"))


def test_match_condition_list_membership():
    assert match_condition({"labels": "needs-review"}, _pr_event())
    assert not match_condition({"labels": "wip"}, _pr_event())


def test_match_condition_empty_matches_all():
    assert match_condition({}, _pr_event())


def test_render_template():
    out = render_template("Review PR #{{number}}: {{title}}", _pr_event(number=7))
    assert out == "Review PR #7: Add feature"


def test_render_template_keeps_unknown_placeholders():
    assert render_template("{{missing}}", _pr_event()) == "{{missing}}"


def test_find_matching_triggers(db):
    sync_experts(db, EXPERTS_DIR)
    upsert_trigger(db, {
        "source": "github", "event_type": "pull_request",
        "condition": {"action": "opened"}, "expert_slug": "code-reviewer",
        "prompt_template": "Review {{external_ref}}",
    })
    upsert_trigger(db, {
        "source": "github", "event_type": "pull_request",
        "condition": {"action": "synchronize"}, "expert_slug": "pr-risk-analyzer",
    })
    matches = find_matching_triggers(db, _pr_event("opened"))
    assert len(matches) == 1
    assert matches[0].expert_slug == "code-reviewer"


@pytest.mark.asyncio
async def test_activation_creates_session(db, fake_client, settings):
    sync_experts(db, EXPERTS_DIR)
    tid = upsert_trigger(db, {
        "source": "github", "event_type": "pull_request",
        "condition": {"action": "opened"}, "expert_slug": "code-reviewer",
        "prompt_template": "Review {{external_ref}}",
    })
    trigger = find_matching_triggers(db, _pr_event())[0]
    expert = get_expert(db, "code-reviewer")
    svc = ActivationService(db, fake_client, settings)

    activation = await svc.activate(trigger, expert, _pr_event(), "comp-123")
    assert activation is not None
    assert activation["factory_session_id"] == "sess-1"
    assert activation["app_url"].endswith("sess-1")
    # message includes persona prompt + rendered template
    msg = [c for c in fake_client.calls if c[0] == "post_message"][0][1]["text"]
    assert "Code Reviewer expert" in msg
    assert "acme/widgets#7" in msg
    assert tid == trigger.id


@pytest.mark.asyncio
async def test_activation_dedupes(db, fake_client, settings):
    sync_experts(db, EXPERTS_DIR)
    upsert_trigger(db, {
        "source": "github", "event_type": "pull_request",
        "condition": {"action": "opened"}, "expert_slug": "code-reviewer",
    })
    trigger = find_matching_triggers(db, _pr_event())[0]
    expert = get_expert(db, "code-reviewer")
    svc = ActivationService(db, fake_client, settings)

    first = await svc.activate(trigger, expert, _pr_event(), "comp-123")
    second = await svc.activate(trigger, expert, _pr_event(), "comp-123")
    assert first is not None
    assert second is None  # duplicate external_ref -> skipped
    assert len([c for c in fake_client.calls if c[0] == "create_session"]) == 1
