import asyncio
import logging
from datetime import UTC, datetime

from .compute import ComputeManager
from .config import Settings
from .connectors.base import Connector
from .db import Database
from .experts import get_expert
from .sse import Broadcaster
from .triggers import ActivationService, find_matching_triggers

log = logging.getLogger("droidland.poller")


class Poller:
    def __init__(
        self,
        db: Database,
        connectors: list[Connector],
        activations: ActivationService,
        compute: ComputeManager,
        broadcaster: Broadcaster,
        settings: Settings,
    ):
        self.db = db
        self.connectors = connectors
        self.activations = activations
        self.compute = compute
        self.broadcaster = broadcaster
        self.settings = settings
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def _cursor(self, source: str) -> str:
        row = self.db.query_one("SELECT cursor FROM connectors WHERE source = ?", (source,))
        return row["cursor"] if row else ""

    def _save_cursor(self, source: str, cursor: str, status: str) -> None:
        self.db.execute(
            """
            INSERT INTO connectors (source, cursor, last_polled_at, status)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
                cursor=excluded.cursor, last_polled_at=excluded.last_polled_at,
                status=excluded.status
            """,
            (source, cursor, datetime.now(UTC).isoformat(), status),
        )

    async def poll_once(self) -> int:
        """Run a single poll cycle across all connectors. Returns activations fired."""
        fired = 0
        for connector in self.connectors:
            try:
                events, cursor = await connector.poll(self._cursor(connector.source))
            except Exception as exc:  # noqa: BLE001
                log.warning("connector %s poll failed: %s", connector.source, exc)
                self._save_cursor(connector.source, self._cursor(connector.source), f"error: {exc}")
                continue

            for event in events:
                for trigger in find_matching_triggers(self.db, event):
                    expert = get_expert(self.db, trigger.expert_slug)
                    if expert is None:
                        log.warning("trigger %s references missing expert %s",
                                    trigger.id, trigger.expert_slug)
                        continue
                    try:
                        computer_id = await self.compute.ensure_computer(
                            trigger.target_repo or None
                        )
                        activation = await self.activations.activate(
                            trigger, expert, event, computer_id
                        )
                    except Exception as exc:  # noqa: BLE001
                        log.error("activation failed for trigger %s: %s", trigger.id, exc)
                        continue
                    if activation:
                        fired += 1
                        self.broadcaster.publish("activation", activation)
            self._save_cursor(connector.source, cursor, "ok")
        return fired

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self.poll_once()
            except Exception as exc:  # noqa: BLE001
                log.exception("poll cycle error: %s", exc)
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=self.settings.poll_interval_seconds
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
