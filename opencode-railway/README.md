# OpenCode on Railway (Hermes Agent project)

OpenCode runs as a separate Railway service in the Hermes Agent project. Hermes delegates work via the `opencode-delegate` plugin.

## Workspace layout (matches Hermes WebUI)

On boot (or via one-shot bootstrap), repos clone into `/data/workspace`:

```
/data/workspace/
  AGENTS.md, n8nac-config.json, workflows/   ← n8n-as-code at workspace root
  prism-platform-ap/
    n8n-as-code/
    prism-knowledge/
    prism-platform/
    prism-playbook/
    PROJECT_BOARD.md                         ← symlink when available
  gtm-dashboard/                             ← symlink when apps/gtm-dashboard exists
```

## MCP hub (12 servers)

OpenCode uses the same connections-hub MCP arsenal as Hermes and code-server-ide. Config is rendered from `prism-playbook/operations/connections-hub/config/opencode/opencode.json.template` and synced via `sync-railway.*` as `OPENCODE_CONFIG_CONTENT`.

| Server | Type | Auth |
|--------|------|------|
| github, firecrawl, railway, retellai, supabase, resend, n8nac, sentry | local (`npx` / `railway mcp`) | Railway env vars (`{env:VAR}` in config) |
| openrouter, better_stack, posthog | remote | Bearer header from env |
| vercel | remote | OAuth (one-time in OpenCode UI) |

**Verify:** in OpenCode shell or session: `opencode mcp list` — should show 12 enabled servers.

**Vercel (one-time):** `opencode mcp auth vercel` or complete OAuth in Settings → MCP. Token persists at `/data/.local/share/opencode/mcp-auth.json`.

**Railway MCP:** `@railway/cli` installs to `/data/.npm-global` on boot via `opencode-mcp-bootstrap.sh`. `RAILWAY_API_TOKEN` is synced from connections-hub; `PREPEND_PATH=/data/.npm-global/bin` puts `railway` on PATH.

Template source: [`operations/connections-hub/config/opencode/`](https://github.com/prism-platform-ap/prism-playbook/tree/main/operations/connections-hub/config/opencode)

## Bootstrap

**Automatic (OpenCode start command):**

```bash
bash /data/opencode-mcp-bootstrap.sh
bash /data/prism-workspace-bootstrap.sh
exec /app/start.sh
```

Set `WORKSPACE_BOOTSTRAP=true` and `GIT_REPO_*` vars on the opencode service.

**One-shot MCP bootstrap from your machine:**

```powershell
$env:OPENCODE_SERVER_URL = "https://opencode-production-5cf2.up.railway.app"
$env:OPENCODE_SERVER_PASSWORD = "..."
python .work/hermes-agent-railway/opencode-railway/run-mcp-bootstrap.py
```

**One-shot workspace bootstrap:**

```powershell
$env:GITHUB_TOKEN = "..."   # optional if repos are public
python .work/hermes-agent-railway/opencode-railway/run-workspace-bootstrap.py
```

**Manual on OpenCode shell:**

```bash
bash /data/opencode-mcp-bootstrap.sh
export WORKSPACE_BOOTSTRAP=true
bash /data/prism-workspace-bootstrap.sh
```

Script sources:
- [`scripts/opencode-mcp-bootstrap.sh`](../scripts/opencode-mcp-bootstrap.sh)
- [`scripts/prism-workspace-bootstrap.sh`](../scripts/prism-workspace-bootstrap.sh)

## Hermes env vars

Set on **hermes-agent** (see connections-hub `sync-railway.*`):

- `OPENCODE_SERVER_URL`
- `OPENCODE_SERVER_PASSWORD`
- `GIT_REPO_N8N`, `GIT_REPO_PLAYBOOK`, `GIT_REPO_PLATFORM`, `GIT_REPO_KNOWLEDGE`
- `WORKSPACE_BOOTSTRAP=true`

## OpenCode env vars

Set on **opencode** service (via `sync-railway.*`):

- `OPENCODE_CONFIG_CONTENT` — full MCP + model config (from `render-opencode.*`)
- `COMMON_VARS` keys: `FIRECRAWL_API_KEY`, `OPENROUTER_API_KEY`, `RETELL_API_KEY`, `RESEND_API_KEY`, `SUPABASE_PAT`, `GITHUB_TOKEN`, `N8N_*`, `RAILWAY_API_TOKEN`, `SENTRY_ACCESS_TOKEN`, `BETTERSTACK_API_TOKEN`, `POSTHOG_PERSONAL_API_KEY`
- `OPENCODE_SERVER_PASSWORD`
- `OPENCODE_MODEL`
- `OPENCODE_WORKSPACE=/data/workspace`
- `ENABLE_OH_MY_OPENCODE=false`
- `PREPEND_PATH=/data/.npm-global/bin`
- `GIT_REPO_*` + `WORKSPACE_BOOTSTRAP=true`

## Persistence on `/data` volume

| Path | Purpose |
|------|---------|
| `/data/.config/opencode/opencode.json` | MCP + model config |
| `/data/.local/share/opencode/mcp-auth.json` | OAuth tokens (Vercel) |
| `/data/.npm-global` | Railway CLI + global npm packages |
| `/data/.railway` | Railway CLI config symlink target |
| `/data/workspace` | Prism org repos |
