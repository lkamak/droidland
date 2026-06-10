import re
from datetime import UTC, datetime
from typing import Any

from .config import Settings
from .db import Database, dumps, loads
from .factory_client import FactoryClient
from .models import Expert, NormalizedEvent, Trigger

_TEMPLATE_RE = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def match_condition(condition: dict[str, Any], event: NormalizedEvent) -> bool:
    """A trigger matches when every condition key matches the event payload.

    List-valued payload fields match by membership (e.g. label in labels);
    scalar fields match by equality.
    """
    if not condition:
        return True
    for key, expected in condition.items():
        actual = event.payload.get(key)
        if isinstance(actual, list):
            if expected not in actual:
                return False
        elif actual != expected:
            return False
    return True


def row_to_trigger(row: dict[str, Any]) -> Trigger:
    return Trigger(
        id=row["id"],
        source=row["source"],
        event_type=row["event_type"],
        condition=loads(row.get("condition_json"), {}),
        expert_slug=row["expert_slug"],
        target_repo=row.get("target_repo", ""),
        cwd=row.get("cwd", ""),
        prompt_template=row.get("prompt_template", ""),
        enabled=bool(row.get("enabled", 1)),
    )


def find_matching_triggers(db: Database, event: NormalizedEvent) -> list[Trigger]:
    rows = db.query(
        "SELECT * FROM triggers WHERE enabled = 1 AND source = ? AND event_type = ?",
        (event.source, event.event_type),
    )
    triggers = [row_to_trigger(r) for r in rows]
    return [t for t in triggers if match_condition(t.condition, event)]


def render_template(template: str, event: NormalizedEvent) -> str:
    context: dict[str, Any] = {
        **event.payload,
        "title": event.title,
        "url": event.url,
        "external_ref": event.external_ref,
        "source": event.source,
    }

    def _sub(m: re.Match[str]) -> str:
        return str(context.get(m.group(1), m.group(0)))

    return _TEMPLATE_RE.sub(_sub, template)


class ActivationService:
    def __init__(self, db: Database, client: FactoryClient, settings: Settings):
        self.db = db
        self.client = client
        self.settings = settings

    def _claim(self, trigger: Trigger, event: NormalizedEvent) -> int | None:
        """Atomically reserve an activation. Returns its id, or None if duplicate."""
        cur = self.db.execute(
            """
            INSERT OR IGNORE INTO activations
                (trigger_id, expert_slug, external_ref, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
            """,
            (trigger.id, trigger.expert_slug, event.external_ref,
             datetime.now(UTC).isoformat()),
        )
        if cur.rowcount == 0:
            return None
        return cur.lastrowid

    async def activate(
        self, trigger: Trigger, expert: Expert, event: NormalizedEvent, computer_id: str
    ) -> dict[str, Any] | None:
        activation_id = self._claim(trigger, event)
        if activation_id is None:
            return None

        settings = {
            "model": expert.model or self.settings.default_model,
            "autonomyLevel": expert.autonomy,
            "interactionMode": expert.interaction_mode,
            "runInWorktree": expert.run_in_worktree,
            "tags": [
                {"name": "droidland", "metadata": {"ref": event.external_ref}},
                {"name": f"expert:{expert.slug}"},
                {"name": f"trigger:{trigger.id}"},
            ],
        }
        if expert.skills:
            settings["enabledToolIds"] = expert.skills

        try:
            session = await self.client.create_session(
                computer_id=computer_id, cwd=trigger.cwd, settings=settings
            )
            session_id = session["sessionId"]
            text = expert.prompt + "\n\n---\n\n" + render_template(trigger.prompt_template, event)
            await self.client.post_message(session_id, text)
        except Exception as exc:  # noqa: BLE001
            self.db.execute(
                "UPDATE activations SET status = ? WHERE id = ?", (f"error: {exc}", activation_id)
            )
            raise

        app_url = self.settings.session_app_url(session_id)
        self.db.execute(
            "UPDATE activations SET factory_session_id = ?, app_url = ?, status = 'running' "
            "WHERE id = ?",
            (session_id, app_url, activation_id),
        )
        self.db.execute(
            """
            INSERT INTO session_cache (factory_session_id, expert_slug, status, app_url, updated_at)
            VALUES (?, ?, 'running', ?, ?)
            ON CONFLICT(factory_session_id) DO UPDATE SET
                expert_slug=excluded.expert_slug, status=excluded.status,
                app_url=excluded.app_url, updated_at=excluded.updated_at
            """,
            (session_id, expert.slug, app_url, datetime.now(UTC).isoformat()),
        )
        return {
            "id": activation_id,
            "trigger_id": trigger.id,
            "expert_slug": expert.slug,
            "external_ref": event.external_ref,
            "factory_session_id": session_id,
            "app_url": app_url,
            "status": "running",
        }


def upsert_trigger(db: Database, t: dict[str, Any], trigger_id: int | None = None) -> int:
    if trigger_id is None:
        cur = db.execute(
            """
            INSERT INTO triggers
                (source, event_type, condition_json, expert_slug, target_repo, cwd,
                 prompt_template, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (t["source"], t["event_type"], dumps(t.get("condition", {})), t["expert_slug"],
             t.get("target_repo", ""), t.get("cwd", ""), t.get("prompt_template", ""),
             int(t.get("enabled", True))),
        )
        return cur.lastrowid
    db.execute(
        """
        UPDATE triggers SET source=?, event_type=?, condition_json=?, expert_slug=?,
            target_repo=?, cwd=?, prompt_template=?, enabled=? WHERE id=?
        """,
        (t["source"], t["event_type"], dumps(t.get("condition", {})), t["expert_slug"],
         t.get("target_repo", ""), t.get("cwd", ""), t.get("prompt_template", ""),
         int(t.get("enabled", True)), trigger_id),
    )
    return trigger_id
