"""Regression tests for the Railway health endpoint."""

from __future__ import annotations

import json
import os
import sys
import unittest
from types import ModuleType
from unittest.mock import patch

import httpx

# The WebSocket terminal requires POSIX fcntl; it is unrelated to these tests.
terminal = ModuleType("admin.terminal")
terminal.login_ws = object()
terminal.shell_ws = object()
sys.modules.setdefault("admin.terminal", terminal)

from admin.app import proxy_health


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


class _FakeAsyncClient:
    def __init__(self, *, status_code: int = 200, error: Exception | None = None):
        self.status_code = status_code
        self.error = error
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, url: str, timeout: float):
        self.requests.append((url, timeout))
        if self.error is not None:
            raise self.error
        return _FakeResponse(self.status_code)


class ProxyHealthTests(unittest.IsolatedAsyncioTestCase):
    async def test_gateway_disabled_keeps_proxy_liveness(self):
        with patch.dict(os.environ, {"START_GATEWAY": "false"}):
            response = await proxy_health(None)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.body)["status"], "ok")

    async def test_gateway_ready_returns_200(self):
        client = _FakeAsyncClient(status_code=200)
        with (
            patch.dict(os.environ, {"START_GATEWAY": "true"}),
            patch("httpx.AsyncClient", return_value=client),
        ):
            response = await proxy_health(None)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.requests, [("http://127.0.0.1:8642/health", 2.0)])

    async def test_gateway_unavailable_returns_503(self):
        client = _FakeAsyncClient(error=httpx.ConnectError("gateway down"))
        with (
            patch.dict(os.environ, {"START_GATEWAY": "true"}),
            patch("httpx.AsyncClient", return_value=client),
        ):
            response = await proxy_health(None)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(json.loads(response.body)["status"], "unavailable")

    async def test_gateway_unhealthy_response_returns_503(self):
        client = _FakeAsyncClient(status_code=503)
        with (
            patch.dict(os.environ, {"START_GATEWAY": "true"}),
            patch("httpx.AsyncClient", return_value=client),
        ):
            response = await proxy_health(None)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(json.loads(response.body)["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
