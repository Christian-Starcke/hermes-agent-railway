"""Git worktree workspace lifecycle for Hermes Railway."""

from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any

from .workspace_store import WorkspaceStore

CURRENT_WORKSPACE_FILE = Path(os.environ.get("HERMES_HOME", "/data")) / "current_workspace.id"
WORKSPACE_META_FILENAME = ".hermes-workspace.json"


class WorkspaceError(Exception):
    pass


def workspace_root() -> Path:
    home = Path(os.environ.get("HERMES_HOME", "/data")) / "home"
    return Path(os.environ.get("WORKSPACE_ROOT", str(home / "workspace")))


def workspaces_base() -> Path:
    return Path(os.environ.get("HERMES_WORKSPACES_BASE", str(workspace_root().parent / ".hermes-workspaces")))


def max_active_workspaces() -> int:
    raw = os.environ.get("WORKSPACE_MAX_ACTIVE", "5").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 5


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:48] or "workspace"


def _repo_slug(repo_root: str) -> str:
    normalized = repo_root.strip().strip("/")
    if not normalized or normalized == ".":
        return "n8n-as-code"
    return Path(normalized).name


def _abs_repo_root(repo_root: str) -> Path:
    root = workspace_root()
    normalized = repo_root.strip().strip("/") or "."
    if normalized == ".":
        candidate = root
    else:
        candidate = root / normalized
    git_dir = candidate / ".git"
    if not git_dir.exists():
        raise WorkspaceError(f"repo_root has no .git: {candidate}")
    return candidate.resolve()


def _run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise WorkspaceError(f"git {' '.join(args)} failed: {stderr}")
    return result


def get_current_workspace_id() -> str | None:
    try:
        value = CURRENT_WORKSPACE_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    return value or None


def get_current_workspace(store: WorkspaceStore | None = None) -> dict[str, Any] | None:
    workspace_id = get_current_workspace_id()
    if not workspace_id:
        return None
    store = store or WorkspaceStore()
    workspace = store.get_workspace(workspace_id)
    if not workspace or workspace.get("status") == "archived":
        return None
    return workspace


def activate_workspace(workspace_id: str, store: WorkspaceStore | None = None) -> dict[str, Any]:
    store = store or WorkspaceStore()
    workspace = store.get_workspace(workspace_id)
    if not workspace:
        raise WorkspaceError(f"workspace not found: {workspace_id}")
    if workspace.get("status") == "archived":
        raise WorkspaceError("cannot activate archived workspace")
    worktree = Path(workspace["worktree_path"])
    if not worktree.is_dir():
        raise WorkspaceError(f"worktree missing: {worktree}")
    CURRENT_WORKSPACE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CURRENT_WORKSPACE_FILE.write_text(workspace_id, encoding="utf-8")
    return workspace


def deactivate_current() -> None:
    if CURRENT_WORKSPACE_FILE.exists():
        CURRENT_WORKSPACE_FILE.unlink()


def create_workspace(
    *,
    name: str,
    repo_root: str = ".",
    base_ref: str = "main",
    issue_url: str | None = None,
    agent_backend: str = "hermes",
    store: WorkspaceStore | None = None,
) -> dict[str, Any]:
    store = store or WorkspaceStore()
    if store.count_active() >= max_active_workspaces():
        raise WorkspaceError(f"too many active workspaces (max {max_active_workspaces()})")

    name = name.strip()
    if not name:
        raise WorkspaceError("name is required")

    abs_repo = _abs_repo_root(repo_root)
    slug = _slugify(name)
    short_id = uuid.uuid4().hex[:8]
    branch = f"wip/{slug}-{short_id}"
    repo_key = _repo_slug(repo_root)
    worktree_path = (workspaces_base() / repo_key / f"ws-{short_id}").resolve()
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    if worktree_path.exists():
        raise WorkspaceError(f"worktree path already exists: {worktree_path}")

    _run_git(abs_repo, "fetch", "origin", base_ref, check=False)
    _run_git(abs_repo, "worktree", "add", "-b", branch, str(worktree_path), base_ref)

    workspace = store.create_workspace(
        name=name,
        branch=branch,
        worktree_path=str(worktree_path),
        repo_root=repo_root.strip().strip("/") or ".",
        base_ref=base_ref,
        agent_backend=agent_backend,
        issue_url=issue_url,
    )

    meta = {
        "id": workspace["id"],
        "name": name,
        "branch": branch,
        "base_ref": base_ref,
        "repo_root": workspace["repo_root"],
        "agent_backend": agent_backend,
        "issue_url": issue_url,
    }
    (worktree_path / WORKSPACE_META_FILENAME).write_text(
        json.dumps(meta, indent=2),
        encoding="utf-8",
    )
    return workspace


def list_workspaces(**kwargs: Any) -> list[dict[str, Any]]:
    store = WorkspaceStore()
    return store.list_workspaces(**kwargs)


def get_workspace(workspace_id: str) -> dict[str, Any] | None:
    return WorkspaceStore().get_workspace(workspace_id)


def archive_workspace(workspace_id: str, store: WorkspaceStore | None = None) -> dict[str, Any]:
    store = store or WorkspaceStore()
    workspace = store.get_workspace(workspace_id)
    if not workspace:
        raise WorkspaceError(f"workspace not found: {workspace_id}")
    if workspace.get("status") == "archived":
        return workspace

    worktree = Path(workspace["worktree_path"])
    abs_repo = _abs_repo_root(workspace["repo_root"])
    if worktree.is_dir():
        _run_git(abs_repo, "worktree", "remove", "--force", str(worktree), check=False)
    _run_git(abs_repo, "worktree", "prune", check=False)

    if get_current_workspace_id() == workspace_id:
        deactivate_current()

    return store.update_workspace(workspace_id, status="archived") or workspace


def get_diff(workspace_id: str, store: WorkspaceStore | None = None) -> dict[str, Any]:
    store = store or WorkspaceStore()
    workspace = store.get_workspace(workspace_id)
    if not workspace:
        raise WorkspaceError(f"workspace not found: {workspace_id}")

    worktree = Path(workspace["worktree_path"])
    base_ref = workspace.get("base_ref") or "main"
    name_status = _run_git(worktree, "diff", "--name-status", f"{base_ref}...HEAD", check=False)
    patch = _run_git(worktree, "diff", f"{base_ref}...HEAD", check=False)
    stat = _run_git(worktree, "diff", "--stat", f"{base_ref}...HEAD", check=False)

    files: list[dict[str, str]] = []
    for line in (name_status.stdout or "").splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2:
            files.append({"status": parts[0].strip(), "path": parts[1].strip()})

    return {
        "workspace_id": workspace_id,
        "branch": workspace.get("branch"),
        "base_ref": base_ref,
        "files": files,
        "stat": (stat.stdout or "").strip(),
        "patch": patch.stdout or "",
    }


def create_pr(
    workspace_id: str,
    *,
    title: str | None = None,
    body: str | None = None,
    store: WorkspaceStore | None = None,
) -> dict[str, Any]:
    store = store or WorkspaceStore()
    workspace = store.get_workspace(workspace_id)
    if not workspace:
        raise WorkspaceError(f"workspace not found: {workspace_id}")

    worktree = Path(workspace["worktree_path"])
    branch = workspace["branch"]
    pr_title = title or workspace.get("name") or branch
    pr_body = body or f"Workspace {workspace_id}\n\nBranch: {branch}"
    if workspace.get("issue_url"):
        pr_body += f"\n\nRelated: {workspace['issue_url']}"

    push = subprocess.run(
        ["git", "-C", str(worktree), "push", "-u", "origin", branch],
        capture_output=True,
        text=True,
        check=False,
    )
    if push.returncode != 0:
        raise WorkspaceError(f"git push failed: {(push.stderr or push.stdout or '').strip()}")

    gh = subprocess.run(
        [
            "gh",
            "pr",
            "create",
            "--title",
            pr_title,
            "--body",
            pr_body,
            "--head",
            branch,
        ],
        cwd=str(worktree),
        capture_output=True,
        text=True,
        check=False,
    )
    if gh.returncode != 0:
        raise WorkspaceError(f"gh pr create failed: {(gh.stderr or gh.stdout or '').strip()}")

    pr_url = (gh.stdout or "").strip()
    updated = store.update_workspace(workspace_id, pr_url=pr_url, status="review")
    return {"workspace": updated, "pr_url": pr_url}


def sync_workspace_from_cursor_task(
    task: dict[str, Any],
    *,
    mapped_status: str,
    pr_url: str | None = None,
    branch_name: str | None = None,
    store: WorkspaceStore | None = None,
) -> dict[str, Any] | None:
    """Update linked workspace when a Cursor delegation completes."""
    store = store or WorkspaceStore()
    workspace_id = task.get("workspace_id")
    workspace = None
    if workspace_id:
        workspace = store.get_workspace(str(workspace_id))
    if not workspace:
        workspace = store.get_workspace_by_cursor_task(str(task.get("id") or ""))
    if not workspace:
        return None

    updates: dict[str, Any] = {}
    if pr_url:
        updates["pr_url"] = pr_url
    if branch_name:
        updates["branch"] = branch_name
    if mapped_status == "finished":
        updates["status"] = "review"
    elif mapped_status in {"error", "cancelled"}:
        updates["status"] = "active"
    if updates:
        return store.update_workspace(workspace["id"], **updates)
    return workspace


def prune_orphan_worktrees_on_boot() -> None:
    """Best-effort cleanup for stale worktree registrations."""
    root = workspace_root()
    if not (root / ".git").exists():
        return
    _run_git(root, "worktree", "prune", check=False)
    for child in workspaces_base().glob("*/*"):
        if child.is_dir() and not (child / WORKSPACE_META_FILENAME).exists():
            continue
