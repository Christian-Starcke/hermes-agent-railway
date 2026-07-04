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

## Bootstrap

**Automatic (OpenCode):** set `WORKSPACE_BOOTSTRAP=true` and `GIT_REPO_*` vars, then use a start command that runs `/data/opencode-workspace-bootstrap.sh` before `start.sh` (installed on first bootstrap).

**One-shot from your machine:**

```powershell
$env:OPENCODE_SERVER_URL = "https://opencode-production-5cf2.up.railway.app"
$env:OPENCODE_SERVER_PASSWORD = "..."
$env:GITHUB_TOKEN = "..."   # optional if repos are public
python .work/hermes-agent-railway/opencode-railway/run-workspace-bootstrap.py
```

**Manual on OpenCode shell:** after script is on volume:

```bash
export WORKSPACE_BOOTSTRAP=true
bash /data/opencode-workspace-bootstrap.sh
```

Script source: [`scripts/prism-workspace-bootstrap.sh`](../scripts/prism-workspace-bootstrap.sh)

## Hermes env vars

Set on **hermes-agent** (see connections-hub `sync-railway.*`):

- `OPENCODE_SERVER_URL`
- `OPENCODE_SERVER_PASSWORD`
- `GIT_REPO_N8N`, `GIT_REPO_PLAYBOOK`, `GIT_REPO_PLATFORM`, `GIT_REPO_KNOWLEDGE`
- `WORKSPACE_BOOTSTRAP=true`

## OpenCode env vars

Set on **opencode** service:

- `OPENROUTER_API_KEY`
- `OPENCODE_SERVER_PASSWORD`
- `OPENCODE_MODEL`
- `OPENCODE_CONFIG_CONTENT`
- `OPENCODE_WORKSPACE=/data/workspace`
- `ENABLE_OH_MY_OPENCODE=false`
- `GITHUB_TOKEN` + `GIT_REPO_*` for workspace bootstrap
- `WORKSPACE_BOOTSTRAP=true`
