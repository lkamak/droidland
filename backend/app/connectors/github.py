import httpx

from ..models import NormalizedEvent

_API = "https://api.github.com"


class GitHubConnector:
    """Detects pull-request activity by polling the GitHub REST API (read-only)."""

    source = "github"

    def __init__(self, token: str, repo: str):
        self.token = token
        self.repo = repo  # "owner/name"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def poll(self, cursor: str) -> tuple[list[NormalizedEvent], str]:
        url = f"{_API}/repos/{self.repo}/pulls"
        params = {"state": "open", "sort": "updated", "direction": "desc", "per_page": "50"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params, headers=self._headers())
        resp.raise_for_status()
        pulls = resp.json()

        events: list[NormalizedEvent] = []
        new_cursor = cursor
        for pr in pulls:
            updated = pr.get("updated_at", "")
            if cursor and updated <= cursor:
                continue
            number = pr.get("number")
            action = "opened" if pr.get("created_at") == updated else "synchronize"
            events.append(
                NormalizedEvent(
                    source=self.source,
                    event_type="pull_request",
                    external_ref=f"{self.repo}#{number}",
                    title=pr.get("title", ""),
                    url=pr.get("html_url", ""),
                    updated_at=updated,
                    payload={
                        "action": action,
                        "number": number,
                        "repo": self.repo,
                        "title": pr.get("title", ""),
                        "url": pr.get("html_url", ""),
                        "draft": pr.get("draft", False),
                        "author": (pr.get("user") or {}).get("login", ""),
                        "base": (pr.get("base") or {}).get("ref", ""),
                        "head": (pr.get("head") or {}).get("ref", ""),
                    },
                )
            )
            if updated > new_cursor:
                new_cursor = updated
        return events, new_cursor
