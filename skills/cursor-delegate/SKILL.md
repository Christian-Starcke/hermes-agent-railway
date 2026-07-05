---
name: cursor-delegate
description: Delegate repository coding work from Hermes to Cursor Cloud Agents
version: 2.1.0
metadata:
  hermes:
    requires:
      env:
        - CURSOR_API_KEY
    primaryEnv: CURSOR_API_KEY
---

# Cursor Cloud Agent Delegation

You can delegate implementation work to **Cursor Cloud Agents** using the `cursor_cloud` toolset.
Hermes remains the orchestrator; Cursor works asynchronously on GitHub repositories.

## Parallel delegate workers (Cursor and OpenCode)

**Cursor Cloud Agents** (`cursor_cloud`) and **OpenCode** (`opencode_delegate`) are parallel coding delegates. Treat them as equivalent for repo work — same coordination workflow, same hard rules (no auto-merge, issue references, notebook updates).

| Delegate | Tool | Where it runs |
|----------|------|----------------|
| Cursor | `cursor_create_agent` | Cursor Cloud on GitHub repos |
| OpenCode | `opencode_create_task` | Co-located `opencode serve` on Hermes (default) or remote Railway service |

## Workspace-aware delegation

When a **Hermes workspace** is active (`/data/current_workspace.id` or `workspace-orchestrator` skill):

1. Prefer `base_ref` = workspace branch for `cursor_create_agent` (not `main`).
2. Pass `workspace_id` when delegating so `cursor_tasks.workspace_id` links to `workspaces.db`.
3. For OpenCode, set `workspace_hint` to the absolute **worktree path** (not a relative subpath).
4. Use `POST /api/workspaces/{id}/delegate` or `/workspaces` UI when the user wants one-click routing.

If the user names a delegate, use that one. If they say "delegate this" without specifying, pick either based on availability (`CURSOR_MAX_ACTIVE`, `OPENCODE_MAX_ACTIVE`) or ask once. Do not favor one delegate for certain repos or task types.

## Project coordination (read first)

Prism Platform work is tracked in three places:

| Layer | Location | Role |
|-------|----------|------|
| **Issues** | `prism-platform-ap/prism-platform` | System of record |
| **Board** | [Prism Platform Sprint](https://github.com/orgs/prism-platform-ap/projects/1) | Visual sprint view |
| **Notebook** | `prism-platform-ap/prism-playbook` → `TASK_NOTEBOOK.md` | Quick-read summary |

Before every delegation:

1. Read `TASK_NOTEBOOK.md` from `prism-playbook` for current slice, decisions, and blockers.
2. Check open issues on the project board (or `gh issue list --repo prism-platform-ap/prism-platform --label slice-2`).
3. Pick the **most specific open issue** (prefer sub-issues over epics).
4. Include the issue number in the Cursor prompt (e.g. `Closes #8` or `Part of #7`).

After delegation completes:

1. Comment on the linked issue with the PR URL and a short summary.
2. Update `TASK_NOTEBOOK.md` on significant milestones (slice complete, major decision, new blocker).
3. Close sub-issues when acceptance criteria are met; close the epic when all children are done.

## When to delegate to Cursor

Use `cursor_create_agent` when the user wants:

- Code changes across one or more files in a GitHub repository
- Bug fixes, refactors, tests, or feature implementation in a repo
- A branch and/or pull request as the deliverable

Stay in Hermes (do not delegate) for:

- Research, comparisons, architecture notes without repo edits
- Questions about concepts, ops, or configuration advice
- Work that does not require changing a repository

## Required workflow

1. **Context** — Read `TASK_NOTEBOOK.md` and find the relevant open issue(s).
2. **Repository** — Default: `prism-platform-ap/prism-platform`. Use `cursor_list_repositories` if unsure.
3. **Objective** — Short title matching the issue (e.g. `Slice 2.1: Invoice file picker UI`).
4. **Prompt** — Detailed instructions for Cursor. Must include:
   - Issue reference: `Related to prism-platform-ap/prism-platform#N`
   - Link to notebook: `https://github.com/prism-platform-ap/prism-playbook/blob/main/TASK_NOTEBOOK.md`
   - Relevant acceptance criteria from the issue body
   - `Do not merge the PR.`
5. **Acceptance criteria** — Copy from the issue as a bullet list.
6. **Delegate** — Call `cursor_create_agent` with `auto_create_pr: true` unless the user says otherwise.
7. **Report** — Tell the user delegation started; share `task_id` and Cursor agent id.
8. **Poll** — Use `cursor_get_agent` or `cursor_list_tasks` when the user asks for status.
9. **Close the loop** — When finished:
   - Comment on the issue with PR link and summary (via GitHub MCP or `gh issue comment`)
   - Summarize branch, PR URL, and changes for the user
   - Update `TASK_NOTEBOOK.md` if milestone-worthy
10. **Follow-up** — If insufficient, send `cursor_create_run` with issue context preserved.

## Hard rules

- **Never merge pull requests.** The user must approve merges manually.
- **Never delete repositories or force-push** via delegated agents unless the user explicitly requests it.
- **Always reference an issue** when delegating Prism Platform work.
- Prefer `cursor_cancel_agent` if the user asks to stop an in-flight delegation.
- If `CURSOR_MAX_ACTIVE` is reached, tell the user to wait or cancel an existing task.

## Example user request

> Delegate the invoice file picker for Slice 2 to Cursor. Do not merge.

Actions:

1. Read `TASK_NOTEBOOK.md` — confirm Slice 2 is active.
2. Find open sub-issue for file picker (e.g. `#8`).
3. `cursor_create_agent` with objective `Slice 2.1: Invoice file picker UI`, prompt referencing `#8` and notebook URL, acceptance criteria from issue.
4. Poll until `finished` or `error`.
5. Comment on `#8` with PR link; update notebook if scope item completed.

## Environment

- `CURSOR_API_KEY` — required (Cursor Dashboard → API Keys)
- `CURSOR_DEFAULT_REPOSITORY` — optional default `owner/repo`
- `CURSOR_WEBHOOK_SECRET` — verifies inbound webhooks at `/webhooks/cursor`
- `CURSOR_MAX_ACTIVE` — max concurrent delegations (default 3)

## Tool discovery (important on Railway)

Hermes loads plugins at **process startup**. Plugin source on disk (`/data/.hermes/plugins/cursor-cloud/`) is synced from the Docker image on **every container boot** — edits made only on the volume are overwritten on restart.

### Deferred tools (Tool Search)

With many MCP servers attached (Firecrawl, GitHub, n8n, Supabase, etc.), Hermes **defers** plugin tools behind:

- `tool_search(query)` — find tools by name/description
- `tool_describe(name)` — load full schema
- `tool_call(name, arguments)` — invoke the tool

All `cursor_cloud` tools (including `cursor_list_models`, `cursor_get_account`) are usually **deferred**, not directly visible to the model. That is normal.

To use a Cursor tool when deferred:

1. `tool_search("cursor list models")` or `tool_search("cursor account")`
2. `tool_describe("cursor_list_models")` if needed
3. `tool_call("cursor_list_models", {})`

Do **not** assume a tool is missing just because it is not in the direct tool list.

### After plugin updates

If new Cursor tools were added but do not appear:

1. Confirm deploy: `grep cursor_list_models /data/.hermes/plugins/cursor-cloud/__init__.py` and `version: "1.1.0"` in `plugin.yaml`
2. **Restart Hermes WebUI** (from `/tui`): `kill $(cat /data/.hermes/webui/server.pid)` — the entrypoint watchdog respawns it
3. **Start a new WebUI chat session** — old sessions can retain stale tool metadata
4. Ensure session toolsets include **`cursor_cloud`** (session settings or `/toolsets`)
5. Verify: `hermes plugins list` from `/tui` — `cursor-cloud` should be **enabled**

### Quick smoke test

Ask the user to run in a **new session**:

> Use `tool_search` to find `cursor_get_account`, then `tool_call` it. Report the API key metadata (redact secrets).
