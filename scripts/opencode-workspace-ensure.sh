#!/usr/bin/env bash
# On-demand clone/pull for lazy workspace repos (playbook, knowledge).
set -euo pipefail

DATA_ROOT="${RAILWAY_VOLUME_MOUNT_PATH:-/data}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-${OPENCODE_WORKSPACE:-${DATA_ROOT}/workspace}}"
ORG_DIR="${WORKSPACE_ROOT}/prism-platform-ap"
PREFIX="${WORKSPACE_BOOTSTRAP_PREFIX:-[workspace-ensure]}"

GIT_REPO_PLAYBOOK="${GIT_REPO_PLAYBOOK:-https://github.com/prism-platform-ap/prism-playbook}"
GIT_REPO_KNOWLEDGE="${GIT_REPO_KNOWLEDGE:-https://github.com/prism-platform-ap/prism-knowledge}"

usage() {
  echo "Usage: $0 prism-playbook|prism-knowledge" >&2
  exit 1
}

[ $# -ge 1 ] || usage

configure_git_auth() {
  if [ -n "${GITHUB_TOKEN:-}" ]; then
    git config --global url."https://${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/" 2>/dev/null || true
  fi
}

clone_or_pull() {
  local url="$1"
  local dest="$2"
  mkdir -p "$(dirname "${dest}")"
  if [ -d "${dest}/.git" ]; then
    echo "${PREFIX} pulling ${dest}..."
    git -C "${dest}" pull --ff-only origin main 2>/dev/null || git -C "${dest}" pull --ff-only
  else
    echo "${PREFIX} cloning ${url} -> ${dest}..."
    git clone --depth 1 "${url}" "${dest}"
  fi
}

case "$1" in
  prism-playbook|playbook)
    configure_git_auth
    clone_or_pull "${GIT_REPO_PLAYBOOK}" "${ORG_DIR}/prism-playbook"
    ;;
  prism-knowledge|knowledge)
    configure_git_auth
    clone_or_pull "${GIT_REPO_KNOWLEDGE}" "${ORG_DIR}/prism-knowledge"
    ;;
  *)
    usage
    ;;
esac

echo "${PREFIX} ready: ${ORG_DIR}/$1"
