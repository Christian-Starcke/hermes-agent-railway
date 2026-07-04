#!/usr/bin/env python3
"""Poll pending OpenCode delegations. Used by Hermes cron and manual ops."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from sync import poll_pending_tasks  # noqa: E402


def main() -> int:
    result = poll_pending_tasks()
    print(json.dumps(result, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
