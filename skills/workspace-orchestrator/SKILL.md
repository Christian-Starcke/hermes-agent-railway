---
name: workspace-orchestrator
description: Manage git worktree workspaces for isolated Hermes coding tasks
---

# Workspace Orchestrator

Hermes supports **Conductor-style workspaces**: isolated git worktrees under `/data/home/.hermes-workspaces/` with a shared activation file at `/data/current_workspace.id`.

## At the start of every turn

1. Read `/data/current_workspace.id` if it exists.
2. If set, load the workspace from `/data/workspaces.db` (or `GET /api/workspaces/{id}`).
3. **All file edits and terminal commands** for repo work must use `worktree_path` as the working directory.
4. Do not modify the main checkout at `/data/home/workspace` when a workspace is active.

## Creating workspaces

Prefer the workspace API or CLI:

```bash
bash /opt/hermes-railway/scripts/hermes-workspace.sh create "Fix invoice workflow" --repo=. --activate
```

Or `POST /api/workspaces` with `{ "name", "repo_root", "base_ref", "activate": true }`.

`repo_root` must point at a directory with `.git`:

- `.` — n8n-as-code at workspace root
- `prism-platform-ap/prism-platform` — prism-platform repo
- `prism-platform-ap/n8n-as-code` — nested n8n-as-code clone

## Agent backends per workspace

| Backend | When to use | How |
|---------|-------------|-----|
| `hermes` | Default — orchestration, MCP, quick edits | Activate workspace; work in `worktree_path` |
| `opencode` | Heavy refactors on same files | `opencode_create_task` with absolute `worktree_path` as `workspace_hint`, or `POST /api/workspaces/{id}/delegate` with `backend: opencode` |
| `cursor` | Cloud sandbox, large parallel work | `cursor_create_agent` with `starting_ref` = workspace branch, pass `workspace_id` in context; or delegate API with `backend: cursor` |

## Hard rules

- **Never auto-merge PRs** — user reviews and merges manually.
- Link GitHub issues in PR bodies when `issue_url` is set.
- Archive workspaces when done: `hermes-workspace.sh archive <id>` or `POST /api/workspaces/{id}/archive`.
- Max active workspaces: `WORKSPACE_MAX_ACTIVE` (default 5).

## Delegation with workspace_id

When calling `cursor_create_agent` or `opencode_create_task` for workspace work, ensure the workspace row is updated with `cursor_task_id` / `opencode_task_id`. The Cursor webhook updates workspace `status` to `review` when the agent finishes.

## UI

- Workspace manager: `/workspaces` on the Hermes WebUI domain
- Activate a workspace before opening chat at `/` so this skill picks up the correct worktree
