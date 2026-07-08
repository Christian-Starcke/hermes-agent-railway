# OpenCode Telegram Bot on Railway

Telegram bridge to the **opencode** Railway service using [@grinev/opencode-telegram-bot](https://github.com/grinev/opencode-telegram-bot).

Separate from the **hermes-agent** Telegram gateway — uses its own BotFather token.

## Architecture

```
Telegram (OpenCode bot) → opencode-telegram-bot service → opencode HTTP API
```

- Long-polling only — no public domain on this service
- Config persisted on `/data` volume (`OPENCODE_TELEGRAM_HOME`)
- Entrypoint writes `/data/.env` from Railway variables on every boot

## Railway service settings

| Setting | Value |
|---------|-------|
| Dockerfile path | `opencode-telegram-railway/Dockerfile` |
| Healthcheck | Disabled |
| Volume | `/data` |
| Public domain | None |

## Environment variables

Synced from connections-hub via `sync-railway.*`:

| Variable | Purpose |
|----------|---------|
| `TELEGRAM_BOT_TOKEN` | OpenCode-dedicated bot (not Hermes bot) |
| `TELEGRAM_ALLOWED_USER_ID` | Your numeric Telegram user ID |
| `OPENCODE_API_URL` | OpenCode public URL |
| `OPENCODE_SERVER_USERNAME` | `opencode` |
| `OPENCODE_SERVER_PASSWORD` | Basic auth password |
| `OPENCODE_MODEL_PROVIDER` | `openrouter` |
| `OPENCODE_MODEL_ID` | `z-ai/glm-5.2` |
| `OPENCODE_AUTO_RESTART_ENABLED` | `false` |
| `OPENCODE_TELEGRAM_HOME` | `/data` |

## Limitations

- `/opencode_start` and `/opencode_stop` require a local OpenCode process — not available in this remote setup
- TUI session tracking requires a shared local port — use Telegram-initiated sessions instead

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| TTY required / wizard prompt | Entrypoint failed to write `.env` — check required vars |
| HTTP 409 from Telegram | Bot token shared with Hermes gateway — use a separate token |
| 401 to OpenCode | Re-sync `OPENCODE_SERVER_PASSWORD` |
| Telegram network errors | Set `TELEGRAM_FORCE_IPV4=true` on Railway |
