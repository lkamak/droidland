import asyncio
import json
import logging
import re
from datetime import UTC, datetime

from .config import Settings
from .db import Database, dumps
from .factory_client import FactoryClient
from .sse import Broadcaster

log = logging.getLogger("droidland.observability")

_VERDICT_RE = re.compile(r'```json\s*(\{[^`]*"verdict"\s*:[^`]*\})\s*```', re.DOTALL)


DROIDLAND_TAG = "droidland"


def _sessions_from_response(data: dict) -> list[dict]:
    if isinstance(data, dict):
        for key in ("sessions", "data", "items"):
            if isinstance(data.get(key), list):
                return data[key]
    return data if isinstance(data, list) else []


def _has_tag(session: dict, name: str) -> bool:
    return any((t or {}).get("name") == name for t in (session.get("tags") or []))


def _expert_from_tags(session: dict) -> str:
    for t in session.get("tags") or []:
        n = (t or {}).get("name", "")
        if n.startswith("expert:"):
            return n.split(":", 1)[1]
    return ""


def _extract_verdict(text: str) -> dict | None:
    """Extract verdict JSON from a fenced code block in session text."""
    match = _VERDICT_RE.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


class Observability:
    def __init__(
        self, db: Database, client: FactoryClient, broadcaster: Broadcaster, settings: Settings
    ):
        self.db = db
        self.client = client
        self.broadcaster = broadcaster
        self.settings = settings
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def refresh_once(self) -> int:
        data = await self.client.list_sessions(limit=100)
        sessions = [s for s in _sessions_from_response(data) if _has_tag(s, DROIDLAND_TAG)]
        now = datetime.now(UTC).isoformat()
        for s in sessions:
            session_id = s.get("sessionId") or s.get("id")
            if not session_id:
                continue
            self.db.execute(
                """
                INSERT INTO session_cache
                    (factory_session_id, expert_slug, status, tokens_json, app_url, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(factory_session_id) DO UPDATE SET
                    expert_slug=COALESCE(
                        NULLIF(excluded.expert_slug, ''), session_cache.expert_slug
                    ),
                    status=excluded.status, tokens_json=excluded.tokens_json,
                    updated_at=excluded.updated_at
                """,
                (
                    session_id,
                    _expert_from_tags(s),
                    s.get("status", ""),
                    dumps(s.get("tokenUsage", {})),
                    self.settings.session_app_url(session_id),
                    now,
                ),
            )
            
            # Update activation status from session
            status = s.get("status", "")
            if status:
                self.db.execute(
                    "UPDATE activations SET status = ? WHERE factory_session_id = ?",
                    (status, session_id),
                )

        # Extract verdicts for completed activations
        await self._extract_verdicts()

        # Fetch and store computers
        computers_data = await self.client.list_computers()
        computers = computers_data.get("data", []) if isinstance(computers_data, dict) else []
        for comp in computers:
            comp_id = comp.get("id")
            if not comp_id:
                continue
            self.db.execute(
                """
                INSERT INTO computers
                    (factory_computer_id, provider, state, repos_json, last_seen, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(factory_computer_id) DO UPDATE SET
                    provider=excluded.provider,
                    state=excluded.state,
                    repos_json=excluded.repos_json,
                    last_seen=excluded.last_seen,
                    updated_at=excluded.updated_at
                """,
                (
                    comp_id,
                    comp.get("provider", ""),
                    comp.get("state", ""),
                    dumps(comp.get("repos", [])),
                    comp.get("lastSeen", ""),
                    now,
                ),
            )

        self.broadcaster.publish("sessions", {"count": len(sessions)})
        self.broadcaster.publish("computers", {"count": len(computers)})
        return len(sessions)

    async def _extract_verdicts(self) -> None:
        """Fetch session details for completed activations and extract verdicts."""
        # Only fetch for activations with completed/idle status but no verdict yet
        activations = self.db.query(
            """
            SELECT id, factory_session_id FROM activations
            WHERE factory_session_id != ''
              AND verdict_json IN ('', '{}')
              AND status IN ('completed', 'idle', 'error_stopped', 'stopped')
            LIMIT 10
            """
        )
        for act in activations:
            try:
                session_data = await self.client.get_session(act["factory_session_id"])
                # Extract verdict from conversation or summary
                conversation = session_data.get("conversation", "")
                if isinstance(conversation, list):
                    # Join all messages
                    conversation = "\n".join(
                        msg.get("text", "") for msg in conversation if isinstance(msg, dict)
                    )
                verdict = _extract_verdict(conversation)
                if verdict:
                    self.db.execute(
                        "UPDATE activations SET verdict_json = ? WHERE id = ?",
                        (dumps(verdict), act["id"]),
                    )
            except Exception as exc:  # noqa: BLE001
                log.debug("Failed to extract verdict for activation %s: %s", act["id"], exc)

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self.refresh_once()
            except Exception as exc:  # noqa: BLE001
                log.warning("observability refresh failed: %s", exc)
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=self.settings.observability_interval_seconds
                )
            except TimeoutError:
                pass

    def start(self) -> None:
        if self._task is None:
            self._stop.clear()
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task
            self._task = None
