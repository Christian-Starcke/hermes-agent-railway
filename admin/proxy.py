"""Reverse proxy: forwards `/*` (HTTP and WebSocket) to hermes-webui on loopback.

Target host/port come from ``HERMES_WEBUI_HOST`` / ``HERMES_WEBUI_PORT``
(default ``127.0.0.1:9120``). The upstream ``hermes dashboard`` CLI usually listens on
**9119** loopback — start it manually (often from ``/tui``). ``admin/dashboard_proxy`` exposes
that UI under ``/hermes-dashboard`` with ``X-Forwarded-Prefix`` so the SPA resolves assets
behind Railway's single public ``PORT`` without binding dashboard to ``0.0.0.0``.

hermes-webui owns auth, session cookies, SSE chat streams, and almost the entire
public surface. Our wrapper sits in front purely so we can also serve `/tui`
(OAuth shortcuts + free-form shell) on the same public port.

Header treatment:
- Hop-by-hop headers stripped (connection, keep-alive, transfer-encoding, etc.).
- `Host` rewritten to the loopback target.
- `Origin` rewritten to the loopback target so hermes-webui's same-origin checks pass.
- `X-Forwarded-*`, `Forwarded`, `Via` dropped so the upstream sees a direct local request.

HTTP responses are streamed end-to-end (important for SSE chat).
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx
import websockets
import yaml
from starlette.requests import Request
from starlette.responses import StreamingResponse, Response
from starlette.websockets import WebSocket, WebSocketDisconnect


def _webui_listen_port(raw: str | None, default: int = 9120) -> int:
    if not raw:
        return default
    try:
        p = int(str(raw).strip(), 10)
        return p if 1 <= p <= 65535 else default
    except ValueError:
        return default


WEBUI_HOST = (os.environ.get("HERMES_WEBUI_HOST") or "127.0.0.1").strip() or "127.0.0.1"
WEBUI_PORT = _webui_listen_port(os.environ.get("HERMES_WEBUI_PORT"))

WEBUI_BASE_URL = f"http://{WEBUI_HOST}:{WEBUI_PORT}"
WEBUI_WS_BASE = f"ws://{WEBUI_HOST}:{WEBUI_PORT}"

# Hermes OpenAI-compatible API server (started by `hermes gateway` when
# API_SERVER_ENABLED=true). Bound on loopback by default; this wrapper exposes
# selected routes on the public Railway PORT so Orchestrator / Open WebUI can
# call Bearer-auth endpoints without a separate TCP proxy.
def _api_listen_port(raw: str | None, default: int = 8642) -> int:
    if not raw:
        return default
    try:
        p = int(str(raw).strip(), 10)
        return p if 1 <= p <= 65535 else default
    except ValueError:
        return default


API_SERVER_HOST = (os.environ.get("API_SERVER_PROXY_HOST") or "127.0.0.1").strip() or "127.0.0.1"
API_SERVER_PORT = _api_listen_port(os.environ.get("API_SERVER_PORT"))
API_SERVER_BASE_URL = f"http://{API_SERVER_HOST}:{API_SERVER_PORT}"

HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/data"))
CONFIG_PATH = HERMES_HOME / "config.yaml"
AUTH_PATH = HERMES_HOME / "auth.json"
_config_provider_cache: tuple[float, str | None] | None = None
_oauth_cache: tuple[float, float, bool] | None = None


def _public_api_key(request: Request) -> str | None:
    """API key from public request.

    Railway's edge (hikari) often blocks inbound ``Authorization: Bearer``.
    Prefer ``X-Hermes-API-Key`` on the public face; still accept Bearer when
    the edge allows it (local/dev).
    """
    custom = (request.headers.get("x-hermes-api-key") or "").strip()
    if custom:
        return custom
    auth = (request.headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        return token or None
    return None


# Public mount for the API server.
# Railway hikari on this host empty-403s bare `/v1/*` and blackholes mounts
# after repeated 502/503s (/hapi, /xapi, /orch). Default `/hm`. Orchestrator:
# HERMES_API_URL=https://<host>/hm
API_PUBLIC_PREFIX = (os.environ.get("API_PUBLIC_PREFIX") or "/hm").strip() or "/hm"
if not API_PUBLIC_PREFIX.startswith("/"):
    API_PUBLIC_PREFIX = "/" + API_PUBLIC_PREFIX
API_PUBLIC_PREFIX = API_PUBLIC_PREFIX.rstrip("/") or "/hm"

# Friendly public paths under the mount → API-server paths (avoids edge-blocked
# shapes like bare `/v1/...` when clients call `{mount}/models`).
_API_MOUNT_ALIASES = {
    "/models": "/v1/models",
    "/chat/completions": "/v1/chat/completions",
}


def _api_upstream_path(path: str, bare_path: str) -> str:
    """Map public path → API-server path (strip mount + apply aliases)."""
    query = ""
    if "?" in path:
        _, query = path.split("?", 1)
        query = "?" + query
    for prefix in (API_PUBLIC_PREFIX, "/hapi", "/xapi", "/orch"):
        if bare_path == prefix or bare_path.startswith(prefix + "/"):
            stripped = bare_path[len(prefix) :] or "/"
            stripped = _API_MOUNT_ALIASES.get(stripped, stripped)
            return stripped + query
    return (bare_path + query) if bare_path else path


def _is_api_mount(bare_path: str) -> bool:
    for prefix in (API_PUBLIC_PREFIX, "/hapi", "/xapi", "/orch"):
        if bare_path == prefix or bare_path.startswith(prefix + "/"):
            return True
    return False


def _wants_api_server(request: Request, bare_path: str) -> bool:
    """Route API-server paths under the public mount only.

    Do not steal bare `/api/sessions` from WebUI — that path is cookie-auth and
    also gets edge-blocked when we 502 from a down API server. Orchestrator
    always uses `{HERMES_API_URL}/api/sessions` with HERMES_API_URL ending in
    the mount (e.g. `/hm`).
    """
    del request
    if _is_api_mount(bare_path):
        return True
    # Bare /v1 is edge-blocked on this host; keep mapping for local/dev only.
    if bare_path == "/v1" or bare_path.startswith("/v1/"):
        return True
    return False


def _oauth_configured() -> bool:
    """True iff auth.json contains a provider matching config.yaml's model.provider.

    Used to suppress the WebUI onboarding wizard after `/tui` OAuth completes:
    upstream's auto-complete (`config_auto_completed`) requires `chat_ready`,
    which requires `imports_ok`, which can briefly flicker False while the
    webui process restarts after our heal step. During that window the wizard
    re-renders. mtime-cached so this costs ~zero on the hot path.
    """
    global _oauth_cache
    try:
        cfg_mtime = CONFIG_PATH.stat().st_mtime
        auth_mtime = AUTH_PATH.stat().st_mtime
    except OSError:
        return False
    if _oauth_cache and _oauth_cache[0] == cfg_mtime and _oauth_cache[1] == auth_mtime:
        return _oauth_cache[2]
    ok = False
    try:
        cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        auth = json.loads(AUTH_PATH.read_text(encoding="utf-8")) or {}
        providers = auth.get("providers") if isinstance(auth.get("providers"), dict) else {}
        # `hermes auth add <X> --type oauth` writes to auth.json["credential_pool"][<X>],
        # not auth.json["providers"][<X>]. Accept either as proof of OAuth setup.
        pool = auth.get("credential_pool") if isinstance(auth.get("credential_pool"), dict) else {}
        model_cfg = cfg.get("model") if isinstance(cfg.get("model"), dict) else {}
        prov = (model_cfg.get("provider") or "").strip()
        pool_entries = pool.get(prov) if prov else None
        ok = bool(
            prov
            and (prov in providers
                 or (isinstance(pool_entries, list) and len(pool_entries) > 0))
        )
    except (OSError, yaml.YAMLError, json.JSONDecodeError):
        ok = False
    _oauth_cache = (cfg_mtime, auth_mtime, ok)
    return ok


def _active_provider() -> str | None:
    """Return model.provider from config.yaml, with mtime-based caching.

    Workaround for hermes-webui upstream bug: when /api/session/new is called
    with no model_provider, the server stores model_provider=null on the new
    session even when catalog.active_provider is correctly set. The agent then
    can't determine credentials at chat-start time. We patch the request body
    to inject the provider before forwarding.
    """
    global _config_provider_cache
    try:
        mtime = CONFIG_PATH.stat().st_mtime
    except OSError:
        return None
    if _config_provider_cache and _config_provider_cache[0] == mtime:
        return _config_provider_cache[1]
    try:
        cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    model_cfg = cfg.get("model")
    provider = (model_cfg or {}).get("provider") if isinstance(model_cfg, dict) else None
    if isinstance(provider, str):
        provider = provider.strip() or None
    else:
        provider = None
    _config_provider_cache = (mtime, provider)
    return provider


HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}

DROPPED_REQUEST_HEADERS = HOP_BY_HOP | {
    "host",
    "x-forwarded-for",
    "x-forwarded-proto",
    "x-forwarded-host",
    "x-forwarded-port",
    "x-forwarded-server",
    "x-real-ip",
    "forwarded",
    "via",
}

# Keep `content-encoding` so the client knows the body is gzipped; we forward
# the raw bytes via aiter_raw() and don't re-encode. Drop content-length because
# StreamingResponse sets `Transfer-Encoding: chunked` which conflicts.
DROPPED_RESPONSE_HEADERS = HOP_BY_HOP | {"content-length"}

PROXY_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


_client: httpx.AsyncClient | None = None
_api_client: httpx.AsyncClient | None = None


def filter_upstream_request_headers(
    headers,
    *,
    upstream_host: str,
    upstream_port: int,
    forwarded_prefix: str | None = None,
) -> dict[str, str]:
    upstream = {
        k: v for k, v in headers.items() if k.lower() not in DROPPED_REQUEST_HEADERS
    }
    upstream["host"] = f"{upstream_host}:{upstream_port}"
    upstream = {k: v for k, v in upstream.items() if k.lower() != "origin"}
    upstream["origin"] = f"http://{upstream_host}:{upstream_port}"
    if forwarded_prefix:
        upstream["x-forwarded-prefix"] = forwarded_prefix
    return upstream


def _filter_request_headers(headers) -> dict[str, str]:
    return filter_upstream_request_headers(
        headers,
        upstream_host=WEBUI_HOST,
        upstream_port=WEBUI_PORT,
        forwarded_prefix=None,
    )


def _filter_response_headers(headers) -> list[tuple[str, str]]:
    return [(k, v) for k, v in headers.items() if k.lower() not in DROPPED_RESPONSE_HEADERS]


async def _ensure_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=WEBUI_BASE_URL,
            timeout=httpx.Timeout(connect=5.0, read=None, write=None, pool=5.0),
            follow_redirects=False,
        )
    return _client


async def _ensure_api_client() -> httpx.AsyncClient:
    global _api_client
    if _api_client is None:
        _api_client = httpx.AsyncClient(
            base_url=API_SERVER_BASE_URL,
            timeout=httpx.Timeout(connect=5.0, read=None, write=None, pool=5.0),
            follow_redirects=False,
        )
    return _api_client


async def _proxy_to_api_server(request: Request, path: str) -> Response:
    bare_upstream = path.split("?", 1)[0]
    # Never 5xx the mount health path — Railway hikari blackholes mounts after
    # repeated upstream failures. Return 200 with a clear payload instead.
    if request.method in ("GET", "HEAD") and bare_upstream in ("/health", "/"):
        try:
            client = await _ensure_api_client()
            upstream = await client.get(path, timeout=2.0)
            if upstream.status_code < 500:
                return Response(
                    content=upstream.content,
                    status_code=upstream.status_code,
                    media_type=upstream.headers.get("content-type") or "application/json",
                )
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.HTTPError):
            pass
        return Response(
            content=json.dumps(
                {
                    "status": "starting",
                    "service": "hermes-api-mount",
                    "detail": "API server not ready yet",
                }
            ),
            status_code=200,
            media_type="application/json",
        )

    client = await _ensure_api_client()
    body = await request.body()
    # Minimal loopback headers only. Forwarding browser Origin/Cookie/etc. has
    # produced empty HTTP 403 from the API server even with a valid Bearer key.
    server_key = (os.environ.get("API_SERVER_KEY") or "").strip()
    provided = _public_api_key(request)
    if not server_key:
        return Response(
            "API_SERVER_KEY is not configured on this service.",
            status_code=503,
            media_type="text/plain",
        )
    if provided != server_key:
        return Response(
            json.dumps({"error": "Unauthorized", "detail": "Invalid or missing X-Hermes-API-Key"}),
            status_code=401,
            media_type="application/json",
        )
    upstream_headers = {
        "host": f"{API_SERVER_HOST}:{API_SERVER_PORT}",
        "authorization": f"Bearer {server_key}",
        "accept": "application/json",
    }
    content_type = (request.headers.get("content-type") or "").strip()
    if content_type:
        upstream_headers["content-type"] = content_type
    try:
        req = client.build_request(
            request.method,
            path,
            headers=upstream_headers,
            content=body if body else None,
        )
        upstream = await client.send(req, stream=True)
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
        # Prefer 503 over 502 for non-health routes. Health never reaches here.
        return Response(
            "Hermes API server unavailable. Ensure API_SERVER_ENABLED=true and the gateway is running.",
            status_code=503,
            media_type="text/plain",
            headers={"Retry-After": "5"},
        )

    async def body_iter():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()

    return StreamingResponse(
        body_iter(),
        status_code=upstream.status_code,
        headers=dict(_filter_response_headers(upstream.headers)),
        media_type=upstream.headers.get("content-type"),
    )


async def http_proxy(request: Request) -> Response:
    raw_path = request.path_params.get("path", "")
    path = "/" + raw_path if not raw_path.startswith("/") else raw_path
    bare_path = path.split("?", 1)[0]
    if request.url.query:
        path = f"{path}?{request.url.query}"

    if _wants_api_server(request, bare_path):
        return await _proxy_to_api_server(
            request, _api_upstream_path(path, bare_path)
        )

    client = await _ensure_client()
    upstream_headers = _filter_request_headers(request.headers)

    body = await request.body()

    # Workaround for upstream hermes-webui: new sessions are persisted with
    # model_provider=null even when catalog.active_provider is set. Inject
    # model_provider from /data/config.yaml when the client doesn't supply one.
    if request.method == "POST" and bare_path == "/api/session/new":
        provider = _active_provider()
        if provider:
            try:
                payload = json.loads(body) if body else {}
                if isinstance(payload, dict) and not (payload.get("model_provider") or "").strip():
                    payload["model_provider"] = provider
                    body = json.dumps(payload).encode("utf-8")
                    upstream_headers = {
                        k: v for k, v in upstream_headers.items() if k.lower() != "content-length"
                    }
                    upstream_headers["content-type"] = "application/json"
            except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
                pass

    try:
        req = client.build_request(
            request.method,
            path,
            headers=upstream_headers,
            content=body if body else None,
        )
        upstream = await client.send(req, stream=True)
    except httpx.ConnectError:
        return Response(
            "Hermes WebUI unavailable.",
            status_code=502,
            media_type="text/plain",
        )

    # Workaround for upstream wizard race: when OAuth is configured but the
    # webui process is mid-restart (chat_ready=False because imports flicker),
    # `/api/onboarding/status` returns completed=false and the wizard re-renders.
    # Buffer the response and force completed=true when auth.json proves OAuth
    # is set up. Only buffers this single small JSON endpoint — every other
    # response (SSE chat, large payloads) streams unchanged.
    if (
        request.method == "GET"
        and bare_path == "/api/onboarding/status"
        and upstream.status_code == 200
        and _oauth_configured()
    ):
        try:
            raw = await upstream.aread()
            await upstream.aclose()
            payload = json.loads(raw)
            if isinstance(payload, dict) and payload.get("completed") is not True:
                payload["completed"] = True
            mutated = json.dumps(payload).encode("utf-8")
            headers = [
                (k, v)
                for k, v in _filter_response_headers(upstream.headers)
                if k.lower() not in ("content-encoding",)
            ]
            return Response(
                content=mutated,
                status_code=upstream.status_code,
                headers=dict(headers),
                media_type="application/json",
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass  # fall through to streaming the original body

    async def body_iter():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()

    return StreamingResponse(
        body_iter(),
        status_code=upstream.status_code,
        headers=dict(_filter_response_headers(upstream.headers)),
        media_type=upstream.headers.get("content-type"),
    )


async def ws_proxy(websocket: WebSocket) -> None:
    raw_path = websocket.path_params.get("path", "")
    path = "/" + raw_path if not raw_path.startswith("/") else raw_path
    qs = websocket.scope.get("query_string", b"").decode()
    if qs:
        path = f"{path}?{qs}"
    upstream_url = WEBUI_WS_BASE + path
    subprotocols = websocket.scope.get("subprotocols") or None

    await websocket.accept(subprotocol=(subprotocols[0] if subprotocols else None))

    try:
        async with websockets.connect(
            upstream_url,
            subprotocols=subprotocols,
            origin=WEBUI_BASE_URL,
            open_timeout=5,
            ping_interval=None,
        ) as upstream:

            async def client_to_upstream() -> None:
                try:
                    while True:
                        msg = await websocket.receive()
                        if msg["type"] == "websocket.disconnect":
                            return
                        if "text" in msg and msg["text"] is not None:
                            await upstream.send(msg["text"])
                        elif "bytes" in msg and msg["bytes"] is not None:
                            await upstream.send(msg["bytes"])
                except (WebSocketDisconnect, websockets.ConnectionClosed):
                    return

            async def upstream_to_client() -> None:
                try:
                    async for msg in upstream:
                        if isinstance(msg, str):
                            await websocket.send_text(msg)
                        else:
                            await websocket.send_bytes(msg)
                except websockets.ConnectionClosed:
                    return

            done, pending = await asyncio.wait(
                {
                    asyncio.create_task(client_to_upstream()),
                    asyncio.create_task(upstream_to_client()),
                },
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
    except (websockets.WebSocketException, OSError):
        pass
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass
