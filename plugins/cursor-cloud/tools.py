"""Tool handlers for the cursor-cloud Hermes plugin."""

from __future__ import annotations

import json
import os
from typing import Any

from .cursor_client import CursorAPIError, CursorClient
from .task_store import TaskStore
from .webhook import sync_task_from_run


def _session_id(kwargs: dict[str, Any]) -> str | None:
    for key in ("session_id", "hermes_session_id"):
        value = kwargs.get(key)
        if value:
            return str(value)
    return None


def _max_active() -> int:
    raw = os.environ.get("CURSOR_MAX_ACTIVE", "3").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 3


def _allowed_repo(repository: str) -> bool:
    allowlist = os.environ.get("CURSOR_ALLOWED_REPOS", "").strip()
    if not allowlist:
        return True
    normalized = CursorClient.normalize_repository(repository)
    allowed = {item.strip() for item in allowlist.split(",") if item.strip()}
    for item in allowed:
        if item in normalized or item in repository:
            return True
    return False


def _build_prompt(prompt: str, acceptance_criteria: list[str] | None) -> str:
    lines = [prompt.strip(), "", "Constraints:", "- Do not merge any pull request.", "- Report what you changed and how to verify it."]
    if acceptance_criteria:
        lines.append("", "Acceptance criteria:")
        lines.extend(f"- {item}" for item in acceptance_criteria)
    return "\n".join(lines)


def handle_list_repositories(params: dict[str, Any], **kwargs: Any) -> str:
    del params, kwargs
    try:
        client = CursorClient()
        data = client.list_repositories()
        return json.dumps({"success": True, "repositories": data})
    except CursorAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_list_models(params: dict[str, Any], **kwargs: Any) -> str:
    del params, kwargs
    try:
        client = CursorClient()
        data = client.list_models()
        return json.dumps({"success": True, "models": data})
    except CursorAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_get_account(params: dict[str, Any], **kwargs: Any) -> str:
    del params, kwargs
    try:
        client = CursorClient()
        data = client.get_account()
        return json.dumps({"success": True, "account": data})
    except CursorAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_create_agent(params: dict[str, Any], **kwargs: Any) -> str:
    try:
        store = TaskStore()
        if store.count_active() >= _max_active():
            return json.dumps(
                {
                    "success": False,
                    "error": f"Too many active Cursor delegations (max {_max_active()}).",
                }
            )

        repository = params.get("repository") or os.environ.get("CURSOR_DEFAULT_REPOSITORY", "")
        if not repository:
            return json.dumps({"success": False, "error": "repository is required"})
        if not _allowed_repo(repository):
            return json.dumps({"success": False, "error": f"repository not allowed: {repository}"})

        repo_url = CursorClient.normalize_repository(repository)
        objective = str(params.get("objective") or "").strip()
        prompt = str(params.get("prompt") or "").strip()
        if not objective or not prompt:
            return json.dumps({"success": False, "error": "objective and prompt are required"})

        criteria = params.get("acceptance_criteria") or []
        if not isinstance(criteria, list):
            criteria = [str(criteria)]
        criteria = [str(item) for item in criteria]

        base_ref = str(params.get("base_ref") or "main")
        auto_create_pr = bool(params.get("auto_create_pr", True))
        model_id = params.get("model_id")

        task = store.create_task(
            objective=objective,
            repository=repo_url,
            base_ref=base_ref,
            hermes_session_id=_session_id(kwargs),
            workspace_id=str(kwargs.get("workspace_id")).strip() if kwargs.get("workspace_id") else None,
            acceptance_criteria=criteria,
            status="pending",
        )

        client = CursorClient()
        full_prompt = _build_prompt(prompt, criteria)
        webhook_url = os.environ.get("CURSOR_WEBHOOK_URL", "").strip()
        webhook_secret = os.environ.get("CURSOR_WEBHOOK_SECRET", "").strip()
        created = client.create_agent(
            prompt_text=full_prompt,
            repository_url=repo_url,
            starting_ref=base_ref,
            auto_create_pr=auto_create_pr,
            model_id=str(model_id) if model_id else None,
            name=objective[:100],
            webhook_url=webhook_url or None,
            webhook_secret=webhook_secret or None,
        )

        agent = created.get("agent") or {}
        run = created.get("run") or {}
        agent_id = agent.get("id")
        run_id = run.get("id") or agent.get("latestRunId")
        if not agent_id:
            store.update_task(task["id"], status="error", summary="Cursor create response missing agent id")
            return json.dumps({"success": False, "error": "Cursor create response missing agent id", "raw": created})

        mapped = CursorClient.map_run_status(run.get("status"))
        store.update_task(
            task["id"],
            cursor_agent_id=agent_id,
            cursor_run_id=run_id,
            status=mapped if mapped != "pending" else "running",
        )
        refreshed = sync_task_from_run(store.get_task(task["id"]) or {}, client=client, store=store)
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
                    cursor_task_id=refreshed.get("id"),
                    status="busy",
                )
            except Exception:
                pass
        return json.dumps(
            {
                "success": True,
                "task": refreshed,
                "agent": agent,
                "run": run,
                "cursor_url": agent.get("url"),
            }
        )
    except CursorAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_get_agent(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        store = TaskStore()
        client = CursorClient()
        task_id = params.get("task_id")
        agent_id = params.get("agent_id")
        task = store.get_task(str(task_id)) if task_id else None
        if not agent_id and task:
            agent_id = task.get("cursor_agent_id")
        if not agent_id:
            return json.dumps({"success": False, "error": "agent_id or task_id is required"})
        agent = client.get_agent(str(agent_id))
        if task:
            task = sync_task_from_run(task, client=client, store=store)
        elif agent.get("id"):
            task = store.get_task_by_agent_id(str(agent.get("id")))
            if task:
                task = sync_task_from_run(task, client=client, store=store)
        return json.dumps({"success": True, "agent": agent, "task": task})
    except CursorAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_list_agents(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        client = CursorClient()
        limit = int(params.get("limit") or 20)
        data = client.list_agents(limit=limit)
        return json.dumps({"success": True, "agents": data})
    except CursorAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_create_run(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        agent_id = str(params.get("agent_id") or "")
        prompt = str(params.get("prompt") or "").strip()
        if not agent_id or not prompt:
            return json.dumps({"success": False, "error": "agent_id and prompt are required"})
        client = CursorClient()
        store = TaskStore()
        created = client.create_run(agent_id, prompt_text=_build_prompt(prompt, None))
        run = created.get("run") or created
        run_id = run.get("id")
        task_id = params.get("task_id")
        task = store.get_task(str(task_id)) if task_id else store.get_task_by_agent_id(agent_id)
        if task:
            store.update_task(
                task["id"],
                cursor_run_id=run_id,
                status=CursorClient.map_run_status(run.get("status")) or "running",
            )
            task = sync_task_from_run(store.get_task(task["id"]) or {}, client=client, store=store)
        return json.dumps({"success": True, "run": run, "task": task})
    except CursorAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_get_run(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        agent_id = str(params.get("agent_id") or "")
        run_id = str(params.get("run_id") or "")
        if not agent_id or not run_id:
            return json.dumps({"success": False, "error": "agent_id and run_id are required"})
        client = CursorClient()
        run = client.get_run(agent_id, run_id)
        return json.dumps({"success": True, "run": run})
    except CursorAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_cancel_agent(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        store = TaskStore()
        client = CursorClient()
        agent_id = str(params.get("agent_id") or "")
        if not agent_id:
            return json.dumps({"success": False, "error": "agent_id is required"})
        task_id = params.get("task_id")
        task = store.get_task(str(task_id)) if task_id else store.get_task_by_agent_id(agent_id)
        run_id = params.get("run_id") or (task.get("cursor_run_id") if task else None)
        cancel_result = None
        if run_id:
            cancel_result = client.cancel_run(agent_id, str(run_id))
        archive_result = client.archive_agent(agent_id)
        if task:
            store.update_task(task["id"], status="cancelled")
            task = store.get_task(task["id"])
        return json.dumps(
            {
                "success": True,
                "cancel": cancel_result,
                "archive": archive_result,
                "task": task,
            }
        )
    except CursorAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_list_tasks(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    store = TaskStore()
    status = params.get("status")
    limit = int(params.get("limit") or 20)
    tasks = store.list_tasks(status=str(status) if status else None, limit=limit)
    return json.dumps({"success": True, "tasks": tasks})
