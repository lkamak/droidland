import httpx
import pytest
import respx

from app.factory_client import FactoryClient, _normalize_repo


def test_normalize_repo_short_form():
    assert _normalize_repo("acme/widgets") == "https://github.com/acme/widgets.git"


def test_normalize_repo_full_https():
    assert _normalize_repo("https://github.com/acme/widgets.git") == (
        "https://github.com/acme/widgets.git"
    )


def test_normalize_repo_ssh():
    assert _normalize_repo("git@github.com:acme/widgets.git") == "git@github.com:acme/widgets.git"


def test_normalize_repo_passthrough_for_unknown():
    assert _normalize_repo("not-a-repo") == "not-a-repo"


@pytest.mark.asyncio
@respx.mock
async def test_create_computer_sends_remote_user_and_normalized_repos():
    route = respx.post("https://api.factory.ai/api/v0/computers").mock(
        return_value=httpx.Response(200, json={"id": "comp-1", "status": "active"})
    )
    client = FactoryClient(api_key="test", base_url="https://api.factory.ai")

    await client.create_computer(name="test", repos=["acme/widgets"])

    assert route.called
    body = route.calls.last.request.read().decode()
    assert "remoteUser" in body
    assert "https://github.com/acme/widgets.git" in body
