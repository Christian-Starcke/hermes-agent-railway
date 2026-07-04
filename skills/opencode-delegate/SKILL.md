---
name: opencode-delegate
description: Delegate coding work from Hermes to OpenCode on Railway
version: 1.0.0
metadata:
  hermes:
    requires:
      env:
        - OPENCODE_SERVER_URL
        - OPENCODE_SERVER_PASSWORD
    primaryEnv: OPENCODE_SERVER_URL
---

# OpenCode Delegation

You can delegate implementation work to **OpenCode** on Railway using the `opencode_delegate` toolset.
Hermes remains the orchestrator; OpenCode runs asynchronously on the Railway-hosted coding server.

## OpenCode vs Cursor

| Use **OpenCode** (`opencode_create_task`) | Use **Cursor** (`cursor_create_agent`) |
|-------------------------------------------|----------------------------------------|
| n8n workflow edits, Railway ops, infra scripts | GitHub repo feature work with branch + PR |
| Fast iteration on repos under `/data/workspace` | Cloud-isolated repo agents with Cursor's native PR flow |
| Shell/file tools in persistent OpenCode volume | Tasks where Cursor's GitHub integration is preferred |

When unsure, prefer **Cursor** for user-facing product code in `prism-platform` and **OpenCode** for automation/ops repos (`n8n-as-code`, playbook scripts).

## Project coordination (read first)

Prism Platform work is tracked in three places:

| Layer | Location | Role |
|-------|----------|------|
| **Issues** | `prism-platform-ap/prism-platform` | System of record |
| **Board** | [Prism Platform Sprint](https://github.com/orgs/prism-platform-ap/projects/1) | Visual sprint view |
| **Notebook** | `prism-platform-ap/prism-playbook` → `TASK_NOTEBOOK.md` | Quick-read summary |

Before every delegation:

1. Read `TASK_NOTEBOOK.md` from `prism-playbook` for current slice, decisions, and blockers.
2. Check open issues when the task ties to Prism Platform.
3. Include issue numbers in prompts when relevant.

After delegation completes:

1. Comment on linked issues with a summary (via GitHub MCP or `gh issue comment`).
2. Update `TASK_NOTEBOOK.md` on significant milestones.

## Required workflow

1. **Context** — Read `TASK_NOTEBOOK.md` and find relevant open issue(s) when applicable.
2. **Workspace** — Set `workspace_hint` to the repo folder under `/data/workspace` (e.g. `n8n-as-code`, `prism-platform`).
3. **Objective** — Short title matching the task.
4. **Prompt** — Detailed instructions. Must include:
   - Issue reference when applicable
   - Link to notebook when Prism work
   - Acceptance criteria
   - `Do not merge the PR.`
5. **Delegate** — Call `opencode_create_task` with `agent: build` unless planning-only.
6. **Report** — Tell the user delegation started; share `task_id` and OpenCode `session_id`.
7. **Poll** — Use `opencode_get_task` or `opencode_poll_pending_tasks` when the user asks for status.
8. **Follow-up** — Use `opencode_send_message` if more instructions are needed.
9. **Abort** — Use `opencode_abort_task` if the user asks to stop.

## Hard rules

- **Never merge pull requests.** The user must approve merges manually.
- **Never delete repositories or force-push** unless the user explicitly requests it.
- Prefer referencing GitHub issues for Prism Platform work.
- If `OPENCODE_MAX_ACTIVE` is reached, tell the user to wait or cancel an existing task.

## Environment

- `OPENCODE_SERVER_URL` — OpenCode Railway public URL (e.g. `https://opencode-production-....up.railway.app`)
- `OPENCODE_SERVER_PASSWORD` — HTTP Basic Auth password (username default: `opencode`)
- `OPENCODE_DEFAULT_AGENT` — default `build`
- `OPENCODE_DEFAULT_MODEL` — e.g. `openrouter/anthropic/claude-sonnet-4`
- `OPENCODE_MAX_ACTIVE` — max concurrent delegations (default 3)

## Tool discovery (important on Railway)

Hermes loads plugins at **process startup**. Plugin source on disk (`/data/.hermes/plugins/opencode-delegate/`) is synced from the Docker image on **every container boot**.

### Deferred tools (Tool Search)

With many MCP servers attached, Hermes **defers** plugin tools behind `tool_search` / `tool_describe` / `tool_call`. All `opencode_delegate` tools are usually deferred — that is normal.

To use an OpenCode tool when deferred:

1. `tool_search("opencode health")` or `tool_search("opencode create task")`
2. `tool_describe("opencode_create_task")` if needed
3. `tool_call("opencode_create_task", {...})`

### After plugin updates

1. Confirm deploy: `grep opencode_create_task /data/.hermes/plugins/opencode-delegate/__init__.py`
2. **Restart Hermes WebUI** from `/tui`: `kill $(cat /data/.hermes/webui/server.pid)`
3. **Start a new WebUI chat session**
4. Ensure session toolsets include **`opencode_delegate`**
5. Verify: `hermes plugins list` — `opencode-delegate` should be **enabled**

## Example user request

> Use OpenCode to update the n8n invoice workflow in n8n-as-code. Do not merge.

Actions:

1. `opencode_create_task` with `workspace_hint: n8n-as-code`, objective and prompt describing the change.
2. Poll with `opencode_get_task` until `finished` or `error`.
3. Summarize changes for the user.
