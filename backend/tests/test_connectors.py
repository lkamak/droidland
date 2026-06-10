import httpx
import pytest
import respx

from app.connectors import GitHubConnector, LinearConnector


@pytest.mark.asyncio
@respx.mock
async def test_github_connector_polls_and_advances_cursor():
    payload = [
        {
            "number": 7,
            "title": "Add feature",
            "html_url": "https://github.com/acme/widgets/pull/7",
            "created_at": "2026-01-02T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
            "draft": False,
            "user": {"login": "octocat"},
            "base": {"ref": "main"},
            "head": {"ref": "feature"},
        }
    ]
    respx.get("https://api.github.com/repos/acme/widgets/pulls").mock(
        return_value=httpx.Response(200, json=payload)
    )
    conn = GitHubConnector("tok", "acme/widgets")

    events, cursor = await conn.poll("")
    assert len(events) == 1
    assert events[0].external_ref == "acme/widgets#7"
    assert events[0].payload["action"] == "opened"
    assert cursor == "2026-01-02T00:00:00Z"

    # Re-poll with the advanced cursor -> nothing new
    events2, cursor2 = await conn.poll(cursor)
    assert events2 == []
    assert cursor2 == cursor


@pytest.mark.asyncio
@respx.mock
async def test_linear_connector_extracts_labels():
    data = {
        "data": {
            "issues": {
                "nodes": [
                    {
                        "id": "iss-1",
                        "identifier": "ENG-42",
                        "title": "Implement X",
                        "url": "https://linear.app/acme/issue/ENG-42",
                        "updatedAt": "2026-01-03T00:00:00.000Z",
                        "state": {"name": "Todo"},
                        "labels": {"nodes": [{"name": "implement"}]},
                    }
                ]
            }
        }
    }
    respx.post("https://api.linear.app/graphql").mock(
        return_value=httpx.Response(200, json=data)
    )
    conn = LinearConnector("lin-key")
    events, cursor = await conn.poll("")
    assert len(events) == 1
    assert events[0].event_type == "issue"
    assert events[0].payload["labels"] == ["implement"]
    assert cursor == "2026-01-03T00:00:00.000Z"


@pytest.mark.asyncio
@respx.mock
async def test_linear_connector_looks_back_with_negative_duration():
    """Empty cursor must query the PAST (negative duration), not the future."""
    import json

    route = respx.post("https://api.linear.app/graphql").mock(
        return_value=httpx.Response(200, json={"data": {"issues": {"nodes": []}}})
    )
    conn = LinearConnector("lin-key")
    await conn.poll("")

    body = json.loads(route.calls.last.request.content)
    assert body["variables"]["after"] == "-P1Y"
