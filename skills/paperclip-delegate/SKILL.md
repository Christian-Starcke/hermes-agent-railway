---
name: paperclip-delegate
description: Delegate repository coding work from Hermes to Paperclip workers (Cursor Cloud, etc.)
version: 1.1.0
metadata:
  hermes:
    requires:
      env:
        - PAPERCLIP_API_TOKEN
        - PAPERCLIP_BASE_URL
        - PAPERCLIP_COMPANY_ID
        - PAPERCLIP_DELEGATION_MODE
    primaryEnv: PAPERCLIP_API_TOKEN
---

# Paperclip Delegation (Hermes → Paperclip → Workers)

When `PAPERCLIP_DELEGATION_MODE=paperclip`, delegate implementation work through **Paperclip** using the `paperclip` toolset.
Hermes creates and assigns issues; Paperclip heartbeats wake worker agents (e.g. Cursor Cloud via `cursor_cloud` adapter).

**Do not call `cursor_create_agent` in Paperclip mode** — that bypasses the work queue and creates split state.

## Project coordination (Prism Platform)

For `prism-platform-ap` work, align with GitHub Issues + board + notebook (same as `cursor-delegate` v2):

- **Issues**: `prism-platform-ap/prism-platform` (system of record)
- **Board**: [Prism Platform Sprint](https://github.com/orgs/prism-platform-ap/projects/1)
- **Notebook**: `prism-platform-ap/prism-playbook` → `TASK_NOTEBOOK.md`

Before delegating: read the notebook, pick the most specific open GitHub issue, reference it in the Paperclip prompt.
After completion: comment on the GitHub issue with the PR link; update the notebook on milestones.

## When to delegate via Paperclip

Use `paperclip_delegate_coding_task` when the user wants:

- Code changes across one or more files in a GitHub repository
- Bug fixes, refactors, tests, or feature implementation in a repo
- A tracked issue (`PAP-xx`) and durable job status on the Paperclip board
- A branch and/or pull request as the deliverable

Stay in Hermes (do not delegate) for:

- Research, comparisons, architecture notes without repo edits
- Questions about concepts, ops, or configuration advice
- Work that does not require changing a repository

## Required workflow

1. Confirm `PAPERCLIP_DELEGATION_MODE=paperclip` is active. If not, use the `cursor-delegate` skill instead.
2. Clarify the **repository** (`owner/repo` or full GitHub URL).
3. Write a crisp **objective** (short title) and a detailed **prompt** for the worker agent.
4. Include **acceptance_criteria** as a bullet list when the user gives requirements.
5. Call `paperclip_delegate_coding_task` with objective, prompt, repository, and optional criteria.
6. Tell the user delegation started; share the Paperclip issue id (`PAP-xx` or UUID).
7. On status requests, use `paperclip_get_issue` or `paperclip_list_issues`.
8. When finished, summarize status, **branch**, **PR URL** (from issue work products/comments), and offer review. **Never merge PRs.**
9. For follow-up instructions on the same issue, use `paperclip_add_comment` or create a linked sub-issue via `paperclip_create_issue` with `parent_id`.
10. To stop work, use `paperclip_cancel_issue`.

## Hard rules

- **Never merge pull requests.** The user must approve merges manually.
- **Never delete repositories or force-push** via delegated agents unless the user explicitly requests it.
- In Paperclip mode, **never** call `cursor_create_agent`, `cursor_create_run`, or other `cursor_cloud` delegation tools.
- Prefer `paperclip_cancel_issue` if the user asks to stop in-flight work.

## Example user request

> Fix invoice upload failures in christian/prism. Delegate via Paperclip. Do not merge.

Actions:

1. `paperclip_delegate_coding_task` with objective, detailed prompt, acceptance criteria, repository `christian/prism`.
2. Report issue id (e.g. `PAP-42`) and that Paperclip will wake the Cursor worker on heartbeat.
3. On follow-up: `paperclip_get_issue` with `PAP-42` until status is `done` or `cancelled`.
4. Report PR link and summary from issue details; remind user to review before merging.

## Environment

- `PAPERCLIP_BASE_URL` — Paperclip API base (use Railway private domain from Hermes)
- `PAPERCLIP_API_TOKEN` — Board API token from Paperclip setup
- `PAPERCLIP_COMPANY_ID` — Company UUID
- `PAPERCLIP_DEFAULT_AGENT_ID` — Default Cursor worker agent UUID
- `PAPERCLIP_DELEGATION_MODE` — Must be `paperclip` for this skill
- `PAPERCLIP_AGENT_MAP` — Optional `owner/repo:agent-uuid,...` for multi-repo routing
- `PAPERCLIP_ALLOWED_REPOS` — Optional comma-separated allowlist
- `PAPERCLIP_DEFAULT_REPOSITORY` — Optional default `owner/repo`

## Tool discovery (Railway)

Hermes loads plugins at **process startup**. Plugin source on disk is synced from the Docker image on every container boot.

The `paperclip_*` tools are **native plugin tools** in the **`paperclip` toolset** — not MCP deferred tools. Do **not** use `tool_search` for them.

When `PAPERCLIP_API_TOKEN` is set, Railway `entrypoint.sh` enables both:

- `plugins.enabled: [paperclip, ...]`
- `toolsets: [..., paperclip]`

Toolset changes apply on a **new WebUI session** (`/reset` or fresh chat). They do not appear mid-conversation.

### Quick smoke test

In a **new session**, call `paperclip_health` directly (or `paperclip_list_agents`). Report whether Paperclip is reachable.
