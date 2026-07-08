#!/usr/bin/env python3
"""One-shot OpenCode /data volume cleanup + script seed via HTTP session shell."""
from __future__ import annotations

import os
import sys
import time

import httpx

CLEANUP = (
    "df -h /data; "
    "du -xh --max-depth=2 /data 2>/dev/null | sort -hr | awk 'NR<=15'; "
    "rm -rf /data/workspace/prism-platform-ap/n8n-as-code "
    "/data/workspace/prism-platform-ap/prism-playbook "
    "/data/workspace/prism-platform-ap/prism-knowledge "
    "/data/.npm-global/.npm/_cacache /data/.npm/_cacache /root/.npm/_cacache 2>/dev/null; "
    "find /data/workspace -name node_modules -type d -prune -exec rm -rf {} + 2>/dev/null; "
    "test -d /data/workspace/.git && git -C /data/workspace gc --prune=now 2>/dev/null; "
    "test -d /data/workspace/prism-platform-ap/prism-platform/.git && "
    "git -C /data/workspace/prism-platform-ap/prism-platform gc --prune=now 2>/dev/null; "
    "echo '=== after ==='; df -h /data; "
    "du -xh --max-depth=2 /data 2>/dev/null | sort -hr | awk 'NR<=15'"
)

SEED = (
    "mkdir -p /data/cron /data/logs; "
    "curl -fsSL https://raw.githubusercontent.com/Christian-Starcke/hermes-agent-railway/main/scripts/opencode-volume-maintain.sh "
    "-o /data/opencode-volume-maintain.sh && chmod +x /data/opencode-volume-maintain.sh && echo seeded-maintain; "
    "curl -fsSL https://raw.githubusercontent.com/Christian-Starcke/hermes-agent-railway/main/scripts/opencode-mcp-bootstrap.sh "
    "-o /data/opencode-mcp-bootstrap.sh && chmod +x /data/opencode-mcp-bootstrap.sh && echo seeded-mcp; "
    "curl -fsSL https://raw.githubusercontent.com/Christian-Starcke/hermes-agent-railway/main/scripts/opencode-workspace-ensure.sh "
    "-o /data/opencode-workspace-ensure.sh && chmod +x /data/opencode-workspace-ensure.sh && echo seeded-ensure; "
    "curl -fsSL https://raw.githubusercontent.com/Christian-Starcke/hermes-agent-railway/main/scripts/opencode-workspace-prep-test.sh "
    "-o /data/opencode-workspace-prep-test.sh && chmod +x /data/opencode-workspace-prep-test.sh && echo seeded-prep; "
    "curl -fsSL https://raw.githubusercontent.com/Christian-Starcke/hermes-agent-railway/main/scripts/prism-workspace-bootstrap.sh "
    "-o /data/prism-workspace-bootstrap.sh && chmod +x /data/prism-workspace-bootstrap.sh && echo seeded-prism; "
    "curl -fsSL https://raw.githubusercontent.com/Christian-Starcke/hermes-agent-railway/main/opencode-railway/workspace-bootstrap.sh "
    "-o /data/workspace-bootstrap.sh && chmod +x /data/workspace-bootstrap.sh && echo seeded-bootstrap; "
    "curl -fsSL https://raw.githubusercontent.com/Christian-Starcke/hermes-agent-railway/main/opencode-railway/opencode-volume-maintain-loop.sh "
    "-o /data/cron/opencode-volume-maintain-loop.sh && chmod +x /data/cron/opencode-volume-maintain-loop.sh && echo seeded-loop; "
    "bash /data/opencode-volume-maintain.sh; "
    "echo '=== seed done ==='"
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


def run_shell(client: httpx.Client, title: str, command: str, timeout: int = 300, marker: str = "=== after ===") -> str:
    session = client.post(f"{BASE}/session", json={"title": title}).json()
    sid = session["id"]
    client.post(f"{BASE}/session/{sid}/shell", json={"agent": "build", "command": command})
    last = ""
    for _ in range(timeout // 5):
        time.sleep(5)
        out = bash_output(client, sid)
        if out:
            last = out
        if marker in out:
            return out
    return last


def main() -> None:
    global BASE
    BASE = os.environ["OPENCODE_SERVER_URL"].rstrip("/")
    auth = (os.environ.get("OPENCODE_SERVER_USER", "opencode"), os.environ["OPENCODE_SERVER_PASSWORD"])
    with httpx.Client(timeout=300, auth=auth) as client:
        health = client.get(f"{BASE}/health", follow_redirects=True)
        print("health", health.status_code)
        if health.status_code >= 400:
            sys.exit(1)
        out = run_shell(client, "volume-cleanup", CLEANUP, marker="=== after ===")
        print("=== cleanup ===")
        print(out[-6000:])
        seed = run_shell(client, "seed-scripts", SEED, marker="=== seed done ===")
        print("=== seed ===")
        print(seed[-4000:])


if __name__ == "__main__":
    main()
