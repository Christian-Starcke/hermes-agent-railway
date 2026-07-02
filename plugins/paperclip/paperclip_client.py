"""HTTP client for Paperclip control-plane API."""

from __future__ import annotations

import os
import time
from typing import Any
from urllib.parse import urlencode

import httpx

DEFAULT_TIMEOUT = 60.0
MAX_RETRIES = 4


class PaperclipAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class PaperclipClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_token: str | None = None,
        company_id: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self._base_url = (base_url or os.environ.get("PAPERCLIP_BASE_URL") or "").strip().rstrip("/")
        self._api_token = (api_token or os.environ.get("PAPERCLIP_API_TOKEN") or "").strip()
        self._company_id = (company_id or os.environ.get("PAPERCLIP_COMPANY_ID") or "").strip()
        self._timeout = timeout
        if not self._base_url:
            raise PaperclipAPIError("PAPERCLIP_BASE_URL is not configured")
        if not self._api_token:
            raise PaperclipAPIError("PAPERCLIP_API_TOKEN is not configured")
        if not self._company_id:
            raise PaperclipAPIError("PAPERCLIP_COMPANY_ID is not configured")

    @property
    def company_id(self) -> str:
        return self._company_id

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_token}",
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
        if not path.startswith("/"):
            path = f"/{path}"
        url = f"{self._base_url}{path}"
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
                    raise PaperclipAPIError(f"Paperclip API request failed: {exc}") from exc
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
                raise PaperclipAPIError(
                    f"Paperclip API {method} {path} failed ({response.status_code})",
                    status_code=response.status_code,
                    body=body,
                )

            if response.status_code == 204 or not response.content:
                return None
            try:
                return response.json()
            except Exception:
                return response.text

        raise PaperclipAPIError(f"Paperclip API request failed: {last_error}")

    def health(self) -> Any:
        return self._request("GET", "/api/health")

    def list_agents(self) -> Any:
        return self._request("GET", f"/api/companies/{self._company_id}/agents")

    def create_issue(self, payload: dict[str, Any]) -> Any:
        return self._request(
            "POST",
            f"/api/companies/{self._company_id}/issues",
            json_body=payload,
        )

    def get_issue(self, issue_id: str) -> Any:
        return self._request("GET", f"/api/issues/{issue_id}")

    def update_issue(self, issue_id: str, payload: dict[str, Any]) -> Any:
        return self._request("PATCH", f"/api/issues/{issue_id}", json_body=payload)

    def list_issues(
        self,
        *,
        status: str | None = None,
        assignee_agent_id: str | None = None,
        limit: int | None = None,
        query: str | None = None,
    ) -> Any:
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        if assignee_agent_id:
            params["assigneeAgentId"] = assignee_agent_id
        if limit is not None:
            params["limit"] = limit
        if query:
            params["q"] = query
        qs = f"?{urlencode(params)}" if params else ""
        return self._request("GET", f"/api/companies/{self._company_id}/issues{qs}")

    @staticmethod
    def normalize_repository(repository: str) -> str:
        repo = repository.strip().rstrip("/")
        if repo.startswith("https://") or repo.startswith("http://"):
            return repo
        if "/" in repo:
            return f"https://github.com/{repo}"
        raise PaperclipAPIError(f"Invalid repository slug: {repository}")

    @staticmethod
    def repository_slug(repository: str) -> str:
        repo = PaperclipClient.normalize_repository(repository)
        if repo.startswith("https://github.com/"):
            return repo.removeprefix("https://github.com/").rstrip("/")
        return repo
