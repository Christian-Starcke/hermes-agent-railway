#!/usr/bin/env bash
# Install Railway CLI to /data/.npm-global for OpenCode MCP (idempotent).
set -euo pipefail

DATA_ROOT="${RAILWAY_VOLUME_MOUNT_PATH:-/data}"
NPM_GLOBAL="${DATA_ROOT}/.npm-global"
export NPM_CONFIG_CACHE="${NPM_CONFIG_CACHE:-${DATA_ROOT}/.npm-cache}"
export npm_config_cache="${NPM_CONFIG_CACHE}"
export PATH="${NPM_GLOBAL}/bin:${PATH}"
PREFIX="[opencode-mcp-bootstrap]"

mkdir -p "${NPM_GLOBAL}" "${NPM_CONFIG_CACHE}"

if command -v railway >/dev/null 2>&1 && railway --version >/dev/null 2>&1; then
  echo "${PREFIX} railway CLI already present: $(railway --version 2>/dev/null | head -1)"
else
  echo "${PREFIX} installing @railway/cli to ${NPM_GLOBAL}..."
  npm install --prefix "${NPM_GLOBAL}" --global @railway/cli --no-audit --no-fund
  echo "${PREFIX} installed: $(railway --version 2>/dev/null | head -1)"
fi

warm_mcp_package() {
  local label="$1"
  shift
  echo "${PREFIX} warming ${label}..."
  if timeout 120 "$@" >/dev/null 2>&1; then
    echo "${PREFIX} ${label} ready"
    return 0
  fi
  echo "${PREFIX} warn: ${label} warm failed (will retry on next boot)"
  return 0
}

mcp_npx_cache_ok() {
  local ok=0
  npx --yes @modelcontextprotocol/server-github --help >/dev/null 2>&1 && ok=$((ok + 1))
  npx --yes firecrawl-mcp --help >/dev/null 2>&1 && ok=$((ok + 1))
  npx --yes mcp-searxng --help >/dev/null 2>&1 && ok=$((ok + 1))
  npx --yes resend-mcp --help >/dev/null 2>&1 && ok=$((ok + 1))
  npx --yes @abhaybabbar/retellai-mcp-server --help >/dev/null 2>&1 && ok=$((ok + 1))
  npx --yes @supabase/mcp-server-supabase@latest --help >/dev/null 2>&1 && ok=$((ok + 1))
  npx --yes @sentry/mcp-server@latest --help >/dev/null 2>&1 && ok=$((ok + 1))
  npx --yes @n8n-as-code/mcp --help >/dev/null 2>&1 && ok=$((ok + 1))
  [ "${ok}" -ge 6 ]
}

warm_all_mcp_packages() {
  warm_mcp_package "github MCP" npx --yes @modelcontextprotocol/server-github
  warm_mcp_package "firecrawl MCP" npx --yes firecrawl-mcp
  warm_mcp_package "searxng MCP" npx --yes mcp-searxng
  warm_mcp_package "retellai MCP" npx --yes @abhaybabbar/retellai-mcp-server
  warm_mcp_package "supabase MCP" npx --yes @supabase/mcp-server-supabase@latest --help
  warm_mcp_package "resend MCP" npx --yes resend-mcp
  warm_mcp_package "sentry MCP" npx --yes @sentry/mcp-server@latest
  warm_mcp_package "n8nac MCP" npx --yes -p n8nac -p @n8n-as-code/mcp n8nac --version
}

# Rebuild npx MCP cache when missing or corrupt (partial installs after volume prune).
if ! mcp_npx_cache_ok; then
  echo "${PREFIX} npx MCP cache missing or corrupt — rebuilding..."
  rm -rf "${NPM_CONFIG_CACHE}/_npx" 2>/dev/null || true
  warm_all_mcp_packages
else
  echo "${PREFIX} npx MCP cache ok"
fi
