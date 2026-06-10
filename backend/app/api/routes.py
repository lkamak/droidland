import asyncio
import json
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from ..context import AppContext
from ..experts import delete_expert, get_expert, list_experts, save_expert
from ..models import (
    AUTONOMY_LEVELS,
    INTERACTION_MODES,
    Expert,
    ExpertBody,
    ExpertIn,
    NormalizedEvent,
    TriggerIn,
)
from ..triggers import row_to_trigger, upsert_trigger

router = APIRouter(prefix="/api")

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def _validate_expert_fields(slug: str, autonomy: str, interaction_mode: str) -> None:
    if not SLUG_RE.match(slug):
        raise HTTPException(400, "slug must be lowercase alphanumeric with dashes")
    if autonomy not in AUTONOMY_LEVELS:
        raise HTTPException(400, f"autonomy must be one of {sorted(AUTONOMY_LEVELS)}")
    if interaction_mode not in INTERACTION_MODES:
        raise HTTPException(400, f"interaction_mode must be one of {sorted(INTERACTION_MODES)}")


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    c = ctx(request)
    return {
        "status": "ok",
        "factory_configured": c.settings.factory_enabled,
        "target_repo": c.settings.target_repo,
        "connectors": [conn.source for conn in c.poller.connectors],
    }


# --- Experts ---
@router.get("/experts")
async def experts_list(request: Request) -> list[dict[str, Any]]:
    return [e.model_dump() for e in list_experts(ctx(request).db)]


@router.get("/experts/{slug}")
async def experts_get(request: Request, slug: str) -> dict[str, Any]:
    expert = get_expert(ctx(request).db, slug)
    if expert is None:
        raise HTTPException(404, "expert not found")
    return expert.model_dump()


@router.post("/experts")
async def experts_create(request: Request, payload: ExpertIn) -> dict[str, Any]:
    c = ctx(request)
    _validate_expert_fields(payload.slug, payload.autonomy, payload.interaction_mode)
    if get_expert(c.db, payload.slug) is not None:
        raise HTTPException(409, f"expert '{payload.slug}' already exists")
    expert = save_expert(c.db, c.settings.experts_dir, Expert(**payload.model_dump()))
    return expert.model_dump()


@router.put("/experts/{slug}")
async def experts_update(request: Request, slug: str, payload: ExpertBody) -> dict[str, Any]:
    c = ctx(request)
    if get_expert(c.db, slug) is None:
        raise HTTPException(404, "expert not found")
    _validate_expert_fields(slug, payload.autonomy, payload.interaction_mode)
    expert = save_expert(c.db, c.settings.experts_dir, Expert(slug=slug, **payload.model_dump()))
    return expert.model_dump()


@router.delete("/experts/{slug}")
async def experts_delete(request: Request, slug: str) -> dict[str, Any]:
    c = ctx(request)
    if not delete_expert(c.db, c.settings.experts_dir, slug):
        raise HTTPException(404, "expert not found")
    return {"deleted": slug}


@router.post("/experts/validate")
async def experts_validate(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
    skills = payload.get("skills", []) or []
    integrations = payload.get("integrations", []) or []
    slug = payload.get("slug", "")
    warnings: list[str] = []
    errors: list[str] = []
    if slug and not SLUG_RE.match(slug):
        errors.append("slug must be lowercase alphanumeric with dashes")
    if payload.get("autonomy", "off") not in AUTONOMY_LEVELS:
        errors.append("invalid autonomy")
    if payload.get("interaction_mode", "auto") not in INTERACTION_MODES:
        errors.append("invalid interaction_mode")
    if integrations and not skills:
        warnings.append("declares integrations but no skills/tools")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "declared_skills": skills,
        "declared_integrations": integrations,
    }


# --- Triggers ---
@router.get("/triggers")
async def triggers_list(request: Request) -> list[dict[str, Any]]:
    rows = ctx(request).db.query("SELECT * FROM triggers ORDER BY id")
    return [row_to_trigger(r).model_dump() for r in rows]


@router.post("/triggers")
async def triggers_create(request: Request, payload: TriggerIn) -> dict[str, Any]:
    c = ctx(request)
    if get_expert(c.db, payload.expert_slug) is None:
        raise HTTPException(400, f"unknown expert '{payload.expert_slug}'")
    trigger_id = upsert_trigger(c.db, payload.model_dump())
    return {"id": trigger_id}


@router.put("/triggers/{trigger_id}")
async def triggers_update(request: Request, trigger_id: int, payload: TriggerIn) -> dict[str, Any]:
    c = ctx(request)
    if c.db.query_one("SELECT id FROM triggers WHERE id = ?", (trigger_id,)) is None:
        raise HTTPException(404, "trigger not found")
    upsert_trigger(c.db, payload.model_dump(), trigger_id)
    return {"id": trigger_id}


@router.delete("/triggers/{trigger_id}")
async def triggers_delete(request: Request, trigger_id: int) -> dict[str, Any]:
    c = ctx(request)
    if c.db.query_one("SELECT id FROM triggers WHERE id = ?", (trigger_id,)) is None:
        raise HTTPException(404, "trigger not found")
    c.db.execute("DELETE FROM triggers WHERE id = ?", (trigger_id,))
    return {"deleted": trigger_id}


@router.post("/triggers/{trigger_id}/test")
async def triggers_test(request: Request, trigger_id: int, event: dict[str, Any]) -> dict[str, Any]:
    """Fire a trigger with a synthetic event payload (manual smoke test)."""
    c = ctx(request)
    row = c.db.query_one("SELECT * FROM triggers WHERE id = ?", (trigger_id,))
    if row is None:
        raise HTTPException(404, "trigger not found")
    trigger = row_to_trigger(row)
    expert = get_expert(c.db, trigger.expert_slug)
    if expert is None:
        raise HTTPException(400, "trigger references missing expert")
    norm = NormalizedEvent(
        source=trigger.source,
        event_type=trigger.event_type,
        external_ref=event.get("external_ref", f"test-{trigger_id}"),
        title=event.get("title", "test event"),
        url=event.get("url", ""),
        payload=event.get("payload", event),
    )
    computer_id = await c.compute.ensure_computer(trigger.target_repo or None)
    activation = await c.activations.activate(trigger, expert, norm, computer_id)
    if activation is None:
        raise HTTPException(409, "duplicate activation (already fired for this ref)")
    c.broadcaster.publish("activation", activation)
    return activation


# --- Connectors ---
@router.get("/connectors")
async def connectors_list(request: Request) -> list[dict[str, Any]]:
    return ctx(request).db.query("SELECT * FROM connectors")


@router.post("/connectors/poll")
async def connectors_poll(request: Request) -> dict[str, Any]:
    fired = await ctx(request).poller.poll_once()
    return {"activations_fired": fired}


# --- Activations & sessions (observability) ---
@router.get("/activations")
async def activations_list(request: Request) -> list[dict[str, Any]]:
    return ctx(request).db.query("SELECT * FROM activations ORDER BY id DESC")


@router.get("/sessions")
async def sessions_list(request: Request) -> list[dict[str, Any]]:
    return ctx(request).db.query("SELECT * FROM session_cache ORDER BY updated_at DESC")


@router.get("/computers")
async def computers_list(request: Request) -> list[dict[str, Any]]:
    return ctx(request).db.query("SELECT * FROM computers ORDER BY id DESC")


# --- SSE ---
@router.get("/stream")
async def stream(request: Request):
    broadcaster = ctx(request).broadcaster
    queue = broadcaster.subscribe()

    async def gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield {"event": event["type"], "data": json.dumps(event["data"])}
                except TimeoutError:
                    yield {"event": "ping", "data": "{}"}
        finally:
            broadcaster.unsubscribe(queue)

    return EventSourceResponse(gen())
