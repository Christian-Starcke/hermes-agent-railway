"""Agent backend routing for Hermes workspaces."""

from __future__ import annotations

import json
import os
from typing import Any

from .workspace_manager import WorkspaceError, activate_workspace, get_workspace
from .workspace_store import WorkspaceStore


def _import_cursor_tools():
    import sys
    from pathlib import Path

    for path in (
        Path(os.environ.get("HERMES_HOME", "/data")) / ".hermes" / "plugins" / "cursor-cloud",
        Path("/opt/hermes-railway/plugins/cursor-cloud"),
    ):
        if path.is_dir() and str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from tools import handle_create_agent as cursor_create  # noqa: E402

    return cursor_create


def _import_opencode_tools():
    import sys
    from pathlib import Path

    for path in (
        Path(os.environ.get("HERMES_HOME", "/data")) / ".hermes" / "plugins" / "opencode-delegate",
        Path("/opt/hermes-railway/plugins/opencode-delegate"),
    ):
        if path.is_dir() and str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from tools import handle_create_task as opencode_create  # noqa: E402

    return opencode_create


def set_agent_backend(workspace_id: str, backend: str, store: WorkspaceStore | None = None) -> dict[str, Any]:
    store = store or WorkspaceStore()
    backend = backend.strip().lower()
    if backend not in {"hermes", "opencode", "cursor"}:
        raise WorkspaceError(f"unsupported agent_backend: {backend}")
    workspace = store.get_workspace(workspace_id)
    if not workspace:
        raise WorkspaceError(f"workspace not found: {workspace_id}")
    updated = store.update_workspace(workspace_id, agent_backend=backend)
    if backend == "hermes":
        activate_workspace(workspace_id, store=store)
    return updated or workspace


def delegate_workspace_to_cursor(
    workspace_id: str,
    *,
    prompt: str,
    objective: str | None = None,
    repository: str | None = None,
    store: WorkspaceStore | None = None,
) -> dict[str, Any]:
    store = store or WorkspaceStore()
    workspace = store.get_workspace(workspace_id)
    if not workspace:
        raise WorkspaceError(f"workspace not found: {workspace_id}")

    repo = repository or os.environ.get("CURSOR_DEFAULT_REPOSITORY", "").strip()
    if not repo:
        raise WorkspaceError("repository is required for Cursor delegation")

    cursor_create = _import_cursor_tools()
    result_raw = cursor_create(
        {
            "repository": repo,
            "objective": objective or workspace.get("name") or workspace_id,
            "prompt": prompt,
            "base_ref": workspace.get("branch") or workspace.get("base_ref") or "main",
            "auto_create_pr": True,
        },
        workspace_id=workspace_id,
    )
    result = json.loads(result_raw)
    if not result.get("success"):
        raise WorkspaceError(result.get("error") or "cursor delegation failed")

    task = result.get("task") or {}
    store.update_workspace(
        workspace_id,
        agent_backend="cursor",
        cursor_task_id=task.get("id"),
        status="busy",
    )
    return {"workspace": store.get_workspace(workspace_id), "task": task, "cursor": result}


def delegate_workspace_to_opencode(
    workspace_id: str,
    *,
    prompt: str,
    objective: str | None = None,
    store: WorkspaceStore | None = None,
) -> dict[str, Any]:
    store = store or WorkspaceStore()
    workspace = store.get_workspace(workspace_id)
    if not workspace:
        raise WorkspaceError(f"workspace not found: {workspace_id}")

    worktree_path = workspace.get("worktree_path") or ""
    opencode_create = _import_opencode_tools()
    result_raw = opencode_create(
        {
            "objective": objective or workspace.get("name") or workspace_id,
            "prompt": prompt,
            "workspace_hint": worktree_path,
        },
        workspace_id=workspace_id,
    )
    result = json.loads(result_raw)
    if not result.get("success"):
        raise WorkspaceError(result.get("error") or "opencode delegation failed")

    task = result.get("task") or {}
    store.update_workspace(
        workspace_id,
        agent_backend="opencode",
        opencode_task_id=task.get("id"),
        status="busy",
    )
    activate_workspace(workspace_id, store=store)
    return {"workspace": store.get_workspace(workspace_id), "task": task, "opencode": result}
