"""Lightweight tests for paperclip plugin (no live API calls)."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from paperclip_client import PaperclipClient  # noqa: E402
import tools  # noqa: E402


class PaperclipPluginTests(unittest.TestCase):
    def test_normalize_repository(self):
        self.assertEqual(
            PaperclipClient.normalize_repository("org/repo"),
            "https://github.com/org/repo",
        )

    def test_agent_map_parsing(self):
        with patch.dict(
            os.environ,
            {
                "PAPERCLIP_AGENT_MAP": "org/a:uuid-a,org/b:uuid-b",
                "PAPERCLIP_DEFAULT_AGENT_ID": "default-uuid",
            },
            clear=False,
        ):
            self.assertEqual(tools._resolve_agent_id("org/a"), "uuid-a")
            self.assertEqual(tools._resolve_agent_id("https://github.com/org/b"), "uuid-b")
            self.assertEqual(tools._resolve_agent_id("org/unknown"), "default-uuid")

    def test_delegate_requires_paperclip_mode(self):
        with patch.dict(os.environ, {"PAPERCLIP_DELEGATION_MODE": "direct"}, clear=False):
            result = json.loads(
                tools.handle_delegate_coding_task(
                    {
                        "objective": "Test",
                        "prompt": "Do thing",
                        "repository": "org/repo",
                    }
                )
            )
            self.assertFalse(result["success"])
            self.assertIn("PAPERCLIP_DELEGATION_MODE", result["error"])

    def test_delegate_coding_task_success(self):
        env = {
            "PAPERCLIP_DELEGATION_MODE": "paperclip",
            "PAPERCLIP_BASE_URL": "http://paperclip:3100",
            "PAPERCLIP_API_TOKEN": "token",
            "PAPERCLIP_COMPANY_ID": "company-1",
            "PAPERCLIP_DEFAULT_AGENT_ID": "agent-1",
        }
        created = {
            "id": "issue-1",
            "identifier": "PAP-7",
            "title": "Fix bug",
            "status": "todo",
            "assigneeAgentId": "agent-1",
        }
        mock_client = MagicMock()
        mock_client.create_issue.return_value = created
        with patch.dict(os.environ, env, clear=False):
            with patch("tools.PaperclipClient", return_value=mock_client):
                result = json.loads(
                    tools.handle_delegate_coding_task(
                        {
                            "objective": "Fix bug",
                            "prompt": "Fix the upload flow",
                            "repository": "org/repo",
                            "acceptance_criteria": ["tests pass"],
                        }
                    )
                )
        self.assertTrue(result["success"])
        self.assertEqual(result["issue"]["identifier"], "PAP-7")
        mock_client.create_issue.assert_called_once()
        payload = mock_client.create_issue.call_args[0][0]
        self.assertEqual(payload["assigneeAgentId"], "agent-1")
        self.assertIn("Fix the upload flow", payload["description"])


if __name__ == "__main__":
    unittest.main()
