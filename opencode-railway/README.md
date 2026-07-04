# OpenCode on Railway (Hermes Agent project)

OpenCode runs as a separate Railway service in the Hermes Agent project. Hermes delegates work via the `opencode-delegate` plugin.

## Workspace bootstrap

Clone Prism repos into OpenCode's persistent volume:

```bash
# On the OpenCode Railway service shell (or one-off):
export GITHUB_TOKEN=...
export GIT_REPO_N8N=https://github.com/prism-platform-ap/n8n-as-code
export GIT_REPO_PLAYBOOK=https://github.com/prism-platform-ap/prism-playbook
export GIT_REPO_PLATFORM=https://github.com/prism-platform-ap/prism-platform
bash /path/to/workspace-bootstrap.sh
```

Script source: [`workspace-bootstrap.sh`](./workspace-bootstrap.sh) (copy into `/data/workspace-bootstrap.sh` on the OpenCode volume, or run from a linked repo).

Target layout:

```
/data/workspace/
  n8n-as-code/
  prism-playbook/
  prism-platform/
```

## Hermes env vars

Set on **hermes-agent** (see connections-hub `sync-railway.*`):

- `OPENCODE_SERVER_URL`
- `OPENCODE_SERVER_PASSWORD`
- `OPENCODE_SERVER_USER` (default `opencode`)
- `OPENCODE_DEFAULT_AGENT` (default `build`)
- `OPENCODE_DEFAULT_MODEL`

## OpenCode env vars

Set on **opencode** service:

- `OPENROUTER_API_KEY`
- `OPENCODE_SERVER_PASSWORD`
- `OPENCODE_MODEL`
- `OPENCODE_CONFIG_CONTENT`
- `ENABLE_OH_MY_OPENCODE=false`
- `GITHUB_TOKEN` + `GIT_REPO_*` for workspace bootstrap
