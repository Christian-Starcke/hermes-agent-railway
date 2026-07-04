#!/usr/bin/env python3
"""Install opencode-mcp-bootstrap.sh on the OpenCode Railway volume."""
from __future__ import annotations

import base64
import os
import time
from pathlib import Path

import httpx

BASE = os.environ["OPENCODE_SERVER_URL"].rstrip("/")
AUTH = (os.environ.get("OPENCODE_SERVER_USER", "opencode"), os.environ["OPENCODE_SERVER_PASSWORD"])

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "opencode-mcp-bootstrap.sh"


def _shell_script() -> str:
    script_b64 = base64.b64encode(SCRIPT_PATH.read_bytes()).decode()
    return (
        f"python3 -c \"import base64,pathlib; pathlib.Path('/data/opencode-mcp-bootstrap.sh')"
        f".write_bytes(base64.b64decode('{script_b64}'))\" "
        f"&& chmod +x /data/opencode-mcp-bootstrap.sh "
        f"&& bash /data/opencode-mcp-bootstrap.sh"
    )


def _bash_output(client: httpx.Client, sid: str) -> str:
    msgs = client.get(f"{BASE}/session/{sid}/message").json()
    for item in msgs:
        for part in item.get("parts", []):
            if part.get("type") == "tool" and part.get("tool") == "bash":
                meta = part.get("state", {}).get("metadata") or {}
                return str(meta.get("output", ""))
    return ""


def main() -> None:
    cmd = _shell_script()
    with httpx.Client(timeout=300, auth=AUTH) as client:
        session = client.post(f"{BASE}/session", json={"title": "opencode-mcp-bootstrap"}).json()
        sid = session["id"]
        print("session", sid)
        resp = client.post(f"{BASE}/session/{sid}/shell", json={"agent": "build", "command": cmd})
        print("shell status", resp.status_code)
        for i in range(60):
            time.sleep(5)
            out = _bash_output(client, sid)
            if "opencode config dir ready" in out:
                print(out[-2000:])
                return
            if out and ("error" in out.lower() or "fatal" in out.lower()):
                print("bootstrap failed:", out[-2000:])
                return
            print("waiting", i, "out_len", len(out))
        print("timeout; last output:", _bash_output(client, sid)[-2000:])


if __name__ == "__main__":
    main()
