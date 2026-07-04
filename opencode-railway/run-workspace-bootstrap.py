#!/usr/bin/env python3
"""One-shot workspace bootstrap for OpenCode Railway service."""
from __future__ import annotations

import os
import time

import httpx

BASE = os.environ["OPENCODE_SERVER_URL"].rstrip("/")
AUTH = ("opencode", os.environ["OPENCODE_SERVER_PASSWORD"])
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

CMD = r"""
set -e
mkdir -p /data/workspace
""".strip()

if GITHUB_TOKEN:
    CMD += f'\ngit config --global url."https://{GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/" || true\n'

repos = [
    ("https://github.com/prism-platform-ap/n8n-as-code", "n8n-as-code"),
    ("https://github.com/prism-platform-ap/prism-playbook", "prism-playbook"),
    ("https://github.com/prism-platform-ap/prism-platform", "prism-platform"),
]
for url, name in repos:
    CMD += f"""
if [ -d "/data/workspace/{name}/.git" ]; then
  git -C "/data/workspace/{name}" pull --ff-only origin main || git -C "/data/workspace/{name}" pull --ff-only
else
  git clone --depth 1 "{url}" "/data/workspace/{name}"
fi
"""
CMD += "\nls -la /data/workspace\n"

with httpx.Client(timeout=300, auth=AUTH) as client:
    session = client.post(f"{BASE}/session", json={"title": "workspace-bootstrap"}).json()
    sid = session["id"]
    print("session", sid)
    resp = client.post(f"{BASE}/session/{sid}/shell", json={"agent": "build", "command": CMD})
    print("shell status", resp.status_code)
    for i in range(36):
        time.sleep(10)
        msgs = client.get(f"{BASE}/session/{sid}/message").json()
        blob = str(msgs)
        if "n8n-as-code" in blob and "prism-platform" in blob and "prism-playbook" in blob:
            print("bootstrap complete")
            break
        print("waiting", i)
    else:
        print("timeout; check session manually")
