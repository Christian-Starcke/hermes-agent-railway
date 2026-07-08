#!/usr/bin/env python3
"""Repair broken n8nac MCP npx cache on OpenCode."""
from __future__ import annotations

import os
import time

import httpx

BASE = os.environ["OPENCODE_SERVER_URL"].rstrip("/")
AUTH = (os.environ.get("OPENCODE_SERVER_USER", "opencode"), os.environ["OPENCODE_SERVER_PASSWORD"])

FIX = (
    "rm -rf /data/.npm-cache/_npx; "
    "curl -fsSL https://raw.githubusercontent.com/Christian-Starcke/hermes-agent-railway/main/scripts/opencode-volume-maintain.sh "
    "-o /data/opencode-volume-maintain.sh && chmod +x /data/opencode-volume-maintain.sh; "
    "curl -fsSL https://raw.githubusercontent.com/Christian-Starcke/hermes-agent-railway/main/scripts/opencode-mcp-bootstrap.sh "
    "-o /data/opencode-mcp-bootstrap.sh && chmod +x /data/opencode-mcp-bootstrap.sh; "
    "bash /data/opencode-mcp-bootstrap.sh; "
    "cd /data/workspace && N8N_AS_CODE_PROJECT_DIR=/data/workspace N8NAC_NATIVE_MCP_ENABLED=1 "
    "timeout 60 npx -y @n8n-as-code/mcp --help 2>&1 | head -20; "
    "opencode mcp list 2>&1 | grep -A3 n8nac; "
    "echo ===FIX_DONE==="
)


def bash_output(client: httpx.Client, sid: str) -> str:
    msgs = client.get(f"{BASE}/session/{sid}/message").json()
    if not isinstance(msgs, list):
        return ""
    parts_out: list[str] = []
    for item in msgs:
        if not isinstance(item, dict):
            continue
        for part in item.get("parts", []):
            if part.get("type") == "tool" and part.get("tool") == "bash":
                state = part.get("state", {}) or {}
                meta = state.get("metadata") or {}
                parts_out.append(str(meta.get("output") or state.get("output") or ""))
    return "\n".join(parts_out)


def main() -> None:
    with httpx.Client(timeout=300, auth=AUTH) as client:
        session = client.post(f"{BASE}/session", json={"title": "fix-n8nac-mcp"}).json()
        sid = session["id"]
        client.post(f"{BASE}/session/{sid}/shell", json={"agent": "build", "command": FIX})
        last = ""
        for _ in range(60):
            time.sleep(5)
            out = bash_output(client, sid)
            if out:
                last = out
            if "===FIX_DONE===" in out:
                break
        print(last[-5000:].encode("ascii", "replace").decode("ascii"))


if __name__ == "__main__":
    main()
