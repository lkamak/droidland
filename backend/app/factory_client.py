from typing import Any

import httpx


class FactoryError(RuntimeError):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(f"Factory API error {status}: {detail}")


class FactoryClient:
    """Async client for the Factory public API (Computers + Sessions)."""

    def __init__(self, api_key: str, base_url: str = "https://api.factory.ai"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        async with self._client() as client:
            resp = await client.request(method, path, **kwargs)
        if resp.status_code >= 400:
            detail = ""
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise FactoryError(resp.status_code, detail)
        if resp.content:
            return resp.json()
        return {}

    # --- Computers ---
    async def create_computer(
        self, name: str, repos: list[str], provider: str = "e2b", auto_install_deps: bool = True
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": name,
            "provider": provider,
            "autoInstallDeps": auto_install_deps,
        }
        if repos:
            body["repos"] = repos
        return await self._request("POST", "/api/v0/computers", json=body)

    async def get_computer(self, computer_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/v0/computers/{computer_id}")

    async def list_computers(self) -> dict[str, Any]:
        return await self._request("GET", "/api/v0/computers")

    # --- Sessions ---
    async def create_session(
        self, computer_id: str, cwd: str = "", settings: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"computerId": computer_id}
        if cwd:
            body["cwd"] = cwd
        if settings:
            body["sessionSettings"] = settings
        return await self._request("POST", "/api/v0/sessions", json=body)

    async def post_message(self, session_id: str, text: str) -> dict[str, Any]:
        return await self._request(
            "POST", f"/api/v0/sessions/{session_id}/messages", json={"text": text}
        )

    async def get_session(self, session_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/v0/sessions/{session_id}")

    async def list_sessions(
        self, computer_id: str | None = None, limit: int = 50, cursor: str | None = None
    ) -> dict[str, Any]:
        # The API has no tag filter; callers filter by the session `tags` array client-side.
        params: dict[str, Any] = {"limit": str(limit)}
        if computer_id:
            params["computerId"] = computer_id
        if cursor:
            params["cursor"] = cursor
        return await self._request("GET", "/api/v0/sessions", params=params)

    async def interrupt_session(self, session_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/api/v0/sessions/{session_id}/interrupt")
