#!/usr/bin/env python3
"""Bootstrap prism-platform-ap workspace on the OpenCode Railway service."""
from __future__ import annotations

import base64
import os
import shlex
import time
from pathlib import Path

import httpx

BASE = os.environ["OPENCODE_SERVER_URL"].rstrip("/")
AUTH = (os.environ.get("OPENCODE_SERVER_USER", "opencode"), os.environ["OPENCODE_SERVER_PASSWORD"])

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "prism-workspace-bootstrap.sh"


def _shell_script() -> str:
    shared_b64 = base64.b64encode(SCRIPT_PATH.read_bytes()).decode()
    env: dict[str, str] = {
        "OPENCODE_WORKSPACE": "/data/workspace",
        "WORKSPACE_BOOTSTRAP": "true",
        "WORKSPACE_BOOTSTRAP_PREFIX": "[opencode-bootstrap]",
    }
    for key in (
        "GITHUB_TOKEN",
        "GIT_REPO_N8N",
        "GIT_REPO_PLAYBOOK",
        "GIT_REPO_PLATFORM",
        "GIT_REPO_KNOWLEDGE",
        "N8N_API_KEY",
        "N8N_BASE_URL",
    ):
        value = os.environ.get(key, "")
        if value:
            env[key] = value
    env_prefix = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
    # OpenCode /session/{id}/shell mangles newlines — keep this one line.
    return (
        f"python3 -c \"import base64,pathlib; pathlib.Path('/data/prism-workspace-bootstrap.sh')"
        f".write_bytes(base64.b64decode('{shared_b64}'))\" "
        f"&& chmod +x /data/prism-workspace-bootstrap.sh "
        f"&& mkdir -p /data/workspace /data/logs "
        f"&& {env_prefix} bash /data/prism-workspace-bootstrap.sh"
    )


def _session_output(client: httpx.Client, sid: str) -> str:
    msgs = client.get(f"{BASE}/session/{sid}/message").json()
    return str(msgs)


def _bash_output(client: httpx.Client, sid: str) -> str:
    msgs = client.get(f"{BASE}/session/{sid}/message").json()
    for item in msgs:
        for part in item.get("parts", []):
            if part.get("type") == "tool" and part.get("tool") == "bash":
                meta = part.get("state", {}).get("metadata") or {}
                return str(meta.get("output", ""))
    return ""


def _verify_workspace(client: httpx.Client) -> bool:
    session = client.post(f"{BASE}/session", json={"title": "workspace-verify"}).json()
    sid = session["id"]
    cmd = "ls -la /data/workspace /data/workspace/prism-platform-ap 2>&1"
    client.post(f"{BASE}/session/{sid}/shell", json={"agent": "build", "command": cmd})
    for _ in range(60):
        time.sleep(5)
        out = _bash_output(client, sid)
        if "prism-platform" in out and "prism-playbook" in out:
            print(out[-2500:])
            return True
    print(_session_output(client, sid)[-2500:])
    return False


def main() -> None:
    cmd = _shell_script()
    with httpx.Client(timeout=300, auth=AUTH) as client:
        session = client.post(f"{BASE}/session", json={"title": "prism-workspace-bootstrap"}).json()
        sid = session["id"]
        print("session", sid)
        resp = client.post(f"{BASE}/session/{sid}/shell", json={"agent": "build", "command": cmd})
        print("shell status", resp.status_code)
        for i in range(120):
            time.sleep(10)
            out = _bash_output(client, sid)
            blob = _session_output(client, sid)
            if "workspace ready at" in out or "workspace ready at" in blob:
                print("bootstrap complete")
                print(out[-2500:] if out else blob[-2500:])
                if _verify_workspace(client):
                    print("workspace verified")
                return
            if out and ("fatal:" in out.lower() or "error:" in out.lower()):
                print("bootstrap failed:", out[-2500:])
                return
            print("waiting", i, "out_len", len(out))
        print("timeout; verifying workspace")
        if _verify_workspace(client):
            print("workspace verified after timeout")
        else:
            print("workspace not ready; session", sid)


if __name__ == "__main__":
    main()
