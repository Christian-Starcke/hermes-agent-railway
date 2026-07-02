"""Lightweight tests for cursor-cloud plugin (no live API calls)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

# Ensure plugin modules import from this directory.
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from cursor_client import CursorClient  # noqa: E402
from task_store import TaskStore  # noqa: E402
from webhook import apply_webhook_payload, verify_signature  # noqa: E402
from unittest.mock import patch  # noqa: E402


class CursorCloudPluginTests(unittest.TestCase):
    def test_normalize_repository(self):
        self.assertEqual(
            CursorClient.normalize_repository("org/repo"),
            "https://github.com/org/repo",
        )

    def test_task_store_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "cursor_tasks.db")
            store = TaskStore(db)
            task = store.create_task(
                objective="Test",
                repository="https://github.com/org/repo",
                acceptance_criteria=["passes tests"],
            )
            self.assertIn("id", task)
            updated = store.update_task(
                task["id"],
                cursor_agent_id="bc-test",
                status="running",
            )
            self.assertEqual(updated["cursor_agent_id"], "bc-test")
            listed = store.list_tasks(status="running")
            self.assertEqual(len(listed), 1)

    def test_webhook_signature_and_apply(self):
        secret = "test-secret"
        payload = {
            "event": "statusChange",
            "id": "bc-test",
            "status": "FINISHED",
            "summary": "done",
            "target": {"branchName": "cursor/test", "prUrl": "https://github.com/org/repo/pull/1"},
        }
        raw = json.dumps(payload).encode()
        sig = "sha256=" + __import__("hmac").new(secret.encode(), raw, __import__("hashlib").sha256).hexdigest()
        self.assertTrue(verify_signature(secret, raw, sig))

        with tempfile.TemporaryDirectory() as tmp:
            store = TaskStore(os.path.join(tmp, "cursor_tasks.db"))
            task = store.create_task(
                objective="Webhook test",
                repository="https://github.com/org/repo",
            )
            store.update_task(task["id"], cursor_agent_id="bc-test", status="running")
            result = apply_webhook_payload(payload, store=store)
            self.assertTrue(result["success"])
            self.assertEqual(result["status"], "finished")
            refreshed = store.get_task(task["id"])
            self.assertEqual(refreshed["pr_url"], "https://github.com/org/repo/pull/1")

    def test_create_agent_uses_v0_when_webhook_configured(self):
        client = CursorClient(api_key="test-key")
        with patch.object(client, "create_agent_v0", return_value={"agent": {"id": "a1"}, "run": {}}) as v0:
            client.create_agent(
                prompt_text="hello",
                repository_url="https://github.com/org/repo",
                webhook_url="https://example.com/webhooks/cursor",
                webhook_secret="secret",
            )
            v0.assert_called_once()


if __name__ == "__main__":
    unittest.main()
