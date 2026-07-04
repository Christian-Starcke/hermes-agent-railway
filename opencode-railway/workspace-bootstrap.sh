#!/usr/bin/env bash
# OpenCode entrypoint: bootstrap prism-platform-ap workspace on /data/workspace.
set -euo pipefail

export WORKSPACE_ROOT="${OPENCODE_WORKSPACE:-/data/workspace}"
export WORKSPACE_BOOTSTRAP="${WORKSPACE_BOOTSTRAP:-true}"
export WORKSPACE_BOOTSTRAP_PREFIX="[opencode-bootstrap]"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHARED="${SCRIPT_DIR}/../scripts/prism-workspace-bootstrap.sh"
if [ -f "${SHARED}" ]; then
  exec bash "${SHARED}"
fi
if [ -f "/data/prism-workspace-bootstrap.sh" ]; then
  exec bash "/data/prism-workspace-bootstrap.sh"
fi
echo "[opencode-bootstrap] prism-workspace-bootstrap.sh not found" >&2
exit 1
