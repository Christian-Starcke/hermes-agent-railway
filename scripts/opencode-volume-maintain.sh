#!/usr/bin/env bash
# Conservative /data maintenance. Safe on boot and on a daily schedule.
# Only disposable caches and logs are pruned; user data is never removed.
set -uo pipefail

DATA_ROOT="${RAILWAY_VOLUME_MOUNT_PATH:-/data}"
LOG_FILE="${DATA_ROOT}/logs/volume-maintain.log"
WARN_PCT="${OPENCODE_VOLUME_WARN_THRESHOLD_PCT:-85}"
LOG_MAX_AGE_DAYS="${OPENCODE_LOG_MAX_AGE_DAYS:-14}"
LOG_MAX_BYTES="${OPENCODE_LOG_MAX_BYTES:-52428800}"
LOG_TAIL_BYTES="${OPENCODE_LOG_TAIL_BYTES:-10485760}"
NPX_MAX_AGE_DAYS="${OPENCODE_NPX_MAX_AGE_DAYS:-14}"
PREFIX="[volume-maintain]"

mkdir -p "${DATA_ROOT}/logs"

log() {
  local line="${PREFIX} $(date -u +%Y-%m-%dT%H:%M:%SZ) $*"
  echo "$line"
  echo "$line" >> "${LOG_FILE}"
}

trim_maintenance_log() {
  if [ -f "${LOG_FILE}" ] && [ "$(wc -c < "${LOG_FILE}" 2>/dev/null || echo 0)" -gt 1048576 ]; then
    tail -n 500 "${LOG_FILE}" > "${LOG_FILE}.tmp" && cat "${LOG_FILE}.tmp" > "${LOG_FILE}"
    rm -f "${LOG_FILE}.tmp"
  fi
}

usage_pct() {
  df -P "${DATA_ROOT}" 2>/dev/null | awk 'NR==2 {gsub(/%/,"",$5); print $5}' || echo 0
}

remove_tree() {
  if [ -e "$1" ]; then
    rm -rf -- "$1"
    log "removed disposable cache $1"
  fi
}

prune_caches() {
  # Download caches are always reconstructible. Installed npm-global tools and
  # workspace node_modules are deliberately not included.
  remove_tree "${DATA_ROOT}/home/.npm/_cacache"
  remove_tree "${DATA_ROOT}/home/.cache/uv"
  remove_tree "${DATA_ROOT}/.npm-cache/_cacache"
  remove_tree "${DATA_ROOT}/.npm-global/.npm/_cacache"
  remove_tree "${DATA_ROOT}/.npm/_cacache"
  remove_tree /root/.npm/_cacache

  # npx environments can be re-created, but avoid removing recently used ones.
  local root
  for root in "${DATA_ROOT}/home/.npm/_npx" "${DATA_ROOT}/.npm-cache/_npx"; do
    if [ -d "${root}" ]; then
      find "${root}" -mindepth 1 -maxdepth 1 -type d -mtime "+${NPX_MAX_AGE_DAYS}" \
        -exec rm -rf -- {} + 2>/dev/null || true
    fi
  done
}

prune_rotated_logs() {
  find "${DATA_ROOT}/logs" -maxdepth 1 -type f \
    \( -name '*.log.[0-9]*' -o -name '*.log.prev' -o -name '*.log.old' \) \
    -mtime "+${LOG_MAX_AGE_DAYS}" -delete 2>/dev/null || true
}

truncate_large_logs() {
  # Keep the inode: running processes continue writing to the same file.
  # The last LOG_TAIL_BYTES are preserved for diagnostics.
  find "${DATA_ROOT}/logs" -maxdepth 1 -type f -name '*.log' \
    -size "+${LOG_MAX_BYTES}c" -print0 2>/dev/null |
  while IFS= read -r -d '' file; do
    local tmp="${file}.maintain.tmp"
    if tail -c "${LOG_TAIL_BYTES}" "${file}" > "${tmp}"; then
      cat "${tmp}" > "${file}" && log "truncated ${file} to ${LOG_TAIL_BYTES} bytes"
    fi
    rm -f "${tmp}"
  done
}

trim_maintenance_log
log "starting maintenance"
log "$(df -h "${DATA_ROOT}" 2>/dev/null | tail -1)"

pct="$(usage_pct)"
if [ "${pct}" -ge "${WARN_PCT}" ] 2>/dev/null; then
  log "WARN disk at ${pct}% (threshold ${WARN_PCT}%)"
fi

prune_caches
prune_rotated_logs
truncate_large_logs

log "done — $(df -h "${DATA_ROOT}" 2>/dev/null | tail -1)"
exit 0
