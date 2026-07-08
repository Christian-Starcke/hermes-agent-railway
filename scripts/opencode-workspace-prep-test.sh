#!/usr/bin/env bash
# On-demand npm/pnpm install for Vitest and test coverage in a workspace repo.
set -euo pipefail

DATA_ROOT="${RAILWAY_VOLUME_MOUNT_PATH:-/data}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-${OPENCODE_WORKSPACE:-${DATA_ROOT}/workspace}}"
export NPM_CONFIG_CACHE="${NPM_CONFIG_CACHE:-${DATA_ROOT}/.npm-cache}"
export npm_config_cache="${NPM_CONFIG_CACHE}"
PREFIX="[prep-test]"

usage() {
  echo "Usage: $0 <path-under-workspace>  (e.g. prism-platform-ap/prism-platform or .)" >&2
  exit 1
}

[ $# -ge 1 ] || usage

REL="${1#./}"
REL="${REL#/}"
if [ "${REL}" = "." ] || [ -z "${REL}" ]; then
  REPO_DIR="${WORKSPACE_ROOT}"
else
  REPO_DIR="${WORKSPACE_ROOT}/${REL}"
fi

if [ ! -d "${REPO_DIR}" ]; then
  echo "${PREFIX} ERROR repo path not found: ${REPO_DIR}" >&2
  exit 1
fi

if [ ! -f "${REPO_DIR}/package.json" ]; then
  echo "${PREFIX} ERROR no package.json in ${REPO_DIR}" >&2
  exit 1
fi

lockfile=""
if [ -f "${REPO_DIR}/pnpm-lock.yaml" ]; then
  lockfile="${REPO_DIR}/pnpm-lock.yaml"
elif [ -f "${REPO_DIR}/package-lock.json" ]; then
  lockfile="${REPO_DIR}/package-lock.json"
fi

if [ -n "${lockfile}" ] && [ -d "${REPO_DIR}/node_modules" ]; then
  if [ "${REPO_DIR}/node_modules" -nt "${lockfile}" ]; then
    echo "${PREFIX} node_modules newer than lockfile — skip install"
    (cd "${REPO_DIR}" && npx vitest --version >/dev/null 2>&1) && {
      echo "${PREFIX} vitest OK"
      exit 0
    }
  fi
fi

cd "${REPO_DIR}"
if [ -f pnpm-lock.yaml ]; then
  if command -v pnpm >/dev/null 2>&1; then
    pnpm install --frozen-lockfile
  elif command -v corepack >/dev/null 2>&1; then
    corepack enable 2>/dev/null || true
    pnpm install --frozen-lockfile
  else
    echo "${PREFIX} pnpm-lock.yaml present but pnpm unavailable — using npm install"
    npm install --no-audit --no-fund
  fi
elif [ -f package-lock.json ]; then
  npm ci --no-audit --no-fund
else
  npm install --no-audit --no-fund
fi

if npx vitest --version >/dev/null 2>&1; then
  echo "${PREFIX} vitest $(npx vitest --version 2>/dev/null | head -1)"
else
  echo "${PREFIX} WARN vitest not found after install — check devDependencies" >&2
  exit 1
fi

echo "${PREFIX} disk: $(df -h "${DATA_ROOT}" 2>/dev/null | tail -1)"
