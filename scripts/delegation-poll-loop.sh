#!/usr/bin/env bash
# Background delegation poll loop (Cursor + OpenCode task sync).
set -euo pipefail

export HERMES_HOME="${HERMES_HOME:-/data}"
export PATH="/opt/hermes/.venv/bin:/data/.local/bin:${PATH}"

INTERVAL="${DELEGATION_POLL_INTERVAL_SEC:-600}"

while true; do
  if [ -f "/data/.hermes/plugins/cursor-cloud/poll_pending.py" ]; then
    python3 /data/.hermes/plugins/cursor-cloud/poll_pending.py >> /data/logs/cursor-poll.log 2>&1 || true
  fi
  if [ -f "/data/.hermes/plugins/opencode-delegate/poll_pending.py" ]; then
    python3 /data/.hermes/plugins/opencode-delegate/poll_pending.py >> /data/logs/opencode-poll.log 2>&1 || true
  fi
  sleep "${INTERVAL}"
done
