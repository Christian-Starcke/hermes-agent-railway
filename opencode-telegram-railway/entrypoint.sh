#!/bin/sh
set -eu

APP_HOME="${OPENCODE_TELEGRAM_HOME:-/data}"
ENV_FILE="${APP_HOME}/.env"
SETTINGS_FILE="${APP_HOME}/settings.json"

require_var() {
  name="$1"
  eval "value=\${$name:-}"
  if [ -z "$value" ]; then
    echo "[entrypoint] Missing required environment variable: $name" >&2
    exit 1
  fi
}

require_var TELEGRAM_BOT_TOKEN
require_var TELEGRAM_ALLOWED_USER_ID
require_var OPENCODE_MODEL_PROVIDER
require_var OPENCODE_MODEL_ID

mkdir -p "$APP_HOME"

cat > "$ENV_FILE" <<EOF
BOT_LOCALE=${BOT_LOCALE:-en}
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
TELEGRAM_ALLOWED_USER_ID=${TELEGRAM_ALLOWED_USER_ID}
OPENCODE_API_URL=${OPENCODE_API_URL:-http://localhost:4096}
OPENCODE_SERVER_USERNAME=${OPENCODE_SERVER_USERNAME:-opencode}
OPENCODE_SERVER_PASSWORD=${OPENCODE_SERVER_PASSWORD:-}
OPENCODE_MODEL_PROVIDER=${OPENCODE_MODEL_PROVIDER}
OPENCODE_MODEL_ID=${OPENCODE_MODEL_ID}
OPENCODE_AUTO_RESTART_ENABLED=${OPENCODE_AUTO_RESTART_ENABLED:-false}
LOG_LEVEL=${LOG_LEVEL:-info}
EOF

if [ ! -f "$SETTINGS_FILE" ]; then
  printf '{}\n' > "$SETTINGS_FILE"
fi

export OPENCODE_TELEGRAM_HOME="$APP_HOME"

echo "[entrypoint] Wrote ${ENV_FILE}"
echo "[entrypoint] OpenCode API: ${OPENCODE_API_URL:-http://localhost:4096}"
echo "[entrypoint] Starting opencode-telegram..."

exec opencode-telegram start
