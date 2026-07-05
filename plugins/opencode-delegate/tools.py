"""Tool handlers for the opencode-delegate Hermes plugin."""

from __future__ import annotations

import json
import os
from typing import Any

from .opencode_client import OpenCodeAPIError, OpenCodeClient
from .sync import sync_task_from_session
from .task_store import TaskStore


def _session_id(kwargs: dict[str, Any]) -> str | None:
    for key in ("session_id", "hermes_session_id"):
        value = kwargs.get(key)
        if value:
            return str(value)
    return None


def _max_active() -> int:
    raw = os.environ.get("OPENCODE_MAX_ACTIVE", "3").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 3


def _default_agent() -> str:
    return os.environ.get("OPENCODE_DEFAULT_AGENT", "build").strip() or "build"


def _default_model() -> str | None:
    value = os.environ.get("OPENCODE_DEFAULT_MODEL", "").strip()
    return value or None


def _build_prompt(prompt: str, acceptance_criteria: list[str] | None, workspace_hint: str | None) -> str:
    lines = [prompt.strip(), "", "Constraints:", "- Do not merge any pull request.", "- Report what you changed and how to verify it."]
    if workspace_hint:
        lines.extend(["", f"Workspace hint: work under /data/workspace/{workspace_hint.strip('/')}"])
    if acceptance_criteria:
        lines.append("", "Acceptance criteria:")
        lines.extend(f"- {item}" for item in acceptance_criteria)
    return "\n".join(lines)


def handle_health(params: dict[str, Any], **kwargs: Any) -> str:
    del params, kwargs
    try:
        client = OpenCodeClient()
        data = client.health()
        return json.dumps({"success": True, "health": data})
    except OpenCodeAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_list_agents(params: dict[str, Any], **kwargs: Any) -> str:
    del params, kwargs
    try:
        client = OpenCodeClient()
        data = client.list_agents()
        return json.dumps({"success": True, "agents": data})
    except OpenCodeAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_list_providers(params: dict[str, Any], **kwargs: Any) -> str:
    del params, kwargs
    try:
        client = OpenCodeClient()
        data = client.list_providers()
        return json.dumps({"success": True, "providers": data})
    except OpenCodeAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_create_task(params: dict[str, Any], **kwargs: Any) -> str:
    try:
        store = TaskStore()
        if store.count_active() >= _max_active():
            return json.dumps(
                {
                    "success": False,
                    "error": f"Too many active OpenCode delegations (max {_max_active()}).",
                }
            )

        objective = str(params.get("objective") or "").strip()
        prompt = str(params.get("prompt") or "").strip()
        if not objective or not prompt:
            return json.dumps({"success": False, "error": "objective and prompt are required"})

        criteria = params.get("acceptance_criteria") or []
        if not isinstance(criteria, list):
            criteria = [str(criteria)]
        criteria = [str(item) for item in criteria]

        workspace_hint = str(params.get("workspace_hint") or "").strip()
        agent = str(params.get("agent") or _default_agent())
        model_id = str(params.get("model") or _default_model() or "")
        model = OpenCodeClient.parse_model(model_id) if model_id else OpenCodeClient.parse_model(_default_model())

        task = store.create_task(
            objective=objective,
            workspace_hint=workspace_hint,
            hermes_session_id=_session_id(kwargs),
            workspace_id=str(kwargs.get("workspace_id")).strip() if kwargs.get("workspace_id") else None,
            acceptance_criteria=criteria,
            agent=agent,
            model=model_id or None,
            status="pending",
        )

        client = OpenCodeClient()
        session = client.create_session(title=objective[:100])
        session_id = str(session.get("id") or "")
        if not session_id:
            store.update_task(task["id"], status="error", summary="OpenCode create session missing id")
            return json.dumps({"success": False, "error": "OpenCode create session missing id", "raw": session})

        store.update_task(
            task["id"],
            opencode_session_id=session_id,
            status="running",
        )

        full_prompt = _build_prompt(prompt, criteria, workspace_hint or None)
        client.prompt_async(
            session_id,
            text=full_prompt,
            agent=agent,
            model=model,
        )

        refreshed = sync_task_from_session(store.get_task(task["id"]) or {}, client=client, store=store)
        workspace_id = kwargs.get("workspace_id")
        if workspace_id and refreshed:
            try:
                import sys
                from pathlib import Path

                railway_root = Path("/opt/hermes-railway")
                if railway_root.is_dir() and str(railway_root) not in sys.path:
                    sys.path.insert(0, str(railway_root))
                from admin.workspace_store import WorkspaceStore

                WorkspaceStore().update_workspace(
                    str(workspace_id),
                    opencode_task_id=refreshed.get("id"),
                    status="busy",
                )
            except Exception:
                pass
        base_url = os.environ.get("OPENCODE_SERVER_URL", "").strip().rstrip("/")
        return json.dumps(
            {
                "success": True,
                "task": refreshed,
                "session": session,
                "opencode_url": f"{base_url}/session/{session_id}" if base_url else None,
            }
        )
    except OpenCodeAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_send_message(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        store = TaskStore()
        client = OpenCodeClient()
        prompt = str(params.get("prompt") or "").strip()
        if not prompt:
            return json.dumps({"success": False, "error": "prompt is required"})

        task_id = params.get("task_id")
        session_id = params.get("session_id")
        task = store.get_task(str(task_id)) if task_id else None
        if not session_id and task:
            session_id = task.get("opencode_session_id")
        if not session_id:
            return json.dumps({"success": False, "error": "session_id or task_id is required"})

        agent = params.get("agent") or (task.get("agent") if task else None) or _default_agent()
        model_id = params.get("model") or (task.get("model") if task else None) or _default_model()
        model = OpenCodeClient.parse_model(str(model_id) if model_id else None)

        result = client.send_message(
            str(session_id),
            text=_build_prompt(prompt, None, task.get("workspace_hint") if task else None),
            agent=str(agent),
            model=model,
        )
        if task:
            store.update_task(task["id"], status="running")
            task = sync_task_from_session(store.get_task(task["id"]) or {}, client=client, store=store)
        return json.dumps({"success": True, "result": result, "task": task})
    except OpenCodeAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_get_task(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        store = TaskStore()
        client = OpenCodeClient()
        task_id = params.get("task_id")
        session_id = params.get("session_id")
        task = store.get_task(str(task_id)) if task_id else None
        if not session_id and task:
            session_id = task.get("opencode_session_id")
        if not task and session_id:
            task = store.get_task_by_session_id(str(session_id))
        if not task:
            return json.dumps({"success": False, "error": "task_id or session_id is required"})

        session = None
        if task.get("opencode_session_id"):
            session = client.get_session(str(task["opencode_session_id"]))
        refreshed = sync_task_from_session(task, client=client, store=store)
        return json.dumps({"success": True, "task": refreshed, "session": session})
    except OpenCodeAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_list_tasks(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    store = TaskStore()
    status = params.get("status")
    limit = int(params.get("limit") or 20)
    tasks = store.list_tasks(status=str(status) if status else None, limit=limit)
    return json.dumps({"success": True, "tasks": tasks})


def handle_abort_task(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        store = TaskStore()
        client = OpenCodeClient()
        task_id = params.get("task_id")
        session_id = params.get("session_id")
        task = store.get_task(str(task_id)) if task_id else None
        if not session_id and task:
            session_id = task.get("opencode_session_id")
        if not session_id:
            return json.dumps({"success": False, "error": "session_id or task_id is required"})

        aborted = client.abort_session(str(session_id))
        if task:
            store.update_task(task["id"], status="cancelled")
            task = store.get_task(task["id"])
        return json.dumps({"success": True, "aborted": aborted, "task": task})
    except OpenCodeAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})
