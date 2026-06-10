from typing import Protocol

from ..models import NormalizedEvent


class Connector(Protocol):
    source: str

    async def poll(self, cursor: str) -> tuple[list[NormalizedEvent], str]:
        """Return new events since `cursor` and the updated cursor."""
        ...
