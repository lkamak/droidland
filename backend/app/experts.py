from pathlib import Path
from typing import Any

import yaml

from .db import Database, dumps, loads
from .models import AUTONOMY_LEVELS, INTERACTION_MODES, Expert

_FRONTMATTER_DELIM = "---"


def parse_expert_markdown(text: str, slug: str, file_path: str = "") -> Expert:
    """Parse a persona markdown file with optional leading YAML front-matter."""
    meta: dict[str, Any] = {}
    body = text
    stripped = text.lstrip()
    if stripped.startswith(_FRONTMATTER_DELIM):
        parts = stripped.split(_FRONTMATTER_DELIM, 2)
        if len(parts) == 3:
            meta = yaml.safe_load(parts[1]) or {}
            body = parts[2]
    if not isinstance(meta, dict):
        meta = {}

    autonomy = str(meta.get("autonomy", "off"))
    if autonomy not in AUTONOMY_LEVELS:
        autonomy = "off"
    mode = str(meta.get("interaction_mode", "auto"))
    if mode not in INTERACTION_MODES:
        mode = "auto"

    return Expert(
        slug=slug,
        name=str(meta.get("name", slug)),
        description=str(meta.get("description", "")),
        model=str(meta.get("model", "")),
        autonomy=autonomy,
        interaction_mode=mode,
        skills=list(meta.get("skills", []) or []),
        integrations=list(meta.get("integrations", []) or []),
        run_in_worktree=bool(meta.get("run_in_worktree", False)),
        prompt=body.strip(),
        file_path=file_path,
    )


def load_experts_from_dir(experts_dir: str) -> list[Expert]:
    directory = Path(experts_dir)
    if not directory.is_dir():
        return []
    experts: list[Expert] = []
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        experts.append(parse_expert_markdown(text, path.stem, str(path)))
    return experts


def expert_to_markdown(e: Expert) -> str:
    """Serialize an expert back to a persona markdown file with YAML front-matter."""
    meta = {
        "name": e.name,
        "description": e.description,
        "model": e.model,
        "autonomy": e.autonomy,
        "interaction_mode": e.interaction_mode,
        "skills": e.skills,
        "integrations": e.integrations,
        "run_in_worktree": e.run_in_worktree,
    }
    front = yaml.safe_dump(meta, sort_keys=False, default_flow_style=False, allow_unicode=True)
    return f"{_FRONTMATTER_DELIM}\n{front}{_FRONTMATTER_DELIM}\n\n{e.prompt.strip()}\n"


def _upsert_expert(db: Database, e: Expert) -> None:
    db.execute(
        """
        INSERT INTO experts
            (slug, name, description, model, autonomy, interaction_mode,
             skills_json, integrations_json, run_in_worktree, prompt, file_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET
            name=excluded.name, description=excluded.description, model=excluded.model,
            autonomy=excluded.autonomy, interaction_mode=excluded.interaction_mode,
            skills_json=excluded.skills_json, integrations_json=excluded.integrations_json,
            run_in_worktree=excluded.run_in_worktree, prompt=excluded.prompt,
            file_path=excluded.file_path
        """,
        (
            e.slug, e.name, e.description, e.model, e.autonomy, e.interaction_mode,
            dumps(e.skills), dumps(e.integrations), int(e.run_in_worktree),
            e.prompt, e.file_path,
        ),
    )


def sync_experts(db: Database, experts_dir: str) -> int:
    experts = load_experts_from_dir(experts_dir)
    for e in experts:
        _upsert_expert(db, e)
    return len(experts)


def save_expert(db: Database, experts_dir: str, expert: Expert) -> Expert:
    """Write the expert to `.factory/droids/<slug>.md` and upsert its DB row."""
    directory = Path(experts_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{expert.slug}.md"
    path.write_text(expert_to_markdown(expert), encoding="utf-8")
    expert = expert.model_copy(update={"file_path": str(path)})
    _upsert_expert(db, expert)
    return expert


def delete_expert(db: Database, experts_dir: str, slug: str) -> bool:
    if get_expert(db, slug) is None:
        return False
    path = Path(experts_dir) / f"{slug}.md"
    if path.exists():
        path.unlink()
    db.execute("DELETE FROM experts WHERE slug = ?", (slug,))
    return True


def row_to_expert(row: dict[str, Any]) -> Expert:
    return Expert(
        slug=row["slug"],
        name=row["name"],
        description=row.get("description", ""),
        model=row.get("model", ""),
        autonomy=row.get("autonomy", "off"),
        interaction_mode=row.get("interaction_mode", "auto"),
        skills=loads(row.get("skills_json"), []),
        integrations=loads(row.get("integrations_json"), []),
        run_in_worktree=bool(row.get("run_in_worktree", 0)),
        prompt=row.get("prompt", ""),
        file_path=row.get("file_path", ""),
    )


def list_experts(db: Database) -> list[Expert]:
    return [row_to_expert(r) for r in db.query("SELECT * FROM experts ORDER BY slug")]


def get_expert(db: Database, slug: str) -> Expert | None:
    row = db.query_one("SELECT * FROM experts WHERE slug = ?", (slug,))
    return row_to_expert(row) if row else None
