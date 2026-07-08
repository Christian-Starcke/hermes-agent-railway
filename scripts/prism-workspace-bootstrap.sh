#!/usr/bin/env bash
# Clone or pull prism-platform-ap org repos into a Hermes/OpenCode workspace volume.
# Layout mirrors Hermes WebUI workspace:
#   ${WORKSPACE_ROOT}/              <- n8n-as-code root (AGENTS.md, workflows/, ...)
#   ${WORKSPACE_ROOT}/prism-platform-ap/{prism-platform, prism-playbook, ...}
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-${OPENCODE_WORKSPACE:-/data/workspace}}"
ORG_DIR="${WORKSPACE_ROOT}/prism-platform-ap"
PREFIX="${WORKSPACE_BOOTSTRAP_PREFIX:-[prism-workspace]}"
# Comma list: n8n,platform,playbook,knowledge — default all for Hermes; OpenCode uses n8n,platform
WORKSPACE_BOOTSTRAP_REPOS="${WORKSPACE_BOOTSTRAP_REPOS:-n8n,platform,playbook,knowledge}"

GIT_REPO_N8N="${GIT_REPO_N8N:-https://github.com/Christian-Starcke/n8n-as-code}"
GIT_REPO_PLAYBOOK="${GIT_REPO_PLAYBOOK:-https://github.com/prism-platform-ap/prism-playbook}"
GIT_REPO_PLATFORM="${GIT_REPO_PLATFORM:-https://github.com/prism-platform-ap/prism-platform}"
GIT_REPO_KNOWLEDGE="${GIT_REPO_KNOWLEDGE:-https://github.com/prism-platform-ap/prism-knowledge}"

mkdir -p "${WORKSPACE_ROOT}" "${ORG_DIR}"

repo_enabled() {
  local key="$1"
  echo ",${WORKSPACE_BOOTSTRAP_REPOS}," | grep -qi ",${key},"
}

configure_git_auth() {
  if [ -n "${GITHUB_TOKEN:-}" ]; then
    git config --global url."https://${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/" 2>/dev/null || true
  fi
}

clone_or_pull() {
  local url="$1"
  local dest="$2"
  if [ -z "${url}" ]; then
    return 0
  fi
  if [ -d "${dest}/.git" ]; then
    echo "${PREFIX} pulling ${dest}..."
    git -C "${dest}" pull --ff-only origin main 2>/dev/null || git -C "${dest}" pull --ff-only
  else
    echo "${PREFIX} cloning ${url} -> ${dest}..."
    mkdir -p "$(dirname "${dest}")"
    git clone --depth 1 "${url}" "${dest}"
  fi
}

clone_or_pull_root_n8n() {
  local url="${GIT_REPO_N8N}"
  if [ -z "${url}" ]; then
    return 0
  fi
  if [ -d "${WORKSPACE_ROOT}/.git" ]; then
    echo "${PREFIX} pulling n8n-as-code at workspace root..."
    git -C "${WORKSPACE_ROOT}" pull --ff-only origin main 2>/dev/null || git -C "${WORKSPACE_ROOT}" pull --ff-only
    return 0
  fi
  local tmp="${WORKSPACE_ROOT}/.n8n-as-code-bootstrap"
  rm -rf "${tmp}"
  echo "${PREFIX} cloning n8n-as-code to workspace root..."
  git clone --depth 1 "${url}" "${tmp}"
  shopt -s dotglob nullglob
  for item in "${tmp}"/*; do
    base="$(basename "${item}")"
    if [ "${base}" = "prism-platform-ap" ]; then
      continue
    fi
    if [ -e "${WORKSPACE_ROOT}/${base}" ]; then
      continue
    fi
    mv "${item}" "${WORKSPACE_ROOT}/${base}"
  done
  shopt -u dotglob nullglob
  rm -rf "${tmp}"
}

link_n8n_org_symlink() {
  local link="${ORG_DIR}/n8n-as-code"
  if [ -e "${link}" ] || [ -L "${link}" ]; then
    return 0
  fi
  if [ -f "${WORKSPACE_ROOT}/n8nac-config.json" ] || [ -d "${WORKSPACE_ROOT}/.git" ]; then
    echo "${PREFIX} symlink ${link} -> ../.. (workspace root n8n-as-code)"
    ln -sfn "../.." "${link}"
  fi
}

link_project_board() {
  local board="${ORG_DIR}/PROJECT_BOARD.md"
  if [ -e "${board}" ]; then
    return 0
  fi
  if [ -f "${ORG_DIR}/prism-playbook/PROJECT_BOARD.md" ]; then
    ln -sfn "prism-playbook/PROJECT_BOARD.md" "${board}"
  elif [ -f "${ORG_DIR}/prism-playbook/TASK_NOTEBOOK.md" ]; then
    ln -sfn "prism-playbook/TASK_NOTEBOOK.md" "${board}"
  fi
}

link_gtm_dashboard() {
  local target="${WORKSPACE_ROOT}/gtm-dashboard"
  local app="${ORG_DIR}/prism-platform/apps/gtm-dashboard"
  if [ -d "${app}" ] && [ ! -e "${target}" ]; then
    ln -sfn "prism-platform-ap/prism-platform/apps/gtm-dashboard" "${target}"
  fi
}

configure_n8n_env() {
  if [ -z "${N8N_API_KEY:-}" ] || [ ! -f "${WORKSPACE_ROOT}/n8nac-config.json" ]; then
    return 0
  fi
  if ! command -v n8nac >/dev/null 2>&1; then
    return 0
  fi
  echo "${PREFIX} configuring n8nac Dev environment..."
  cd "${WORKSPACE_ROOT}"
  if n8nac env list 2>/dev/null | grep -q "Dev"; then
    n8nac env use Dev 2>/dev/null || true
    printf '%s' "${N8N_API_KEY}" | n8nac env auth set Dev --api-key-stdin 2>/dev/null || true
  else
    n8nac env add Dev \
      --base-url "${N8N_BASE_URL:-https://primary-production-10917.up.railway.app}" \
      --workflows-path workflows/dev 2>/dev/null || true
    printf '%s' "${N8N_API_KEY}" | n8nac env auth set Dev --api-key-stdin 2>/dev/null || true
    n8nac env use Dev 2>/dev/null || true
  fi
  n8nac update-ai 2>/dev/null || true
}

if [ "${WORKSPACE_BOOTSTRAP:-}" != "true" ] && [ "${WORKSPACE_BOOTSTRAP:-}" != "1" ]; then
  echo "${PREFIX} WORKSPACE_BOOTSTRAP not enabled — skip"
  exit 0
fi

configure_git_auth

if repo_enabled n8n; then
  clone_or_pull_root_n8n
fi
if repo_enabled platform; then
  clone_or_pull "${GIT_REPO_PLATFORM}" "${ORG_DIR}/prism-platform"
  link_n8n_org_symlink
fi
if repo_enabled knowledge; then
  clone_or_pull "${GIT_REPO_KNOWLEDGE}" "${ORG_DIR}/prism-knowledge"
fi
if repo_enabled playbook; then
  clone_or_pull "${GIT_REPO_PLAYBOOK}" "${ORG_DIR}/prism-playbook"
fi

link_project_board
link_gtm_dashboard
configure_n8n_env

echo "${PREFIX} workspace ready at ${WORKSPACE_ROOT} (repos: ${WORKSPACE_BOOTSTRAP_REPOS})"
ls -la "${WORKSPACE_ROOT}"
ls -la "${ORG_DIR}" 2>/dev/null || true
