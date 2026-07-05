"""Unit tests for workspace store and manager helpers."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from admin.workspace_manager import CURRENT_WORKSPACE_FILE, _slugify
from admin.workspace_store import WorkspaceStore


class WorkspaceStoreTests(unittest.TestCase):
    def test_create_and_get_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "workspaces.db")
            store = WorkspaceStore(db_path=db)
            ws = store.create_workspace(
                name="Test task",
                branch="wip/test-abc",
                worktree_path="/tmp/ws-abc",
                repo_root=".",
            )
            self.assertTrue(ws["id"].startswith("ws-"))
            loaded = store.get_workspace(ws["id"])
            self.assertEqual(loaded["name"], "Test task")

    def test_update_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = WorkspaceStore(db_path=os.path.join(tmp, "workspaces.db"))
            ws = store.create_workspace(
                name="A",
                branch="wip/a",
                worktree_path="/tmp/a",
                repo_root=".",
            )
            updated = store.update_workspace(ws["id"], status="review", pr_url="https://example.com/pr/1")
            self.assertEqual(updated["status"], "review")
            self.assertEqual(updated["pr_url"], "https://example.com/pr/1")


class WorkspaceManagerTests(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(_slugify("Fix Invoice Flow!"), "fix-invoice-flow")

    def test_activate_writes_current_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            hermes_home = Path(tmp)
            db = hermes_home / "workspaces.db"
            store = WorkspaceStore(db_path=str(db))
            ws = store.create_workspace(
                name="Active",
                branch="wip/active",
                worktree_path=str(hermes_home / "wt"),
                repo_root=".",
            )
            (hermes_home / "wt").mkdir()
            with mock.patch.dict(os.environ, {"HERMES_HOME": str(hermes_home)}):
                with mock.patch("admin.workspace_manager.CURRENT_WORKSPACE_FILE", hermes_home / "current_workspace.id"):
                    from admin.workspace_manager import activate_workspace, get_current_workspace_id

                    activate_workspace(ws["id"], store=store)
                    self.assertEqual(get_current_workspace_id(), ws["id"])


if __name__ == "__main__":
    unittest.main()
