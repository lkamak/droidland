from .config import Settings
from .db import Database
from .factory_client import FactoryClient


class ComputeManager:
    """Maintains one persistent shared Droid Computer per target repo."""

    def __init__(self, db: Database, client: FactoryClient, settings: Settings):
        self.db = db
        self.client = client
        self.settings = settings

    def cached_computer_id(self, target_repo: str) -> str | None:
        row = self.db.query_one(
            "SELECT factory_computer_id FROM computers WHERE target_repo = ? AND status != 'error' "
            "ORDER BY id DESC LIMIT 1",
            (target_repo,),
        )
        return row["factory_computer_id"] if row else None

    def _remember(self, computer_id: str, target_repo: str, status: str) -> None:
        self.db.execute(
            """
            INSERT INTO computers (factory_computer_id, target_repo, status)
            VALUES (?, ?, ?)
            ON CONFLICT(factory_computer_id) DO UPDATE SET status=excluded.status
            """,
            (computer_id, target_repo, status),
        )

    async def ensure_computer(self, target_repo: str | None = None) -> str:
        target_repo = target_repo or self.settings.target_repo
        existing = self.cached_computer_id(target_repo)
        if existing:
            return existing
        repos = [target_repo] if target_repo else []
        result = await self.client.create_computer(
            name=f"droidland-{abs(hash(target_repo)) % 100000}", repos=repos
        )
        computer_id = result["id"]
        self._remember(computer_id, target_repo, result.get("status", "provisioning"))
        return computer_id

    async def refresh_status(self, computer_id: str) -> str:
        info = await self.client.get_computer(computer_id)
        status = info.get("status", "unknown")
        self.db.execute(
            "UPDATE computers SET status = ? WHERE factory_computer_id = ?", (status, computer_id)
        )
        return status
