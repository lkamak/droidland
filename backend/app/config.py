from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DROIDLAND_", env_file=".env", extra="ignore")

    # Factory
    factory_api_key: str = ""
    factory_api_base: str = "https://api.factory.ai"
    factory_app_base: str = "https://app.factory.ai"
    factory_session_url_template: str = "{app_base}/session/{session_id}"

    # Detection connectors (read-only)
    github_token: str = ""
    linear_api_key: str = ""

    # Storage / experts
    db_path: str = str(_REPO_ROOT / "droidland.db")
    experts_dir: str = str(_REPO_ROOT / ".factory" / "droids")

    # Compute target (dogfooding default = this repo)
    target_repo: str = ""

    # Polling
    poll_interval_seconds: int = 30
    observability_interval_seconds: int = 15
    default_model: str = "claude-sonnet-4-5-20250929"

    @property
    def factory_enabled(self) -> bool:
        return bool(self.factory_api_key)

    def session_app_url(self, session_id: str) -> str:
        return self.factory_session_url_template.format(
            app_base=self.factory_app_base.rstrip("/"), session_id=session_id
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
