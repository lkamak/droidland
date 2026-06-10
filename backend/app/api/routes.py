import asyncio
import json
import re
from datetime import UTC, datetime
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


def _save_expert_or_409(c: AppContext, expert: Expert) -> Expert:
    try:
        return save_expert(c.db, c.settings.experts_dir, expert)
    except OSError as exc:
        raise HTTPException(
            500,
            f"cannot write persona to '{c.settings.experts_dir}': {exc.strerror or exc}. "
            "The experts directory must be writable (in Docker, mount it without ':ro').",
        ) from exc


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
    expert = _save_expert_or_409(c, Expert(**payload.model_dump()))
    return expert.model_dump()


@router.put("/experts/{slug}")
async def experts_update(request: Request, slug: str, payload: ExpertBody) -> dict[str, Any]:
    c = ctx(request)
    if get_expert(c.db, slug) is None:
        raise HTTPException(404, "expert not found")
    _validate_expert_fields(slug, payload.autonomy, payload.interaction_mode)
    expert = _save_expert_or_409(c, Expert(slug=slug, **payload.model_dump()))
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
async def activations_list(
    request: Request,
    expert: str | None = None,
    source: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    filters = []
    params = []
    if expert:
        filters.append("expert_slug = ?")
        params.append(expert)
    if source:
        filters.append("source = ?")
        params.append(source)
    if status:
        filters.append("status = ?")
        params.append(status)
    if date_from:
        filters.append("created_at >= ?")
        params.append(date_from)
    if date_to:
        filters.append("created_at <= ?")
        params.append(date_to)

    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    sql = f"SELECT * FROM activations {where} ORDER BY id DESC"
    return ctx(request).db.query(sql, params)


@router.post("/activations/{activation_id}/rerun")
async def activations_rerun(request: Request, activation_id: int) -> dict[str, Any]:
    """Re-run an activation by creating a new one with the same trigger and external ref."""
    c = ctx(request)
    
    # Fetch the original activation
    activation = c.db.query_one("SELECT * FROM activations WHERE id = ?", (activation_id,))
    if activation is None:
        raise HTTPException(404, "activation not found")
    
    trigger_id = activation.get("trigger_id")
    if trigger_id is None:
        raise HTTPException(400, "activation has no associated trigger")
    
    # Fetch the trigger
    trigger_row = c.db.query_one("SELECT * FROM triggers WHERE id = ?", (trigger_id,))
    if trigger_row is None:
        raise HTTPException(404, "trigger not found")
    trigger = row_to_trigger(trigger_row)
    
    # Fetch the expert
    expert = get_expert(c.db, trigger.expert_slug)
    if expert is None:
        raise HTTPException(400, "trigger references missing expert")
    
    # Create a new external ref with timestamp to avoid dedupe
    original_ref = activation["external_ref"]
    rerun_ref = f"{original_ref}-rerun-{int(datetime.now(UTC).timestamp())}"
    
    # Create normalized event for re-run
    norm = NormalizedEvent(
        source=activation.get("source", trigger.source),
        event_type=trigger.event_type,
        external_ref=rerun_ref,
        title=f"Re-run of {original_ref}",
        url=activation.get("app_url", ""),
        payload={"original_ref": original_ref, "rerun": True},
    )
    
    # Ensure computer exists
    computer_id = await c.compute.ensure_computer(trigger.target_repo or None)
    
    # Create new activation
    new_activation = await c.activations.activate(trigger, expert, norm, computer_id)
    if new_activation is None:
        raise HTTPException(409, "failed to create re-run activation")
    
    c.broadcaster.publish("activation", new_activation)
    return new_activation


@router.get("/sessions")
async def sessions_list(request: Request) -> list[dict[str, Any]]:
    return ctx(request).db.query("SELECT * FROM session_cache ORDER BY updated_at DESC")


@router.get("/computers")
async def computers_list(request: Request) -> list[dict[str, Any]]:
    return ctx(request).db.query("SELECT * FROM computers ORDER BY id DESC")


@router.get("/usage")
async def usage_summary(request: Request) -> dict[str, Any]:
    """Roll up token and credit usage across active sessions."""
    sessions = ctx(request).db.query("SELECT * FROM session_cache")
    total_input = 0
    total_output = 0
    total_credits = 0.0
    active_count = 0
    stale_count = 0
    errored_count = 0

    now = datetime.now(UTC)
    for s in sessions:
        tokens = json.loads(s.get("tokens_json") or "{}")
        total_input += tokens.get("inputTokens", 0)
        total_output += tokens.get("outputTokens", 0)
        total_credits += tokens.get("totalCreditsUsed", 0.0)

        status = s.get("status", "")
        if status.startswith("error"):
            errored_count += 1
        elif status in ("running", "pending"):
            active_count += 1

        # Flag stale: updated more than 5 minutes ago and still running
        updated = s.get("updated_at", "")
        if updated and status in ("running", "pending"):
            try:
                last_update = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                if (now - last_update).total_seconds() > 300:
                    stale_count += 1
            except (ValueError, TypeError):
                pass

    return {
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_credits": round(total_credits, 2),
        "total_sessions": len(sessions),
        "active_sessions": active_count,
        "stale_sessions": stale_count,
        "errored_sessions": errored_count,
    }


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
