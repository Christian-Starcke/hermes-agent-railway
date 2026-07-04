#!/usr/bin/env bash
# Clone or pull Prism workspace repos into OpenCode's persistent /data/workspace volume.
# Run once on the OpenCode Railway service (shell or one-off deploy hook).
set -euo pipefail

WORKSPACE_ROOT="${OPENCODE_WORKSPACE_ROOT:-/data/workspace}"
mkdir -p "${WORKSPACE_ROOT}"

clone_or_pull() {
  local url="$1"
  local name="$2"
  local target="${WORKSPACE_ROOT}/${name}"
  if [ -d "${target}/.git" ]; then
    echo "[bootstrap] pulling ${name}..."
    git -C "${target}" pull --ff-only origin main 2>/dev/null || git -C "${target}" pull --ff-only
  else
    echo "[bootstrap] cloning ${name}..."
    git clone --depth 1 "${url}" "${target}"
  fi
}

if [ -n "${GITHUB_TOKEN:-}" ]; then
  git config --global url."https://${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/" 2>/dev/null || true
fi

[ -n "${GIT_REPO_N8N:-}" ] && clone_or_pull "${GIT_REPO_N8N}" "n8n-as-code"
[ -n "${GIT_REPO_PLAYBOOK:-}" ] && clone_or_pull "${GIT_REPO_PLAYBOOK}" "prism-playbook"
[ -n "${GIT_REPO_PLATFORM:-}" ] && clone_or_pull "${GIT_REPO_PLATFORM}" "prism-platform"

echo "[bootstrap] workspace ready at ${WORKSPACE_ROOT}"
ls -la "${WORKSPACE_ROOT}"
