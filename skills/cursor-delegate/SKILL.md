---
name: cursor-delegate
description: Delegate repository coding work from Hermes to Cursor Cloud Agents
version: 2.2.0
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

## Independent delegation

Cursor is the only configured coding delegate. Hermes remains the orchestrator; Cursor works asynchronously on the GitHub repository you identify or configure. There is no default organization, project board, or task notebook.
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

1. **Context** — Use the user's request and any repository documentation or issue links they provide.
2. **Repository** — Use `CURSOR_DEFAULT_REPOSITORY` when configured; otherwise use the repository named by the user or `cursor_list_repositories`. Never assume a default organization.
3. **Objective** — Write a short title matching the requested change.
4. **Prompt** — Include detailed requirements, relevant issue links when supplied, and `Do not merge the PR.`
5. **Acceptance criteria** — Convert the user's requirements into a bullet list.
6. **Delegate** — Call `cursor_create_agent` with `auto_create_pr: true` unless the user says otherwise.
7. **Report** — Tell the user delegation started; share `task_id` and Cursor agent id.
8. **Poll** — Use `cursor_get_agent` or `cursor_list_tasks` when the user asks for status.
9. **Close the loop** — Summarize the branch, PR URL, and changes. Comment on an issue only when the user supplied or requested an issue workflow.
10. **Follow-up** — If more work is needed, send `cursor_create_run` with the relevant context preserved.

## Hard rules

- **Never merge pull requests.** The user must approve merges manually.
- **Never delete repositories or force-push** via delegated agents unless the user explicitly requests it.
- **Reference issues only when supplied or requested**; never invent project-board or notebook workflows.
- Prefer `cursor_cancel_agent` if the user asks to stop an in-flight delegation.
- If `CURSOR_MAX_ACTIVE` is reached, tell the user to wait or cancel an existing task.

## Example user request

> Delegate the login fix for owner/repo#123 to Cursor. Do not merge.

Actions:

1. Read the issue and repository guidance supplied by the user.
2. `cursor_create_agent` with a focused objective, the issue link, acceptance criteria, and `Do not merge the PR.`
3. Poll until `finished` or `error`.
4. Summarize the branch, PR URL, and verification results.

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
