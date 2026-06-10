import httpx

from ..models import NormalizedEvent

_API = "https://api.linear.app/graphql"

# Linear relative-time durations are relative to now; a NEGATIVE ISO-8601 duration
# looks back in time. "P1Y" would mean one year in the FUTURE and match nothing.
_DEFAULT_LOOKBACK = "-P1Y"

_QUERY = """
query Issues($after: DateTimeOrDuration) {
  issues(
    first: 50
    filter: { updatedAt: { gt: $after } }
    orderBy: updatedAt
  ) {
    nodes {
      id
      identifier
      title
      url
      updatedAt
      state { name }
      labels { nodes { name } }
    }
  }
}
"""


class LinearConnector:
    """Detects Linear issue activity (e.g. label changes) by polling the GraphQL API."""

    source = "linear"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {"Authorization": self.api_key, "Content-Type": "application/json"}

    async def poll(self, cursor: str) -> tuple[list[NormalizedEvent], str]:
        variables = {"after": cursor or _DEFAULT_LOOKBACK}  # look back when no cursor yet
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                _API, json={"query": _QUERY, "variables": variables}, headers=self._headers()
            )
        resp.raise_for_status()
        data = resp.json()
        nodes = (((data.get("data") or {}).get("issues") or {}).get("nodes")) or []

        events: list[NormalizedEvent] = []
        new_cursor = cursor
        for issue in nodes:
            updated = issue.get("updatedAt", "")
            if cursor and updated <= cursor:
                continue
            labels = [n["name"] for n in (issue.get("labels") or {}).get("nodes", [])]
            events.append(
                NormalizedEvent(
                    source=self.source,
                    event_type="issue",
                    external_ref=issue.get("id", ""),
                    title=issue.get("title", ""),
                    url=issue.get("url", ""),
                    updated_at=updated,
                    payload={
                        "identifier": issue.get("identifier", ""),
                        "title": issue.get("title", ""),
                        "url": issue.get("url", ""),
                        "state": (issue.get("state") or {}).get("name", ""),
                        "labels": labels,
                    },
                )
            )
            if updated > new_cursor:
                new_cursor = updated
        return events, new_cursor
