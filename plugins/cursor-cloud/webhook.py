"""Webhook verification and task updates for Cursor Cloud Agent events."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

try:
    from .cursor_client import CursorClient
    from .task_store import TaskStore
except ImportError:
    from cursor_client import CursorClient
    from task_store import TaskStore


def verify_signature(secret: str, raw_body: bytes, signature_header: str | None) -> bool:
    if not secret or not signature_header:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.strip())


def apply_webhook_payload(payload: dict[str, Any], *, store: TaskStore | None = None) -> dict[str, Any]:
    """Handle Cursor webhook statusChange payloads (v0 format, forward-compatible)."""
    store = store or TaskStore()
    event = payload.get("event")
    if event and event != "statusChange":
        return {"success": True, "ignored": True, "reason": f"unsupported event: {event}"}

    agent_id = str(payload.get("id") or "")
    status = str(payload.get("status") or "").upper()
    if not agent_id:
        return {"success": False, "error": "missing agent id in webhook payload"}

    task = store.get_task_by_agent_id(agent_id)
    if not task:
        return {"success": False, "error": f"no local task for agent {agent_id}"}

    mapped = "running"
    if status == "FINISHED":
        mapped = "finished"
    elif status == "ERROR":
        mapped = "error"
    elif status in {"CANCELLED", "CANCELED"}:
        mapped = "cancelled"

    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    updates: dict[str, Any] = {
        "status": mapped,
        "branch_name": target.get("branchName") or task.get("branch_name"),
        "pr_url": target.get("prUrl") or task.get("pr_url"),
        "summary": payload.get("summary") or task.get("summary"),
        "webhook_id": payload.get("id") or task.get("webhook_id"),
    }
    updated = store.update_task(task["id"], **updates)

    workspace_synced = None
    try:
        import sys
        from pathlib import Path

        railway_admin = Path("/opt/hermes-railway/admin")
        if railway_admin.is_dir() and str(railway_admin.parent) not in sys.path:
            sys.path.insert(0, str(railway_admin.parent))
        from admin.workspace_manager import sync_workspace_from_cursor_task

        workspace_synced = sync_workspace_from_cursor_task(
            updated or task,
            mapped_status=mapped,
            pr_url=updates.get("pr_url"),
            branch_name=updates.get("branch_name"),
        )
    except Exception:
        workspace_synced = None

    return {
        "success": True,
        "task": updated,
        "agent_id": agent_id,
        "status": mapped,
        "workspace": workspace_synced,
    }


def sync_task_from_run(
    task: dict[str, Any],
    *,
    client: CursorClient | None = None,
    store: TaskStore | None = None,
) -> dict[str, Any] | None:
    """Refresh a local task from Cursor run state (cron / manual poll)."""
    store = store or TaskStore()
    client = client or CursorClient()
    agent_id = task.get("cursor_agent_id")
    run_id = task.get("cursor_run_id")
    if not agent_id:
        return task

    if not run_id:
        agent = client.get_agent(agent_id)
        run_id = agent.get("latestRunId")
        if run_id:
            store.update_task(task["id"], cursor_run_id=run_id)

    if not run_id:
        return store.get_task(task["id"])

    run = client.get_run(agent_id, run_id)
    mapped = CursorClient.map_run_status(run.get("status"))
    branch, pr_url = CursorClient.extract_run_git(run)
    updates: dict[str, Any] = {
        "status": mapped,
        "summary": run.get("result") or task.get("summary"),
    }
    if branch:
        updates["branch_name"] = branch
    if pr_url:
        updates["pr_url"] = pr_url
    refreshed = store.update_task(task["id"], **updates)
    try:
        import sys
        from pathlib import Path

        railway_admin = Path("/opt/hermes-railway/admin")
        if railway_admin.is_dir() and str(railway_admin.parent) not in sys.path:
            sys.path.insert(0, str(railway_admin.parent))
        from admin.workspace_manager import sync_workspace_from_cursor_task

        sync_workspace_from_cursor_task(
            refreshed or task,
            mapped_status=mapped,
            pr_url=pr_url,
            branch_name=branch,
        )
    except Exception:
        pass
    return refreshed


def poll_pending_tasks(*, store: TaskStore | None = None, client: CursorClient | None = None) -> dict[str, Any]:
    store = store or TaskStore()
    client = client or CursorClient()
    tasks = store.list_pending_or_running()
    updated: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for task in tasks:
        try:
            refreshed = sync_task_from_run(task, client=client, store=store)
            if refreshed:
                updated.append(refreshed)
        except Exception as exc:
            errors.append({"task_id": task.get("id", ""), "error": str(exc)})
    return {"success": True, "checked": len(tasks), "updated": len(updated), "errors": errors, "tasks": updated}
