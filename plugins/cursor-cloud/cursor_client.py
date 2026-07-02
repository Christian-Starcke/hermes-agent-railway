"""HTTP client for Cursor Cloud Agents API v1."""

from __future__ import annotations

import os
import time
from typing import Any
from urllib.parse import quote

import httpx

BASE_URL = "https://api.cursor.com"
DEFAULT_TIMEOUT = 60.0
MAX_RETRIES = 4


class CursorAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class CursorClient:
    def __init__(self, api_key: str | None = None, *, timeout: float = DEFAULT_TIMEOUT):
        key = (api_key or os.environ.get("CURSOR_API_KEY") or "").strip()
        if not key:
            raise CursorAPIError("CURSOR_API_KEY is not configured")
        self._api_key = key
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{BASE_URL}{path}"
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.request(
                        method,
                        url,
                        headers=self._headers(),
                        params=params,
                        json=json_body,
                    )
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt + 1 >= MAX_RETRIES:
                    raise CursorAPIError(f"Cursor API request failed: {exc}") from exc
                time.sleep(2**attempt)
                continue

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "0") or 0)
                time.sleep(max(retry_after, 2**attempt))
                continue

            if response.status_code >= 400:
                body: Any
                try:
                    body = response.json()
                except Exception:
                    body = response.text
                raise CursorAPIError(
                    f"Cursor API {method} {path} failed ({response.status_code})",
                    status_code=response.status_code,
                    body=body,
                )

            if response.status_code == 204 or not response.content:
                return {}
            return response.json()

        raise CursorAPIError(f"Cursor API request failed after retries: {last_error}")

    def list_repositories(self) -> Any:
        return self._request("GET", "/v1/repositories")

    def list_models(self) -> Any:
        return self._request("GET", "/v1/models")

    def get_account(self) -> Any:
        return self._request("GET", "/v1/me")

    def list_agents(self, *, limit: int = 20, cursor: str | None = None) -> Any:
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/v1/agents", params=params)

    def get_agent(self, agent_id: str) -> Any:
        return self._request("GET", f"/v1/agents/{quote(agent_id, safe='')}")

    def create_agent(
        self,
        *,
        prompt_text: str,
        repository_url: str,
        starting_ref: str = "main",
        auto_create_pr: bool = True,
        model_id: str | None = None,
        name: str | None = None,
        mode: str = "agent",
        webhook_url: str | None = None,
        webhook_secret: str | None = None,
    ) -> Any:
        if webhook_url and webhook_secret:
            return self.create_agent_v0(
                prompt_text=prompt_text,
                repository_url=repository_url,
                starting_ref=starting_ref,
                auto_create_pr=auto_create_pr,
                webhook_url=webhook_url,
                webhook_secret=webhook_secret,
                model_id=model_id,
            )

        body: dict[str, Any] = {
            "prompt": {"text": prompt_text},
            "repos": [{"url": repository_url, "startingRef": starting_ref}],
            "autoCreatePR": auto_create_pr,
            "mode": mode,
        }
        if model_id:
            body["model"] = {"id": model_id}
        if name:
            body["name"] = name[:100]
        return self._request("POST", "/v1/agents", json_body=body)

    def create_agent_v0(
        self,
        *,
        prompt_text: str,
        repository_url: str,
        starting_ref: str = "main",
        auto_create_pr: bool = True,
        webhook_url: str,
        webhook_secret: str,
        model_id: str | None = None,
    ) -> Any:
        """Legacy v0 launch path — supports webhooks until v1 webhooks ship."""
        body: dict[str, Any] = {
            "prompt": {"text": prompt_text},
            "source": {"repository": repository_url, "ref": starting_ref},
            "target": {"autoCreatePr": auto_create_pr},
            "webhook": {"url": webhook_url, "secret": webhook_secret},
        }
        if model_id:
            body["model"] = model_id
        raw = self._request("POST", "/v0/agents", json_body=body)
        agent_id = raw.get("id")
        return {
            "agent": {
                "id": agent_id,
                "name": raw.get("name"),
                "status": raw.get("status"),
                "url": raw.get("target", {}).get("url") if isinstance(raw.get("target"), dict) else None,
                "latestRunId": raw.get("latestRunId"),
            },
            "run": {
                "id": raw.get("latestRunId"),
                "agentId": agent_id,
                "status": raw.get("status"),
            },
            "raw_v0": raw,
        }

    def create_run(self, agent_id: str, *, prompt_text: str, mode: str | None = None) -> Any:
        body: dict[str, Any] = {"prompt": {"text": prompt_text}}
        if mode:
            body["mode"] = mode
        return self._request(
            "POST",
            f"/v1/agents/{quote(agent_id, safe='')}/runs",
            json_body=body,
        )

    def get_run(self, agent_id: str, run_id: str) -> Any:
        return self._request(
            "GET",
            f"/v1/agents/{quote(agent_id, safe='')}/runs/{quote(run_id, safe='')}",
        )

    def cancel_run(self, agent_id: str, run_id: str) -> Any:
        return self._request(
            "POST",
            f"/v1/agents/{quote(agent_id, safe='')}/runs/{quote(run_id, safe='')}/cancel",
        )

    def archive_agent(self, agent_id: str) -> Any:
        return self._request("POST", f"/v1/agents/{quote(agent_id, safe='')}/archive")

    @staticmethod
    def normalize_repository(repository: str) -> str:
        repo = repository.strip()
        if repo.startswith("http://") or repo.startswith("https://"):
            return repo.rstrip("/")
        if "/" in repo:
            return f"https://github.com/{repo.lstrip('/')}"
        raise CursorAPIError(f"Invalid repository identifier: {repository}")

    @staticmethod
    def map_run_status(run_status: str | None) -> str:
        status = (run_status or "").upper()
        if status in {"CREATING", "RUNNING"}:
            return "running"
        if status in {"FINISHED", "COMPLETED", "SUCCEEDED", "DONE"}:
            return "finished"
        if status in {"ERROR", "EXPIRED", "FAILED"}:
            return "error"
        if status in {"CANCELLED", "CANCELED"}:
            return "cancelled"
        return "pending"

    @staticmethod
    def extract_run_git(run: dict[str, Any]) -> tuple[str | None, str | None]:
        branch = run.get("branchName")
        pr_url = run.get("prUrl")
        if branch or pr_url:
            return branch, pr_url
        git = run.get("git") or {}
        branches = git.get("branches") or []
        if not branches:
            return None, None
        first = branches[0] if isinstance(branches[0], dict) else {}
        return first.get("branch"), first.get("prUrl")
