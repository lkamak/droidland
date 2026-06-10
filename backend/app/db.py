import json
import sqlite3
import threading
from collections.abc import Iterable
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS experts (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    model TEXT DEFAULT '',
    autonomy TEXT DEFAULT 'off',
    interaction_mode TEXT DEFAULT 'auto',
    skills_json TEXT DEFAULT '[]',
    integrations_json TEXT DEFAULT '[]',
    run_in_worktree INTEGER DEFAULT 0,
    prompt TEXT DEFAULT '',
    file_path TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS triggers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    event_type TEXT NOT NULL,
    condition_json TEXT DEFAULT '{}',
    expert_slug TEXT NOT NULL,
    target_repo TEXT DEFAULT '',
    cwd TEXT DEFAULT '',
    prompt_template TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS connectors (
    source TEXT PRIMARY KEY,
    config_json TEXT DEFAULT '{}',
    cursor TEXT DEFAULT '',
    last_polled_at TEXT DEFAULT '',
    status TEXT DEFAULT 'idle'
);

CREATE TABLE IF NOT EXISTS activations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger_id INTEGER,
    expert_slug TEXT NOT NULL,
    external_ref TEXT NOT NULL,
    factory_session_id TEXT DEFAULT '',
    app_url TEXT DEFAULT '',
    status TEXT DEFAULT 'created',
    created_at TEXT DEFAULT '',
    UNIQUE (trigger_id, external_ref)
);

CREATE TABLE IF NOT EXISTS computers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    factory_computer_id TEXT NOT NULL,
    target_repo TEXT DEFAULT '',
    status TEXT DEFAULT 'unknown',
    UNIQUE (factory_computer_id)
);

CREATE TABLE IF NOT EXISTS session_cache (
    factory_session_id TEXT PRIMARY KEY,
    expert_slug TEXT DEFAULT '',
    status TEXT DEFAULT '',
    tokens_json TEXT DEFAULT '{}',
    app_url TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self.init_schema()

    def init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            self._conn.commit()
            return cur

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            return [dict(row) for row in cur.fetchall()]

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"))


def loads(value: str | None, default: Any = None) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default
