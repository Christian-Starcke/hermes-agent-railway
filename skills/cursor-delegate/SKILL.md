---
name: cursor-delegate
description: Delegate repository coding work from Hermes to Cursor Cloud Agents
version: 1.0.0
metadata:
  hermes:
    requires:
      env:
        - CURSOR_API_KEY
    primaryEnv: CURSOR_API_KEY
---

# Cursor Cloud Agent Delegation

> **Delegation mode:** If `PAPERCLIP_DELEGATION_MODE=paperclip`, use the **`paperclip-delegate`** skill and `paperclip_delegate_coding_task` instead. Do not call `cursor_create_agent` in Paperclip mode.

You can delegate implementation work to **Cursor Cloud Agents** using the `cursor_cloud` toolset (direct Hermes → Cursor path).
Hermes remains the orchestrator; Cursor works asynchronously on GitHub repositories.

This skill applies when `PAPERCLIP_DELEGATION_MODE` is unset, `direct`, or any value other than `paperclip`.

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

1. Clarify the **repository** (`owner/repo` or full GitHub URL). Use `cursor_list_repositories` if unsure.
2. Write a crisp **objective** (short title) and a detailed **prompt** for Cursor.
3. Include **acceptance_criteria** as a bullet list when the user gives requirements.
4. Call `cursor_create_agent` with `auto_create_pr: true` unless the user says otherwise.
5. Tell the user delegation started; share the local `task_id` and Cursor agent id when available.
6. Poll progress with `cursor_get_agent` or `cursor_list_tasks` when the user asks for status.
7. When finished, summarize **branch**, **PR URL**, and **summary**. Offer to review the diff with `gh` if available.
8. If the result is insufficient, send a follow-up with `cursor_create_run`.

## Hard rules

- **Never merge pull requests.** The user must approve merges manually.
- **Never delete repositories or force-push** via delegated agents unless the user explicitly requests it.
- Prefer `cursor_cancel_agent` if the user asks to stop an in-flight delegation.
- If `CURSOR_MAX_ACTIVE` is reached, tell the user to wait or cancel an existing task.

## Example user request

> Fix invoice upload failures in christian/prism. Delegate to Cursor. Do not merge.

Actions:

1. `cursor_create_agent` with objective, detailed prompt, acceptance criteria, repository `christian/prism`.
2. Periodically `cursor_get_agent` / `cursor_poll_pending_tasks` until status is `finished` or `error`.
3. Report PR link and summary; remind user to review before merging.

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
4. Ensure session toolsets include **`cursor_cloud`** (session settings 🔧 or `/toolsets`)
5. Verify: `hermes plugins list` from `/tui` — `cursor-cloud` should be **enabled**

### Quick smoke test

Ask the user to run in a **new session**:

> Use `tool_search` to find `cursor_get_account`, then `tool_call` it. Report the API key metadata (redact secrets).
