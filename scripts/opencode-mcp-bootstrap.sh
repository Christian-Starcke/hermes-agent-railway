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
  exit 0
fi

echo "${PREFIX} installing @railway/cli to ${NPM_GLOBAL}..."
npm install --prefix "${NPM_GLOBAL}" --global @railway/cli --no-audit --no-fund
echo "${PREFIX} installed: $(railway --version 2>/dev/null | head -1)"
