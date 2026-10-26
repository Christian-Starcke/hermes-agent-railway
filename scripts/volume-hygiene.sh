#!/usr/bin/env bash
# Hermes-native cron entry point for the shared conservative volume policy.
set -euo pipefail

exec bash /opt/hermes-railway/scripts/opencode-volume-maintain.sh
