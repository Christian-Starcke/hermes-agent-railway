"""SQLite store for Hermes git worktree workspaces."""

from __future__ import annotations

from contextlib import contextmanager
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any


def _default_db_path() -> str:
    return os.path.join(os.environ.get("HERMES_HOME", "/data"), "workspaces.db")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS workspaces (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  branch TEXT NOT NULL,
  base_ref TEXT DEFAULT 'main',
  worktree_path TEXT NOT NULL,
  repo_root TEXT NOT NULL,
  agent_backend TEXT DEFAULT 'hermes',
  status TEXT DEFAULT 'active',
  hermes_session_id TEXT,
  cursor_task_id TEXT,
  opencode_task_id TEXT,
  issue_url TEXT,
  pr_url TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_workspaces_status ON workspaces(status);
CREATE INDEX IF NOT EXISTS idx_workspaces_branch ON workspaces(branch);

CREATE TABLE IF NOT EXISTS workspace_comments (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  file_path TEXT,
  line_number INTEGER,
  body TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
);
CREATE INDEX IF NOT EXISTS idx_workspace_comments_ws ON workspace_comments(workspace_id);
"""


class WorkspaceStore:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or _default_db_path()
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _db(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._db() as conn:
            conn.executescript(_SCHEMA)

    def create_workspace(
        self,
        *,
        name: str,
        branch: str,
        worktree_path: str,
        repo_root: str,
        base_ref: str = "main",
        agent_backend: str = "hermes",
        issue_url: str | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        workspace_id = f"ws-{uuid.uuid4().hex[:12]}"
        now = _utc_now()
        with self._db() as conn:
            conn.execute(
                """
                INSERT INTO workspaces (
                  id, name, branch, base_ref, worktree_path, repo_root,
                  agent_backend, status, issue_url, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workspace_id,
                    name,
                    branch,
                    base_ref,
                    worktree_path,
                    repo_root,
                    agent_backend,
                    status,
                    issue_url,
                    now,
                    now,
                ),
            )
        return self.get_workspace(workspace_id) or {}

    def update_workspace(self, workspace_id: str, **fields: Any) -> dict[str, Any] | None:
        if not fields:
            return self.get_workspace(workspace_id)
        fields["updated_at"] = _utc_now()
        columns = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [workspace_id]
        with self._db() as conn:
            conn.execute(f"UPDATE workspaces SET {columns} WHERE id = ?", values)
        return self.get_workspace(workspace_id)

    def get_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        with self._db() as conn:
            row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
        return dict(row) if row else None

    def get_workspace_by_branch(self, branch: str) -> dict[str, Any] | None:
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM workspaces WHERE branch = ? ORDER BY updated_at DESC LIMIT 1",
                (branch,),
            ).fetchone()
        return dict(row) if row else None

    def get_workspace_by_cursor_task(self, cursor_task_id: str) -> dict[str, Any] | None:
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM workspaces WHERE cursor_task_id = ? ORDER BY updated_at DESC LIMIT 1",
                (cursor_task_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_workspaces(
        self,
        *,
        status: str | None = None,
        include_archived: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM workspaces"
        params: list[Any] = []
        clauses: list[str] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        elif not include_archived:
            clauses.append("status != 'archived'")
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._db() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def count_active(self) -> int:
        with self._db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM workspaces WHERE status IN ('active', 'review', 'busy')"
            ).fetchone()
        return int(row["c"]) if row else 0

    def add_comment(
        self,
        *,
        workspace_id: str,
        body: str,
        file_path: str | None = None,
        line_number: int | None = None,
    ) -> dict[str, Any]:
        comment_id = str(uuid.uuid4())
        now = _utc_now()
        with self._db() as conn:
            conn.execute(
                """
                INSERT INTO workspace_comments (id, workspace_id, file_path, line_number, body, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (comment_id, workspace_id, file_path, line_number, body, now),
            )
        return {
            "id": comment_id,
            "workspace_id": workspace_id,
            "file_path": file_path,
            "line_number": line_number,
            "body": body,
            "created_at": now,
        }

    def list_comments(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._db() as conn:
            rows = conn.execute(
                "SELECT * FROM workspace_comments WHERE workspace_id = ? ORDER BY created_at ASC",
                (workspace_id,),
            ).fetchall()
        return [dict(row) for row in rows]
