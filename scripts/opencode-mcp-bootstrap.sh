#!/usr/bin/env bash
# Bootstrap Railway CLI + OpenCode config dirs on the OpenCode /data volume.
set -euo pipefail

PREFIX="${OPENCODE_MCP_BOOTSTRAP_PREFIX:-[opencode-mcp-bootstrap]}"
NPM_PREFIX="${NPM_CONFIG_PREFIX:-/data/.npm-global}"
RAILWAY_HOME="/data/.railway"

mkdir -p "${NPM_PREFIX}/bin" /data/.config/opencode /data/logs "${RAILWAY_HOME}"
export NPM_CONFIG_PREFIX="${NPM_PREFIX}"
export PATH="${NPM_PREFIX}/bin:${PATH}"

if [ -n "${RAILWAY_API_TOKEN:-}" ]; then
  export RAILWAY_TOKEN="${RAILWAY_API_TOKEN}"
fi

if [ ! -e "${HOME}/.railway" ]; then
  ln -sf "${RAILWAY_HOME}" "${HOME}/.railway"
fi

if ! command -v railway >/dev/null 2>&1; then
  echo "${PREFIX} installing @railway/cli into ${NPM_PREFIX}"
  npm install -g @railway/cli
fi

echo "${PREFIX} railway=$(command -v railway)"
echo "${PREFIX} opencode config dir ready"
