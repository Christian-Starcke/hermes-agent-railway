"""Local smoke test for paperclip plugin configuration (optional live API)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    required = ["PAPERCLIP_BASE_URL", "PAPERCLIP_API_TOKEN", "PAPERCLIP_COMPANY_ID"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        print(json.dumps({"success": False, "error": f"Missing env: {', '.join(missing)}"}))
        return 1

    from paperclip_client import PaperclipClient  # noqa: WPS433
    import tools  # noqa: WPS433

    client = PaperclipClient()
    health = client.health()
    print(json.dumps({"success": True, "step": "health", "health": health}, indent=2))

    agents = client.list_agents()
    print(json.dumps({"success": True, "step": "list_agents", "agents": agents}, indent=2))

    if os.environ.get("PAPERCLIP_SMOKE_DELEGATE") == "1":
        result = json.loads(
            tools.handle_delegate_coding_task(
                {
                    "objective": "Paperclip smoke test",
                    "prompt": "No code changes needed — acknowledge this test issue.",
                    "repository": os.environ.get("PAPERCLIP_DEFAULT_REPOSITORY", "owner/repo"),
                }
            )
        )
        print(json.dumps({"success": True, "step": "delegate", "result": result}, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
