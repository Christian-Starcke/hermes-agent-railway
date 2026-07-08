#!/usr/bin/env python3
"""One-shot OpenCode /data volume cleanup via HTTP session shell."""
from __future__ import annotations

import os
import sys
import time

import httpx

CLEANUP = r"""
set -e
echo '=== before ==='
df -h /data
du -xh --max-depth=2 /data 2>/dev/null | sort -hr | head -15
rm -rf /data/workspace/prism-platform-ap/n8n-as-code
rm -rf /data/workspace/prism-platform-ap/prism-playbook
rm -rf /data/workspace/prism-platform-ap/prism-knowledge
rm -rf /data/.npm-global/.npm/_cacache /data/.npm/_cacache /root/.npm/_cacache 2>/dev/null || true
find /data/workspace -name node_modules -type d -prune -exec rm -rf {} + 2>/dev/null || true
git -C /data/workspace gc --prune=now 2>/dev/null || true
git -C /data/workspace/prism-platform-ap/prism-platform gc --prune=now 2>/dev/null || true
echo '=== after ==='
df -h /data
du -xh --max-depth=2 /data 2>/dev/null | sort -hr | head -15
"""


def bash_output(client: httpx.Client, sid: str) -> str:
    msgs = client.get(f"{BASE}/session/{sid}/message").json()
    for item in msgs:
        for part in item.get("parts", []):
            if part.get("type") == "tool" and part.get("tool") == "bash":
                meta = part.get("state", {}).get("metadata") or {}
                return str(meta.get("output", ""))
    return ""


def run_shell(client: httpx.Client, title: str, command: str, timeout: int = 300) -> str:
    session = client.post(f"{BASE}/session", json={"title": title}).json()
    sid = session["id"]
    client.post(f"{BASE}/session/{sid}/shell", json={"agent": "build", "command": command})
    for _ in range(timeout // 5):
        time.sleep(5)
        out = bash_output(client, sid)
        if out and "=== after ===" in out:
            return out
    return bash_output(client, sid)


def main() -> None:
    global BASE
    BASE = os.environ["OPENCODE_SERVER_URL"].rstrip("/")
    auth = (os.environ.get("OPENCODE_SERVER_USER", "opencode"), os.environ["OPENCODE_SERVER_PASSWORD"])
    with httpx.Client(timeout=300, auth=auth) as client:
        health = client.get(f"{BASE}/health", follow_redirects=True)
        print("health", health.status_code)
        if health.status_code >= 400:
            sys.exit(1)
        out = run_shell(client, "volume-cleanup", CLEANUP)
        print(out[-8000:])


if __name__ == "__main__":
    main()
