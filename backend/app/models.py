from typing import Any

from pydantic import BaseModel, Field

AUTONOMY_LEVELS = {"off", "low", "medium", "high"}
INTERACTION_MODES = {"auto", "spec", "agi", "mission"}


class ExpertBody(BaseModel):
    name: str
    description: str = ""
    model: str = ""
    autonomy: str = "off"
    interaction_mode: str = "auto"
    skills: list[str] = Field(default_factory=list)
    integrations: list[str] = Field(default_factory=list)
    run_in_worktree: bool = False
    prompt: str = ""


class ExpertIn(ExpertBody):
    slug: str


class Expert(ExpertIn):
    file_path: str = ""


class TriggerIn(BaseModel):
    source: str
    event_type: str
    condition: dict[str, Any] = Field(default_factory=dict)
    expert_slug: str
    target_repo: str = ""
    cwd: str = ""
    prompt_template: str = ""
    enabled: bool = True


class Trigger(TriggerIn):
    id: int


class NormalizedEvent(BaseModel):
    source: str
    event_type: str
    external_ref: str
    title: str = ""
    url: str = ""
    updated_at: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class Activation(BaseModel):
    id: int
    trigger_id: int | None
    expert_slug: str
    external_ref: str
    factory_session_id: str = ""
    app_url: str = ""
    status: str = "created"
    created_at: str = ""
    verdict: dict[str, Any] = Field(default_factory=dict)
    source: str = ""
