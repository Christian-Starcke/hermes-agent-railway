"""Refresh local OpenCode task status from the remote session."""

from __future__ import annotations

from typing import Any

try:
    from .opencode_client import OpenCodeClient
    from .task_store import TaskStore
except ImportError:
    from opencode_client import OpenCodeClient
    from task_store import TaskStore


def sync_task_from_session(
    task: dict[str, Any],
    *,
    client: OpenCodeClient | None = None,
    store: TaskStore | None = None,
) -> dict[str, Any] | None:
    store = store or TaskStore()
    client = client or OpenCodeClient()
    session_id = task.get("opencode_session_id")
    if not session_id:
        return task

    statuses = client.session_status()
    session_status = statuses.get(session_id) if isinstance(statuses, dict) else None
    mapped = OpenCodeClient.map_session_status(session_status)

    messages = client.list_messages(session_id, limit=20)
    summary = OpenCodeClient.extract_summary(messages) or task.get("summary")

    if mapped == "running" and summary and task.get("status") == "pending":
        mapped = "running"

    # If session status is idle and we have assistant output, treat as finished.
    if mapped == "running" and summary:
        if isinstance(session_status, dict):
            state = str(session_status.get("type") or session_status.get("status") or "").lower()
            if state in {"idle", ""}:
                mapped = "finished"

    updates: dict[str, Any] = {"status": mapped}
    if summary:
        updates["summary"] = summary
    return store.update_task(task["id"], **updates)


def poll_pending_tasks(*, store: TaskStore | None = None, client: OpenCodeClient | None = None) -> dict[str, Any]:
    store = store or TaskStore()
    client = client or OpenCodeClient()
    tasks = store.list_pending_or_running()
    updated: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for task in tasks:
        try:
            refreshed = sync_task_from_session(task, client=client, store=store)
            if refreshed:
                updated.append(refreshed)
        except Exception as exc:
            errors.append({"task_id": task.get("id", ""), "error": str(exc)})
    return {"success": True, "checked": len(tasks), "updated": len(updated), "errors": errors, "tasks": updated}
