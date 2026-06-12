import shutil
from pathlib import Path
from typing import Any

import pytest

from app.config import Settings
from app.context import build_context
from app.db import Database

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERTS_DIR = str(REPO_ROOT / ".factory" / "droids")


class FakeFactoryClient:
    """Duck-typed stand-in for FactoryClient that records calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.sessions: list[dict[str, Any]] = []
        self._session_seq = 0

    async def create_computer(self, name, repos, provider="e2b", auto_install_deps=True):
        self.calls.append(("create_computer", {"name": name, "repos": repos}))
        return {"id": "comp-123", "status": "active", "name": name}

    async def get_computer(self, computer_id):
        return {"id": computer_id, "status": "active"}

    async def list_computers(self):
        return {"computers": [{"id": "comp-123", "status": "active"}]}

    async def create_session(self, computer_id, cwd="", settings=None):
        self._session_seq += 1
        sid = f"sess-{self._session_seq}"
        self.calls.append(("create_session", {"computerId": computer_id, "settings": settings}))
        self.sessions.append({
            "sessionId": sid,
            "status": "running",
            "tags": (settings or {}).get("tags", []),
            "settings": settings,
        })
        return {"sessionId": sid, "status": "running"}

    async def post_message(self, session_id, text):
        self.calls.append(("post_message", {"session_id": session_id, "text": text}))
        return {"messageId": "msg-1", "status": "running"}

    async def get_session(self, session_id):
        return {"sessionId": session_id, "status": "running"}

    async def list_sessions(self, computer_id=None, limit=50, cursor=None):
        return {"sessions": self.sessions, "pagination": {"hasMore": False, "nextCursor": None}}

    async def interrupt_session(self, session_id):
        return {"status": "idle"}

    async def get_session_messages(self, session_id):
        verdict_json = '{"verdict": "pass", "summary": "No issues found"}'
        assistant_content = f"I'll review the changes.\n\n```json\n{verdict_json}\n```"
        return {
            "messages": [
                {
                    "role": "user",
                    "content": "Review this PR",
                    "timestamp": "2026-06-10T12:00:00Z",
                },
                {
                    "role": "assistant",
                    "content": assistant_content,
                    "timestamp": "2026-06-10T12:01:00Z",
                },
            ]
        }


@pytest.fixture
def settings(tmp_path) -> Settings:
    # Copy the prebuilt experts into a temp dir so authoring writes never touch the repo.
    experts_copy = tmp_path / "droids"
    shutil.copytree(EXPERTS_DIR, experts_copy)
    return Settings(
        factory_api_key="test-key",
        db_path=str(tmp_path / "test.db"),
        experts_dir=str(experts_copy),
        target_repo="acme/widgets",
    )


@pytest.fixture
def db(settings) -> Database:
    return Database(settings.db_path)


@pytest.fixture
def fake_client() -> FakeFactoryClient:
    return FakeFactoryClient()


@pytest.fixture
def context(settings, db, fake_client):
    return build_context(settings=settings, db=db, client=fake_client, connectors=[])


@pytest.fixture
def app_client(context):
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app(context=context, start_background=False)
    with TestClient(app) as client:
        yield client
