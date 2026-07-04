"""HTTP client for OpenCode server API."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

DEFAULT_TIMEOUT = 120.0
MAX_RETRIES = 3


class OpenCodeAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class OpenCodeClient:
    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        url = (base_url or os.environ.get("OPENCODE_SERVER_URL") or "").strip().rstrip("/")
        if not url:
            raise OpenCodeAPIError("OPENCODE_SERVER_URL is not configured")
        self._base_url = url
        self._username = (username or os.environ.get("OPENCODE_SERVER_USER") or "opencode").strip()
        self._password = (password or os.environ.get("OPENCODE_SERVER_PASSWORD") or "").strip()
        if not self._password:
            raise OpenCodeAPIError("OPENCODE_SERVER_PASSWORD is not configured")
        self._timeout = timeout

    def _auth(self) -> tuple[str, str]:
        return self._username, self._password

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        expect_json: bool = True,
    ) -> Any:
        url = f"{self._base_url}{path}"
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.request(
                        method,
                        url,
                        auth=self._auth(),
                        params=params,
                        json=json_body,
                        headers={"Accept": "application/json"},
                    )
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt + 1 >= MAX_RETRIES:
                    raise OpenCodeAPIError(f"OpenCode request failed: {exc}") from exc
                time.sleep(2**attempt)
                continue

            if response.status_code == 429:
                time.sleep(2**attempt)
                continue

            if response.status_code == 204:
                return None

            if response.status_code >= 400:
                body: Any
                try:
                    body = response.json()
                except Exception:
                    body = response.text
                raise OpenCodeAPIError(
                    f"OpenCode {method} {path} failed ({response.status_code})",
                    status_code=response.status_code,
                    body=body,
                )

            if not expect_json or not response.content:
                return None
            try:
                return response.json()
            except Exception:
                return response.text

        raise OpenCodeAPIError(f"OpenCode request failed after retries: {last_error}")

    def health(self) -> dict[str, Any]:
        data = self._request("GET", "/global/health")
        return data if isinstance(data, dict) else {"raw": data}

    def list_providers(self) -> dict[str, Any]:
        data = self._request("GET", "/config/providers")
        return data if isinstance(data, dict) else {"raw": data}

    def list_agents(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/agent")
        if isinstance(data, list):
            return data
        return []

    def create_session(self, *, title: str | None = None, parent_id: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if title:
            body["title"] = title
        if parent_id:
            body["parentID"] = parent_id
        data = self._request("POST", "/session", json_body=body)
        return data if isinstance(data, dict) else {}

    def get_session(self, session_id: str) -> dict[str, Any]:
        data = self._request("GET", f"/session/{session_id}")
        return data if isinstance(data, dict) else {}

    def session_status(self) -> dict[str, Any]:
        data = self._request("GET", "/session/status")
        return data if isinstance(data, dict) else {}

    def list_messages(self, session_id: str, *, limit: int | None = None) -> list[dict[str, Any]]:
        params = {"limit": limit} if limit else None
        data = self._request("GET", f"/session/{session_id}/message", params=params)
        if isinstance(data, list):
            return data
        return []

    def send_message(
        self,
        session_id: str,
        *,
        text: str,
        agent: str | None = None,
        model: dict[str, str] | None = None,
        system: str | None = None,
    ) -> dict[str, Any]:
        parts = [{"type": "text", "text": text}]
        body: dict[str, Any] = {"parts": parts}
        if agent:
            body["agent"] = agent
        if model:
            body["model"] = model
        if system:
            body["system"] = system
        data = self._request("POST", f"/session/{session_id}/message", json_body=body)
        return data if isinstance(data, dict) else {}

    def prompt_async(
        self,
        session_id: str,
        *,
        text: str,
        agent: str | None = None,
        model: dict[str, str] | None = None,
        system: str | None = None,
    ) -> None:
        parts = [{"type": "text", "text": text}]
        body: dict[str, Any] = {"parts": parts}
        if agent:
            body["agent"] = agent
        if model:
            body["model"] = model
        if system:
            body["system"] = system
        self._request("POST", f"/session/{session_id}/prompt_async", json_body=body, expect_json=False)

    def abort_session(self, session_id: str) -> bool:
        data = self._request("POST", f"/session/{session_id}/abort")
        return bool(data)

    @staticmethod
    def parse_model(model_id: str | None) -> dict[str, str] | None:
        if not model_id:
            return None
        raw = model_id.strip()
        if raw.startswith("openrouter/"):
            return {"providerID": "openrouter", "modelID": raw.removeprefix("openrouter/")}
        if "/" in raw:
            provider, name = raw.split("/", 1)
            return {"providerID": provider, "modelID": name}
        return {"providerID": "openrouter", "modelID": raw}

    @staticmethod
    def map_session_status(status: Any) -> str:
        if status is None:
            return "running"
        if isinstance(status, dict):
            state = str(status.get("type") or status.get("status") or "").lower()
        else:
            state = str(status).lower()
        if state in {"idle", "completed", "complete", "done", "finished"}:
            return "finished"
        if state in {"error", "failed", "failure"}:
            return "error"
        if state in {"aborted", "cancelled", "canceled"}:
            return "cancelled"
        if state in {"busy", "running", "working", "active"}:
            return "running"
        return "running"

    @staticmethod
    def extract_summary(messages: list[dict[str, Any]]) -> str | None:
        for item in reversed(messages):
            info = item.get("info") if isinstance(item, dict) else None
            parts = item.get("parts") if isinstance(item, dict) else None
            if isinstance(info, dict) and str(info.get("role", "")).lower() == "assistant":
                if isinstance(parts, list):
                    texts = [
                        str(part.get("text", ""))
                        for part in parts
                        if isinstance(part, dict) and part.get("type") == "text" and part.get("text")
                    ]
                    if texts:
                        return "\n".join(texts).strip()
        return None
