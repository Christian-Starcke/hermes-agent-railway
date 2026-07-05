# OpenCode on Railway (Hermes Agent project)

OpenCode can run in two modes:

1. **Co-located (recommended)** — `opencode serve` loopback inside the **hermes-agent** container (`OPENCODE_COLOCATE=true`, default). Shares `/data/home/workspace` and git worktrees with Hermes. `OPENCODE_SERVER_URL` defaults to `http://127.0.0.1:9130`.
2. **Remote service** — separate Railway **opencode** service with its own `/data/workspace` volume. Set `OPENCODE_SERVER_URL` to the public URL and `OPENCODE_COLOCATE=false` on hermes-agent to skip local serve.

> **Not Crush:** This stack uses [opencode.ai](https://opencode.ai) (SST/anomalyco). The archived `opencode-ai/opencode` → Crush project has an incompatible API.

Hermes delegates work via the `opencode-delegate` plugin.

## Co-location env vars (hermes-agent)

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENCODE_COLOCATE` | `true` | Start `opencode serve` on boot |
| `OPENCODE_LOCAL_PORT` | `9130` | Loopback port |
| `OPENCODE_PREFER_LOCAL` | `true` | Use local URL even if remote URL was set |
| `OPENCODE_SERVER_PASSWORD` | — | HTTP basic auth (required) |
| `OPENCODE_CONFIG_CONTENT` | — | Written to `/data/opencode.json` |
| `OPENCODE_WORKSPACE` | `/data/home/workspace` | Default project root |

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

## Version upgrades (auto on new release)

OpenCode **core + web UI are baked into the Docker image** at build time (`SOURCE_MODE=true`, `OPENCODE_REF=<git tag>`). Restarting the container or editing runtime env vars does **not** upgrade the UI — Railway must **rebuild** with a newer `OPENCODE_REF`.

| What | Auto-updates? |
|------|----------------|
| OpenCode CLI + web UI | No — requires `OPENCODE_REF` change + image rebuild |
| MCP config / API keys | Yes — via `sync-railway.*` (`OPENCODE_CONFIG_CONTENT` + env vars) |
| Workspace, MCP OAuth, `/data` volume | Persists across version upgrades |

**Automatic:** [prism-playbook `opencode-release-check` workflow](https://github.com/prism-platform-ap/prism-playbook/blob/main/.github/workflows/opencode-release-check.yml) polls GitHub every 6 hours; redeploys only when `anomalyco/opencode` has a newer release tag. Set `RAILWAY_API_TOKEN` in prism-playbook Actions secrets.

**Manual (local):**

```powershell
cd prism-playbook/operations/connections-hub
.\scripts\check-opencode-release.ps1
.\scripts\check-opencode-release.ps1 -DryRun
.\scripts\check-opencode-release.ps1 -Force v1.17.13
```

**Verify after upgrade:** `python opencode-railway/verify-mcp-hub.py` (12 MCPs) + OpenCode UI loads.

**Note:** Large version jumps with 12 MCPs can exceed the LaceLetho wrapper's 30s startup health timeout. If a deploy shows `502` / `OpenCode failed to start within timeout`, roll back with `-Force v1.14.41` or wait for a LaceLetho template update. The release-check workflow only upgrades when the GitHub tag is newer — it does not auto-rollback.


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
- `OPENCODE_REF` — git tag built into image (e.g. `v1.17.13`); see Version upgrades above
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
