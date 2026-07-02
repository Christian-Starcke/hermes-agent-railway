#!/usr/bin/env python3
"""Local smoke checks for cursor-cloud (no live Cursor API or Railway deploy)."""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from cursor_client import CursorClient  # noqa: E402
from task_store import TaskStore  # noqa: E402
from webhook import apply_webhook_payload, poll_pending_tasks, verify_signature  # noqa: E402


class LocalSmokeTests(unittest.TestCase):
    def test_plugin_manifest_and_schemas(self):
        import yaml

        manifest = yaml.safe_load((ROOT / "plugin.yaml").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "cursor-cloud")
        self.assertIn("CURSOR_API_KEY", manifest.get("requires_env", []))

        from schemas import TOOL_SCHEMAS

        expected_tools = {
            "cursor_list_repositories",
            "cursor_list_models",
            "cursor_get_account",
            "cursor_create_agent",
            "cursor_get_agent",
            "cursor_list_agents",
            "cursor_create_run",
            "cursor_get_run",
            "cursor_cancel_agent",
            "cursor_list_tasks",
        }
        self.assertTrue(expected_tools.issubset(set(TOOL_SCHEMAS)))

    def test_admin_webhook_route(self):
        try:
            import starlette  # noqa: F401
        except ImportError:
            self.skipTest("starlette not installed locally")
        from starlette.testclient import TestClient

        admin_dir = REPO_ROOT / "admin"
        sys.path.insert(0, str(admin_dir.parent))
        os.environ["CURSOR_WEBHOOK_SECRET"] = "smoke-secret"
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["HERMES_HOME"] = tmp
            db = os.path.join(tmp, "cursor_tasks.db")
            store = TaskStore(db)
            task = store.create_task(
                objective="smoke",
                repository="https://github.com/org/repo",
            )
            store.update_task(task["id"], cursor_agent_id="agent-smoke", status="running")

            from admin.cursor_webhook import cursor_webhook  # noqa: E402
            from starlette.applications import Starlette
            from starlette.routing import Route

            app = Starlette(routes=[Route("/webhooks/cursor", cursor_webhook, methods=["POST"])])
            client = TestClient(app)

            payload = {
                "event": "statusChange",
                "id": "agent-smoke",
                "status": "FINISHED",
                "summary": "smoke ok",
                "target": {"branchName": "cursor/smoke", "prUrl": "https://github.com/org/repo/pull/99"},
            }
            raw = json.dumps(payload).encode()
            sig = "sha256=" + hmac.new(b"smoke-secret", raw, hashlib.sha256).hexdigest()
            response = client.post("/webhooks/cursor", content=raw, headers={"X-Webhook-Signature": sig})
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertTrue(body.get("success"))
            self.assertEqual(body.get("status"), "finished")

    def test_poll_pending_with_mock_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TaskStore(os.path.join(tmp, "cursor_tasks.db"))
            task = store.create_task(
                objective="poll",
                repository="https://github.com/org/repo",
            )
            store.update_task(
                task["id"],
                cursor_agent_id="agent-poll",
                cursor_run_id="run-poll",
                status="running",
            )

            mock_client = MagicMock()
            mock_client.get_run.return_value = {
                "status": "FINISHED",
                "result": "done via poll",
                "branchName": "cursor/poll",
                "prUrl": "https://github.com/org/repo/pull/2",
            }

            result = poll_pending_tasks(store=store, client=mock_client)
            self.assertTrue(result["success"])
            self.assertEqual(result["checked"], 1)
            refreshed = store.get_task(task["id"])
            self.assertEqual(refreshed["status"], "finished")
            self.assertEqual(refreshed["pr_url"], "https://github.com/org/repo/pull/2")


if __name__ == "__main__":
    unittest.main(verbosity=2)
