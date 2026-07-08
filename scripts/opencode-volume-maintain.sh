#!/usr/bin/env bash
# Idempotent OpenCode /data volume maintenance. Safe on boot and on schedule.
set -uo pipefail

DATA_ROOT="${RAILWAY_VOLUME_MOUNT_PATH:-/data}"
LOG_FILE="${DATA_ROOT}/logs/volume-maintain.log"
WARN_PCT="${OPENCODE_VOLUME_WARN_THRESHOLD_PCT:-85}"
NODE_MAX_AGE_DAYS="${OPENCODE_NODE_MODULES_MAX_AGE_DAYS:-14}"
LAZY_MAX_AGE_DAYS="${OPENCODE_LAZY_REPO_MAX_AGE_DAYS:-7}"
WORKSPACE="${OPENCODE_WORKSPACE:-${DATA_ROOT}/workspace}"
PREFIX="[volume-maintain]"

mkdir -p "${DATA_ROOT}/logs"

log() {
  local line="${PREFIX} $(date -u +%Y-%m-%dT%H:%M:%SZ) $*"
  echo "$line"
  echo "$line" >> "${LOG_FILE}"
}

rotate_log() {
  if [ -f "${LOG_FILE}" ]; then
    local size
    size="$(wc -c < "${LOG_FILE}" 2>/dev/null || echo 0)"
    if [ "${size}" -gt 1048576 ]; then
      tail -n 500 "${LOG_FILE}" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "${LOG_FILE}"
    fi
  fi
}

usage_pct() {
  df -P "${DATA_ROOT}" 2>/dev/null | awk 'NR==2 {gsub(/%/,"",$5); print $5}' || echo 0
}

prune_npm_caches() {
  rm -rf \
    "${DATA_ROOT}/.npm-cache"/* \
    "${DATA_ROOT}/.npm-global/.npm/_cacache" \
    "${DATA_ROOT}/.npm/_cacache" \
    /root/.npm/_cacache 2>/dev/null || true
}

prune_node_modules() {
  local max_age_days="$1"
  local aggressive="$2"
  if [ ! -d "${WORKSPACE}" ]; then
    return 0
  fi
  if [ "${aggressive}" = "1" ]; then
    find "${WORKSPACE}" -name node_modules -type d -prune -exec rm -rf {} + 2>/dev/null || true
    return 0
  fi
  find "${WORKSPACE}" -name node_modules -type d -prune -mtime "+${max_age_days}" -exec rm -rf {} + 2>/dev/null || true
}

prune_lazy_repos() {
  local max_age_days="$1"
  local org="${WORKSPACE}/prism-platform-ap"
  for name in prism-playbook prism-knowledge; do
    local path="${org}/${name}"
    if [ -d "${path}" ] && [ ! -L "${path}" ]; then
      if find "${path}" -maxdepth 0 -mtime "+${max_age_days}" | grep -q .; then
        log "removing idle lazy repo ${path}"
        rm -rf "${path}"
      fi
    fi
  done
}

git_gc_workspace() {
  if [ ! -d "${WORKSPACE}" ]; then
    return 0
  fi
  while IFS= read -r gitdir; do
    git -C "$(dirname "${gitdir}")" gc --prune=now 2>/dev/null || true
  done < <(find "${WORKSPACE}" -name .git -type d 2>/dev/null)
}

rotate_log
log "starting maintenance"
log "$(df -h "${DATA_ROOT}" 2>/dev/null | tail -1)"

pct="$(usage_pct)"
aggressive=0
if [ "${pct}" -ge "${WARN_PCT}" ] 2>/dev/null; then
  aggressive=1
  log "WARN disk at ${pct}% (threshold ${WARN_PCT}%) — aggressive prune"
fi

if [ "${aggressive}" = "1" ]; then
  prune_node_modules 0 1
  prune_lazy_repos "${LAZY_MAX_AGE_DAYS}"
else
  prune_npm_caches
  prune_node_modules "${NODE_MAX_AGE_DAYS}" 0
fi

git_gc_workspace
log "done — $(df -h "${DATA_ROOT}" 2>/dev/null | tail -1)"
exit 0
