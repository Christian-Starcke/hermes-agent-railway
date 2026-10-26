#!/usr/bin/env bash
# Background scheduler for opencode-volume-maintain.sh
set -uo pipefail

DATA_ROOT="${RAILWAY_VOLUME_MOUNT_PATH:-/data}"
INTERVAL="${OPENCODE_VOLUME_MAINTAIN_INTERVAL_SEC:-86400}"
MAINTAIN="${OPENCODE_VOLUME_MAINTAIN_SCRIPT:-/opt/hermes-railway/scripts/opencode-volume-maintain.sh}"

mkdir -p "${DATA_ROOT}/logs"

while true; do
  sleep "${INTERVAL}"
  if [ -f "${MAINTAIN}" ]; then
    bash "${MAINTAIN}" >/dev/null 2>&1 || true
  fi
done
