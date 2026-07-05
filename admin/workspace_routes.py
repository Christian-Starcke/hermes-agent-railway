"""HTTP routes for Hermes workspace management."""

from __future__ import annotations

import json
from pathlib import Path

from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from .auth import is_authenticated
from .workspace_manager import (
    WorkspaceError,
    activate_workspace,
    archive_workspace,
    create_pr,
    create_workspace,
    deactivate_current,
    get_current_workspace,
    get_current_workspace_id,
    get_diff,
    get_workspace,
    list_workspaces,
)
from .workspace_router import delegate_workspace_to_cursor, delegate_workspace_to_opencode, set_agent_backend
from .workspace_store import WorkspaceStore

TEMPLATES = Path(__file__).parent / "templates"
STATIC = Path(__file__).parent / "static"


async def _require_auth(request: Request) -> JSONResponse | None:
    if not await is_authenticated(request):
        return JSONResponse({"success": False, "error": "unauthorized"}, status_code=401)
    return None


async def workspaces_page(request: Request):
    if not await is_authenticated(request):
        return RedirectResponse("/login?next=/workspaces", status_code=303)
    return HTMLResponse((TEMPLATES / "workspaces.html").read_text(encoding="utf-8"))


async def workspaces_static(request: Request):
    filename = request.path_params["filename"]
    if filename not in {"workspaces.js", "workspaces.css"}:
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(STATIC / filename)


async def api_list_workspaces(request: Request):
    denied = await _require_auth(request)
    if denied:
        return denied
    include_archived = request.query_params.get("include_archived") == "1"
    items = list_workspaces(include_archived=include_archived)
    current_id = get_current_workspace_id()
    return JSONResponse({"success": True, "workspaces": items, "current_workspace_id": current_id})


async def api_create_workspace(request: Request):
    denied = await _require_auth(request)
    if denied:
        return denied
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"success": False, "error": "invalid json"}, status_code=400)

    try:
        workspace = create_workspace(
            name=str(body.get("name") or ""),
            repo_root=str(body.get("repo_root") or "."),
            base_ref=str(body.get("base_ref") or "main"),
            issue_url=str(body.get("issue_url")).strip() if body.get("issue_url") else None,
            agent_backend=str(body.get("agent_backend") or "hermes"),
        )
        if body.get("activate"):
            activate_workspace(workspace["id"])
        return JSONResponse({"success": True, "workspace": workspace}, status_code=201)
    except WorkspaceError as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=400)


async def api_get_workspace(request: Request):
    denied = await _require_auth(request)
    if denied:
        return denied
    workspace_id = request.path_params["workspace_id"]
    workspace = get_workspace(workspace_id)
    if not workspace:
        return JSONResponse({"success": False, "error": "not found"}, status_code=404)
    return JSONResponse({"success": True, "workspace": workspace})


async def api_patch_workspace(request: Request):
    denied = await _require_auth(request)
    if denied:
        return denied
    workspace_id = request.path_params["workspace_id"]
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"success": False, "error": "invalid json"}, status_code=400)

    store = WorkspaceStore()
    workspace = store.get_workspace(workspace_id)
    if not workspace:
        return JSONResponse({"success": False, "error": "not found"}, status_code=404)

    try:
        if "agent_backend" in body:
            workspace = set_agent_backend(workspace_id, str(body["agent_backend"]), store=store)
        updates = {}
        for key in ("status", "hermes_session_id", "issue_url", "pr_url"):
            if key in body:
                updates[key] = body[key]
        if updates:
            workspace = store.update_workspace(workspace_id, **updates) or workspace
        return JSONResponse({"success": True, "workspace": workspace})
    except WorkspaceError as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=400)


async def api_workspace_diff(request: Request):
    denied = await _require_auth(request)
    if denied:
        return denied
    workspace_id = request.path_params["workspace_id"]
    try:
        diff = get_diff(workspace_id)
        return JSONResponse({"success": True, "diff": diff})
    except WorkspaceError as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=400)


async def api_workspace_pr(request: Request):
    denied = await _require_auth(request)
    if denied:
        return denied
    workspace_id = request.path_params["workspace_id"]
    body = {}
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return JSONResponse({"success": False, "error": "invalid json"}, status_code=400)
    try:
        result = create_pr(
            workspace_id,
            title=str(body.get("title")).strip() if body.get("title") else None,
            body=str(body.get("body")).strip() if body.get("body") else None,
        )
        return JSONResponse({"success": True, **result})
    except WorkspaceError as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=400)


async def api_workspace_archive(request: Request):
    denied = await _require_auth(request)
    if denied:
        return denied
    workspace_id = request.path_params["workspace_id"]
    try:
        workspace = archive_workspace(workspace_id)
        return JSONResponse({"success": True, "workspace": workspace})
    except WorkspaceError as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=400)


async def api_activate_workspace(request: Request):
    denied = await _require_auth(request)
    if denied:
        return denied
    workspace_id = request.path_params["workspace_id"]
    try:
        workspace = activate_workspace(workspace_id)
        return JSONResponse({"success": True, "workspace": workspace})
    except WorkspaceError as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=400)


async def api_deactivate_current(request: Request):
    denied = await _require_auth(request)
    if denied:
        return denied
    deactivate_current()
    return JSONResponse({"success": True})


async def api_current_workspace(request: Request):
    denied = await _require_auth(request)
    if denied:
        return denied
    workspace = get_current_workspace()
    return JSONResponse(
        {
            "success": True,
            "current_workspace_id": get_current_workspace_id(),
            "workspace": workspace,
        }
    )


async def api_chat_link(request: Request):
    denied = await _require_auth(request)
    if denied:
        return denied
    workspace_id = request.path_params["workspace_id"]
    workspace = get_workspace(workspace_id)
    if not workspace:
        return JSONResponse({"success": False, "error": "not found"}, status_code=404)
    activate_workspace(workspace_id)
    return JSONResponse(
        {
            "success": True,
            "workspace_id": workspace_id,
            "chat_url": "/",
            "note": "Open WebUI chat; workspace-orchestrator skill reads /data/current_workspace.id",
        }
    )


async def api_delegate_workspace(request: Request):
    denied = await _require_auth(request)
    if denied:
        return denied
    workspace_id = request.path_params["workspace_id"]
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"success": False, "error": "invalid json"}, status_code=400)

    backend = str(body.get("backend") or "").strip().lower()
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return JSONResponse({"success": False, "error": "prompt is required"}, status_code=400)

    try:
        if backend == "cursor":
            result = delegate_workspace_to_cursor(
                workspace_id,
                prompt=prompt,
                objective=str(body.get("objective") or "").strip() or None,
                repository=str(body.get("repository") or "").strip() or None,
            )
        elif backend == "opencode":
            result = delegate_workspace_to_opencode(
                workspace_id,
                prompt=prompt,
                objective=str(body.get("objective") or "").strip() or None,
            )
        else:
            return JSONResponse({"success": False, "error": "backend must be cursor or opencode"}, status_code=400)
        return JSONResponse({"success": True, **result})
    except WorkspaceError as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=400)


def workspace_routes():
    from starlette.routing import Route

    return [
        Route("/workspaces", workspaces_page, methods=["GET"]),
        Route("/static/{filename}", workspaces_static, methods=["GET"]),
        Route("/api/workspaces", api_list_workspaces, methods=["GET"]),
        Route("/api/workspaces", api_create_workspace, methods=["POST"]),
        Route("/api/workspaces/current", api_current_workspace, methods=["GET"]),
        Route("/api/workspaces/current", api_deactivate_current, methods=["DELETE"]),
        Route("/api/workspaces/{workspace_id}", api_get_workspace, methods=["GET"]),
        Route("/api/workspaces/{workspace_id}", api_patch_workspace, methods=["PATCH"]),
        Route("/api/workspaces/{workspace_id}/diff", api_workspace_diff, methods=["GET"]),
        Route("/api/workspaces/{workspace_id}/pr", api_workspace_pr, methods=["POST"]),
        Route("/api/workspaces/{workspace_id}/archive", api_workspace_archive, methods=["POST"]),
        Route("/api/workspaces/{workspace_id}/activate", api_activate_workspace, methods=["PUT"]),
        Route("/api/workspaces/{workspace_id}/chat-link", api_chat_link, methods=["GET"]),
        Route("/api/workspaces/{workspace_id}/delegate", api_delegate_workspace, methods=["POST"]),
    ]
