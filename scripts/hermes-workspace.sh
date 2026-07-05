#!/usr/bin/env bash
# Hermes workspace CLI — git worktree isolation for Conductor-style tasks.
set -euo pipefail

export HERMES_HOME="${HERMES_HOME:-/data}"
export PYTHONPATH="/opt/hermes-railway:${PYTHONPATH:-}"

CMD="${1:-}"
shift || true

exec python3 - "$CMD" "$@" <<'PY'
import json
import sys

from admin.workspace_manager import (
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

cmd = sys.argv[1] if len(sys.argv) > 1 else ""
args = sys.argv[2:]


def emit(payload):
    print(json.dumps(payload, indent=2))


try:
    if cmd == "create":
        name = args[0] if args else ""
        repo_root = "."
        base_ref = "main"
        activate = False
        for arg in args[1:]:
            if arg.startswith("--repo="):
                repo_root = arg.split("=", 1)[1]
            elif arg.startswith("--base="):
                base_ref = arg.split("=", 1)[1]
            elif arg == "--activate":
                activate = True
        ws = create_workspace(name=name, repo_root=repo_root, base_ref=base_ref)
        if activate:
            activate_workspace(ws["id"])
        emit({"success": True, "workspace": ws})
    elif cmd == "list":
        emit({"success": True, "workspaces": list_workspaces(), "current": get_current_workspace_id()})
    elif cmd == "show":
        ws_id = args[0] if args else get_current_workspace_id()
        if not ws_id:
            raise WorkspaceError("workspace id required")
        ws = get_workspace(ws_id)
        if not ws:
            raise WorkspaceError(f"not found: {ws_id}")
        emit({"success": True, "workspace": ws})
    elif cmd == "activate":
        ws_id = args[0] if args else ""
        if not ws_id:
            raise WorkspaceError("workspace id required")
        emit({"success": True, "workspace": activate_workspace(ws_id)})
    elif cmd == "deactivate":
        deactivate_current()
        emit({"success": True})
    elif cmd == "current":
        emit(
            {
                "success": True,
                "current_workspace_id": get_current_workspace_id(),
                "workspace": get_current_workspace(),
            }
        )
    elif cmd == "diff":
        ws_id = args[0] if args else get_current_workspace_id()
        if not ws_id:
            raise WorkspaceError("workspace id required")
        emit({"success": True, "diff": get_diff(ws_id)})
    elif cmd == "pr":
        ws_id = args[0] if args else get_current_workspace_id()
        if not ws_id:
            raise WorkspaceError("workspace id required")
        emit({"success": True, **create_pr(ws_id)})
    elif cmd == "archive":
        ws_id = args[0] if args else get_current_workspace_id()
        if not ws_id:
            raise WorkspaceError("workspace id required")
        emit({"success": True, "workspace": archive_workspace(ws_id)})
    else:
        print(
            "Usage: hermes-workspace.sh <create|list|show|activate|deactivate|current|diff|pr|archive> [args]",
            file=sys.stderr,
        )
        sys.exit(2)
except WorkspaceError as exc:
    emit({"success": False, "error": str(exc)})
    sys.exit(1)
PY
