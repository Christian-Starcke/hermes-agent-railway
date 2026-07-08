#!/usr/bin/env bash
# OpenCode Railway boot orchestrator — sync scripts, maintain volume, bootstrap workspace.
set -euo pipefail

DATA_ROOT="${RAILWAY_VOLUME_MOUNT_PATH:-/data}"
SCRIPT_SRC="${OPENCODE_SCRIPT_SRC:-/opt/hermes-railway/scripts}"
SCRIPT_RAW_BASE="${OPENCODE_SCRIPT_RAW_BASE:-https://raw.githubusercontent.com/Christian-Starcke/hermes-agent-railway/main/scripts}"
CRON_RAW_BASE="${OPENCODE_CRON_RAW_BASE:-https://raw.githubusercontent.com/Christian-Starcke/hermes-agent-railway/main/opencode-railway}"
PREFIX="[workspace-bootstrap]"

export NPM_CONFIG_CACHE="${NPM_CONFIG_CACHE:-${DATA_ROOT}/.npm-cache}"
export npm_config_cache="${NPM_CONFIG_CACHE}"
export OPENCODE_WORKSPACE="${OPENCODE_WORKSPACE:-${DATA_ROOT}/workspace}"
export WORKSPACE_ROOT="${OPENCODE_WORKSPACE}"

mkdir -p "${DATA_ROOT}/cron" "${DATA_ROOT}/logs"

fetch_script() {
  local name="$1"
  local dest="${DATA_ROOT}/${name}"
  if [ -f "${dest}" ] && [ "${OPENCODE_FORCE_SCRIPT_SYNC:-false}" != "true" ]; then
    return 0
  fi
  if [ -n "${SCRIPT_RAW_BASE}" ] && command -v curl >/dev/null 2>&1; then
    curl -fsSL "${SCRIPT_RAW_BASE}/${name}" -o "${dest}" && chmod +x "${dest}" && return 0
  fi
  return 1
}

sync_scripts() {
  local names=(
    opencode-volume-maintain.sh
    opencode-mcp-bootstrap.sh
    opencode-workspace-ensure.sh
    opencode-workspace-prep-test.sh
    prism-workspace-bootstrap.sh
  )

  if [ -d "${SCRIPT_SRC}" ]; then
    for name in "${names[@]}"; do
      if [ -f "${SCRIPT_SRC}/${name}" ]; then
        cp -f "${SCRIPT_SRC}/${name}" "${DATA_ROOT}/${name}"
        chmod +x "${DATA_ROOT}/${name}"
      fi
    done
  else
    for name in "${names[@]}"; do
      fetch_script "${name}" || echo "${PREFIX} warn: could not fetch ${name}"
    done
  fi

  local loop_dest="${DATA_ROOT}/cron/opencode-volume-maintain-loop.sh"
  if [ -f /opt/hermes-railway/opencode-railway/opencode-volume-maintain-loop.sh ]; then
    cp -f /opt/hermes-railway/opencode-railway/opencode-volume-maintain-loop.sh "${loop_dest}"
    chmod +x "${loop_dest}"
  elif command -v curl >/dev/null 2>&1; then
    curl -fsSL "${CRON_RAW_BASE}/opencode-volume-maintain-loop.sh" -o "${loop_dest}" && chmod +x "${loop_dest}" || true
  fi

  cp -f "$0" "${DATA_ROOT}/workspace-bootstrap.sh" 2>/dev/null || true
  chmod +x "${DATA_ROOT}/workspace-bootstrap.sh" 2>/dev/null || true
}

if [ -d /opt/hermes-railway/scripts ]; then
  SCRIPT_SRC=/opt/hermes-railway/scripts
fi

sync_scripts

run_if() {
  local script="${DATA_ROOT}/$1"
  if [ -x "${script}" ]; then
    bash "${script}" || echo "${PREFIX} warn: $1 exited non-zero (continuing)"
  else
    echo "${PREFIX} skip missing ${script}"
  fi
}

run_if opencode-volume-maintain.sh
run_if opencode-mcp-bootstrap.sh

export WORKSPACE_BOOTSTRAP_PREFIX="[opencode-bootstrap]"
bash "${DATA_ROOT}/prism-workspace-bootstrap.sh" || echo "${PREFIX} warn: prism-workspace-bootstrap failed"

if [ "${OPENCODE_PREP_TESTS_ON_BOOT:-false}" = "true" ]; then
  bash "${DATA_ROOT}/opencode-workspace-prep-test.sh" prism-platform-ap/prism-platform || true
fi

LOOP="${DATA_ROOT}/cron/opencode-volume-maintain-loop.sh"
if [ -x "${LOOP}" ]; then
  if ! pgrep -f "opencode-volume-maintain-loop.sh" >/dev/null 2>&1; then
    nohup bash "${LOOP}" >/dev/null 2>&1 &
    echo "${PREFIX} started volume maintain loop (interval ${OPENCODE_VOLUME_MAINTAIN_INTERVAL_SEC:-86400}s)"
  fi
fi

echo "${PREFIX} complete"
