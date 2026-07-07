#!/usr/bin/env python3
"""Verify 13 MCP servers on OpenCode after connections-hub sync."""
from __future__ import annotations

import os
import re
import time

import httpx

BASE = os.environ["OPENCODE_SERVER_URL"].rstrip("/")
AUTH = (os.environ.get("OPENCODE_SERVER_USER", "opencode"), os.environ["OPENCODE_SERVER_PASSWORD"])

EXPECTED = {
    "github",
    "firecrawl",
    "searxng",
    "railway",
    "retellai",
    "supabase",
    "resend",
    "n8nac",
    "openrouter",
    "vercel",
    "sentry",
    "better_stack",
    "posthog",
}


def bash_output(client: httpx.Client, sid: str) -> str:
    msgs = client.get(f"{BASE}/session/{sid}/message").json()
    for item in msgs:
        for part in item.get("parts", []):
            if part.get("type") == "tool" and part.get("tool") == "bash":
                meta = part.get("state", {}).get("metadata") or {}
                return str(meta.get("output", ""))
    return ""


def run_shell(client: httpx.Client, title: str, command: str, timeout: int = 120) -> str:
    session = client.post(f"{BASE}/session", json={"title": title}).json()
    sid = session["id"]
    client.post(f"{BASE}/session/{sid}/shell", json={"agent": "build", "command": command})
    for _ in range(timeout // 5):
        time.sleep(5)
        out = bash_output(client, sid)
        if out and not out.strip().endswith("..."):
            return out
    return bash_output(client, sid)


def main() -> None:
    mcp_cmd = (
        "bash -lc '"
        "export PATH=/data/.npm-global/bin:/usr/local/bin:$PATH; "
        "export RAILWAY_TOKEN=${RAILWAY_API_TOKEN:-}; "
        "which opencode 2>&1; "
        "opencode mcp list 2>&1"
        "'"
    )
    smoke_cmd = (
        "bash -lc '"
        "export PATH=/data/.npm-global/bin:$PATH; "
        "export RAILWAY_TOKEN=${RAILWAY_API_TOKEN:-}; "
        "railway whoami 2>&1; "
        "echo ---; "
        "test -f /data/opencode-mcp-bootstrap.sh && echo mcp-bootstrap-present; "
        "echo OPENCODE_CONFIG_HAS_MCP=$(python3 -c \"import os; print(\\\"mcp\\\" in os.environ.get(\\\"OPENCODE_CONFIG_CONTENT\\\",\\\"\\\"))\" 2>/dev/null || echo unknown)"
        "'"
    )

    with httpx.Client(timeout=300, auth=AUTH) as client:
        health = client.get(f"{BASE}/health", follow_redirects=True)
        print("health", health.status_code)

        mcp_out = run_shell(client, "verify-mcp-list", mcp_cmd)
        print("=== mcp list ===")
        print(mcp_out[-4000:].encode("ascii", "replace").decode("ascii"))

        found = set(re.findall(r"\b([a-z_]+)\b", mcp_out.lower()))
        matched = EXPECTED & found
        print(f"matched {len(matched)}/13:", sorted(matched))

        smoke = run_shell(client, "verify-smoke", smoke_cmd)
        print("=== smoke ===")
        print(smoke[-2000:].encode("ascii", "replace").decode("ascii"))


if __name__ == "__main__":
    main()
