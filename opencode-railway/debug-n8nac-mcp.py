#!/usr/bin/env python3
"""Diagnose n8nac MCP failure on OpenCode."""
from __future__ import annotations

import os
import time

import httpx

BASE = os.environ["OPENCODE_SERVER_URL"].rstrip("/")
AUTH = (os.environ.get("OPENCODE_SERVER_USER", "opencode"), os.environ["OPENCODE_SERVER_PASSWORD"])

COMMANDS = [
    ("git-remote", "git -C /data/workspace remote -v 2>&1; echo ===END_GIT==="),
    (
        "opencode-n8nac-config",
        'python3 -c "import json; d=json.load(open(\'/data/.config/opencode/opencode.json\')); print(json.dumps(d.get(\'mcp\',{}).get(\'n8nac\',{}), indent=2))"; echo ===END_CFG===',
    ),
    (
        "env-check",
        "bash -lc 'for v in N8N_NATIVE_MCP_URL N8N_NATIVE_MCP_TOKEN N8N_API_KEY; do printf \"%s=set\\n\" \"$v\"; done'; echo ===END_ENV===",
    ),
    (
        "n8nac-env-status",
        "cd /data/workspace && npx --yes n8nac env status --json 2>&1 | head -30; echo ===END_N8NAC===",
    ),
    (
        "mcp-stderr",
        "cd /data/workspace && N8N_AS_CODE_PROJECT_DIR=/data/workspace N8NAC_NATIVE_MCP_ENABLED=1 bash -lc 'timeout 15 npx -y @n8n-as-code/mcp 2>&1 | head -50'; echo ===END_MCP===",
    ),
    ("mcp-list", "opencode mcp list 2>&1 | grep -A4 n8nac; echo ===END_LIST==="),
]


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


def run_shell(client: httpx.Client, title: str, command: str, marker: str, timeout: int = 90) -> str:
    session = client.post(f"{BASE}/session", json={"title": title}).json()
    sid = session["id"]
    client.post(f"{BASE}/session/{sid}/shell", json={"agent": "build", "command": command})
    last = ""
    for _ in range(timeout // 3):
        time.sleep(3)
        out = bash_output(client, sid)
        if out:
            last = out
        if marker in out:
            return out
    return last


def main() -> None:
    with httpx.Client(timeout=300, auth=AUTH) as client:
        health = client.get(f"{BASE}/health", follow_redirects=True)
        print("health", health.status_code)
        for name, cmd in COMMANDS:
            marker = "===END_" + name.split("-")[-1].upper().replace("CONFIG", "CFG").replace("STDERR", "MCP").replace("LIST", "LIST") + "==="
            if name == "opencode-n8nac-config":
                marker = "===END_CFG==="
            elif name == "git-remote":
                marker = "===END_GIT==="
            elif name == "env-check":
                marker = "===END_ENV==="
            elif name == "n8nac-env-status":
                marker = "===END_N8NAC==="
            elif name == "mcp-stderr":
                marker = "===END_MCP==="
            elif name == "mcp-list":
                marker = "===END_LIST==="
            print(f"\n=== {name} ===")
            out = run_shell(client, f"n8nac-{name}", cmd, marker=marker, timeout=120)
            print(out[-4000:] if out else "(no output)")


if __name__ == "__main__":
    main()
