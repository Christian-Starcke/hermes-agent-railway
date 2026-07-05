"""POST /webhooks/cursor — Cursor Cloud Agent status webhooks."""

from __future__ import annotations

import json
import os

from starlette.requests import Request
from starlette.responses import JSONResponse

# Import plugin modules from the synced plugins directory or image bundle.
import sys
from pathlib import Path

_PLUGIN_DIRS = [
    Path(os.environ.get("HERMES_HOME", "/data")) / ".hermes" / "plugins" / "cursor-cloud",
    Path("/opt/hermes-railway/plugins/cursor-cloud"),
]
for _path in _PLUGIN_DIRS:
    if _path.is_dir() and str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from webhook import apply_webhook_payload, verify_signature  # noqa: E402


async def cursor_webhook(request: Request) -> JSONResponse:
    secret = os.environ.get("CURSOR_WEBHOOK_SECRET", "").strip()
    if not secret:
        return JSONResponse({"success": False, "error": "CURSOR_WEBHOOK_SECRET not configured"}, status_code=503)

    raw = await request.body()
    signature = request.headers.get("X-Webhook-Signature")
    if not verify_signature(secret, raw, signature):
        return JSONResponse({"success": False, "error": "invalid signature"}, status_code=401)

    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return JSONResponse({"success": False, "error": "invalid json"}, status_code=400)

    result = apply_webhook_payload(payload)
    status = 200 if result.get("success") else 400
    return JSONResponse(result, status_code=status)
