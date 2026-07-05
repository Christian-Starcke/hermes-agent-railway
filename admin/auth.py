"""Shared auth helpers for wrapper routes."""

from __future__ import annotations

from starlette.requests import Request


async def is_authenticated(request: Request) -> bool:
    """Probe hermes-webui session cookies via /api/onboarding/status."""
    import httpx

    from . import proxy as hermes_proxy

    cookie = request.headers.get("cookie", "")
    if not cookie:
        return False
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{hermes_proxy.WEBUI_BASE_URL}/api/onboarding/status",
                headers={
                    "cookie": cookie,
                    "host": f"{hermes_proxy.WEBUI_HOST}:{hermes_proxy.WEBUI_PORT}",
                },
            )
        return response.status_code == 200
    except (httpx.ConnectError, httpx.ReadTimeout):
        return False
