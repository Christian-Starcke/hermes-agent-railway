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

# n8nac MCP uses npx; volume maintenance must not delete _npx caches. Warm a clean install anyway.
rm -rf "${NPM_CONFIG_CACHE}/_npx" 2>/dev/null || true
warm_mcp_package "n8nac CLI" npx --yes n8nac --version
warm_mcp_package "@n8n-as-code/mcp" npx --yes @n8n-as-code/mcp --help
