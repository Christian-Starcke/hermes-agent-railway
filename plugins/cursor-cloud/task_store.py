"""SQLite task store for Hermes ↔ Cursor delegations."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

def _default_db_path() -> str:
    return os.path.join(os.environ.get("HERMES_HOME", "/data"), "cursor_tasks.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cursor_tasks (
  id TEXT PRIMARY KEY,
  hermes_session_id TEXT,
  workspace_id TEXT,
  objective TEXT NOT NULL,
  repository TEXT NOT NULL,
  base_ref TEXT DEFAULT 'main',
  cursor_agent_id TEXT,
  cursor_run_id TEXT,
  status TEXT NOT NULL,
  branch_name TEXT,
  pr_url TEXT,
  summary TEXT,
  acceptance_criteria TEXT,
  webhook_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cursor_tasks_status ON cursor_tasks(status);
CREATE INDEX IF NOT EXISTS idx_cursor_tasks_agent ON cursor_tasks(cursor_agent_id);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class TaskStore:
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
            columns = {row[1] for row in conn.execute("PRAGMA table_info(cursor_tasks)").fetchall()}
            if "workspace_id" not in columns:
                conn.execute("ALTER TABLE cursor_tasks ADD COLUMN workspace_id TEXT")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cursor_tasks_workspace ON cursor_tasks(workspace_id)"
            )

    def create_task(
        self,
        *,
        objective: str,
        repository: str,
        base_ref: str = "main",
        hermes_session_id: str | None = None,
        workspace_id: str | None = None,
        acceptance_criteria: list[str] | None = None,
        status: str = "pending",
    ) -> dict[str, Any]:
        task_id = str(uuid.uuid4())
        now = _utc_now()
        criteria_json = json.dumps(acceptance_criteria or [])
        with self._db() as conn:
            conn.execute(
                """
                INSERT INTO cursor_tasks (
                  id, hermes_session_id, workspace_id, objective, repository, base_ref,
                  status, acceptance_criteria, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    hermes_session_id,
                    workspace_id,
                    objective,
                    repository,
                    base_ref,
                    status,
                    criteria_json,
                    now,
                    now,
                ),
            )
        return self.get_task(task_id) or {}

    def update_task(self, task_id: str, **fields: Any) -> dict[str, Any] | None:
        if not fields:
            return self.get_task(task_id)
        fields["updated_at"] = _utc_now()
        columns = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [task_id]
        with self._db() as conn:
            conn.execute(f"UPDATE cursor_tasks SET {columns} WHERE id = ?", values)
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._db() as conn:
            row = conn.execute("SELECT * FROM cursor_tasks WHERE id = ?", (task_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def get_task_by_agent_id(self, cursor_agent_id: str) -> dict[str, Any] | None:
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM cursor_tasks WHERE cursor_agent_id = ? ORDER BY updated_at DESC LIMIT 1",
                (cursor_agent_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_tasks(
        self,
        *,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM cursor_tasks"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._db() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def count_active(self) -> int:
        with self._db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM cursor_tasks WHERE status IN ('pending', 'running')"
            ).fetchone()
        return int(row["c"]) if row else 0

    def list_pending_or_running(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._db() as conn:
            rows = conn.execute(
                """
                SELECT * FROM cursor_tasks
                WHERE status IN ('pending', 'running')
                ORDER BY updated_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        raw = data.get("acceptance_criteria")
        if isinstance(raw, str) and raw:
            try:
                data["acceptance_criteria"] = json.loads(raw)
            except json.JSONDecodeError:
                data["acceptance_criteria"] = []
        else:
            data["acceptance_criteria"] = []
        return data
