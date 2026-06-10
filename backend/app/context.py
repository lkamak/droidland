from dataclasses import dataclass

from .compute import ComputeManager
from .config import Settings, get_settings
from .connectors import GitHubConnector, LinearConnector
from .connectors.base import Connector
from .db import Database
from .experts import sync_experts
from .factory_client import FactoryClient
from .observability import Observability
from .poller import Poller
from .sse import Broadcaster
from .triggers import ActivationService, seed_default_triggers


@dataclass
class AppContext:
    settings: Settings
    db: Database
    client: FactoryClient
    broadcaster: Broadcaster
    compute: ComputeManager
    activations: ActivationService
    poller: Poller
    observability: Observability


def build_connectors(settings: Settings) -> list[Connector]:
    connectors: list[Connector] = []
    if settings.github_token and settings.target_repo:
        repo = settings.target_repo
        if repo.startswith("http") or repo.endswith(".git"):
            repo = repo.rstrip("/").removesuffix(".git").split("/", 3)[-1]
        connectors.append(GitHubConnector(settings.github_token, repo))
    if settings.linear_api_key:
        connectors.append(LinearConnector(settings.linear_api_key))
    return connectors


def build_context(
    settings: Settings | None = None,
    db: Database | None = None,
    client: FactoryClient | None = None,
    connectors: list[Connector] | None = None,
) -> AppContext:
    settings = settings or get_settings()
    db = db or Database(settings.db_path)
    client = client or FactoryClient(settings.factory_api_key, settings.factory_api_base)
    broadcaster = Broadcaster()
    compute = ComputeManager(db, client, settings)
    activations = ActivationService(db, client, settings)
    connectors = connectors if connectors is not None else build_connectors(settings)

    sync_experts(db, settings.experts_dir)
    seed_default_triggers(db)

    poller = Poller(db, connectors, activations, compute, broadcaster, settings)
    observability = Observability(db, client, broadcaster, settings)
    return AppContext(
        settings=settings,
        db=db,
        client=client,
        broadcaster=broadcaster,
        compute=compute,
        activations=activations,
        poller=poller,
        observability=observability,
    )
