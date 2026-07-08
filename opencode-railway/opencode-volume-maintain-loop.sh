#!/usr/bin/env bash
# Background scheduler for opencode-volume-maintain.sh
set -uo pipefail

DATA_ROOT="${RAILWAY_VOLUME_MOUNT_PATH:-/data}"
INTERVAL="${OPENCODE_VOLUME_MAINTAIN_INTERVAL_SEC:-86400}"
LOG="${DATA_ROOT}/logs/volume-maintain.log"
MAINTAIN="${DATA_ROOT}/opencode-volume-maintain.sh"

mkdir -p "${DATA_ROOT}/logs"

while true; do
  sleep "${INTERVAL}"
  if [ -x "${MAINTAIN}" ]; then
    bash "${MAINTAIN}" >> "${LOG}" 2>&1 || true
  fi
done
