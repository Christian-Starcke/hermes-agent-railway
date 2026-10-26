#!/usr/bin/env bash
# Behavioral regression test for conservative volume maintenance.
set -euo pipefail

SCRIPT="$(cd "$(dirname "$0")" && pwd)/opencode-volume-maintain.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT
DATA="${TMP}/data"

mkdir -p \
  "${DATA}/home/.npm/_cacache" \
  "${DATA}/home/.npm/_npx/stale" \
  "${DATA}/home/.npm/_npx/fresh" \
  "${DATA}/home/.cache/uv/archive-v0" \
  "${DATA}/logs" \
  "${DATA}/workspace/node_modules" \
  "${DATA}/backups"

printf 'cache\n' > "${DATA}/home/.npm/_cacache/package"
printf 'stale\n' > "${DATA}/home/.npm/_npx/stale/package"
printf 'fresh\n' > "${DATA}/home/.npm/_npx/fresh/package"
printf 'cache\n' > "${DATA}/home/.cache/uv/archive-v0/package"
printf 'old\n' > "${DATA}/logs/gateway.log.1"
printf 'recent\n' > "${DATA}/logs/gateway.log.2"
printf 'workspace\n' > "${DATA}/workspace/node_modules/keep"
printf 'backup\n' > "${DATA}/backups/keep"

touch -d '30 days ago' \
  "${DATA}/home/.npm/_npx/stale" \
  "${DATA}/logs/gateway.log.1"
touch -d '1 day ago' \
  "${DATA}/home/.npm/_npx/fresh" \
  "${DATA}/logs/gateway.log.2"

dd if=/dev/zero of="${DATA}/logs/mcp-stderr.log" bs=1M count=60 status=none
printf 'latest-log-line\n' >> "${DATA}/logs/mcp-stderr.log"

# A threshold of 1% proves even warning-level runs never delete user data.
RAILWAY_VOLUME_MOUNT_PATH="${DATA}" \
OPENCODE_VOLUME_WARN_THRESHOLD_PCT=1 \
  bash "${SCRIPT}"

[ ! -e "${DATA}/home/.npm/_cacache" ]
[ ! -e "${DATA}/home/.cache/uv" ]
[ ! -e "${DATA}/home/.npm/_npx/stale" ]
[ -f "${DATA}/home/.npm/_npx/fresh/package" ]
[ ! -e "${DATA}/logs/gateway.log.1" ]
[ -f "${DATA}/logs/gateway.log.2" ]
[ -f "${DATA}/workspace/node_modules/keep" ]
[ -f "${DATA}/backups/keep" ]
[ "$(wc -c < "${DATA}/logs/mcp-stderr.log")" -le 10485760 ]
grep -q 'latest-log-line' "${DATA}/logs/mcp-stderr.log"
[ ! -e "${DATA}/logs/mcp-stderr.log.maintain.tmp" ]

echo 'volume maintenance regression test: PASS'
