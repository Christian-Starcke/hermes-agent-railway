"""JSON schemas for opencode-delegate plugin tools."""

TOOL_SCHEMAS = {
    "opencode_health": {
        "name": "opencode_health",
        "description": "Check OpenCode server health and version.",
        "parameters": {"type": "object", "properties": {}},
    },
    "opencode_list_agents": {
        "name": "opencode_list_agents",
        "description": "List available OpenCode agents (build, plan, custom).",
        "parameters": {"type": "object", "properties": {}},
    },
    "opencode_list_providers": {
        "name": "opencode_list_providers",
        "description": "List OpenCode LLM providers and default models.",
        "parameters": {"type": "object", "properties": {}},
    },
    "opencode_create_task": {
        "name": "opencode_create_task",
        "description": (
            "Delegate a coding task to OpenCode on Railway. Creates a remote session and "
            "starts async work. Never merge pull requests automatically — report back for approval."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "objective": {
                    "type": "string",
                    "description": "Short title for the delegation task.",
                },
                "prompt": {
                    "type": "string",
                    "description": "Detailed instructions for the OpenCode agent.",
                },
                "workspace_hint": {
                    "type": "string",
                    "description": "Optional path hint under /data/workspace (e.g. n8n-as-code).",
                },
                "acceptance_criteria": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Checklist the OpenCode agent must satisfy.",
                },
                "agent": {
                    "type": "string",
                    "description": "OpenCode agent name (default from OPENCODE_DEFAULT_AGENT).",
                },
                "model": {
                    "type": "string",
                    "description": "Model id, e.g. openrouter/anthropic/claude-sonnet-4.",
                },
            },
            "required": ["objective", "prompt"],
        },
    },
    "opencode_send_message": {
        "name": "opencode_send_message",
        "description": "Send a synchronous follow-up message to an OpenCode session.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Local task id."},
                "session_id": {"type": "string", "description": "OpenCode session id."},
                "prompt": {"type": "string", "description": "Follow-up instruction text."},
                "agent": {"type": "string", "description": "Optional agent override."},
                "model": {"type": "string", "description": "Optional model override."},
            },
            "required": ["prompt"],
        },
    },
    "opencode_get_task": {
        "name": "opencode_get_task",
        "description": "Get local task metadata and refresh status from OpenCode.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Local task id."},
                "session_id": {"type": "string", "description": "OpenCode session id."},
            },
        },
    },
    "opencode_list_tasks": {
        "name": "opencode_list_tasks",
        "description": "List locally tracked Hermes→OpenCode delegations.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter: pending, running, finished, error, cancelled.",
                },
                "limit": {"type": "integer", "description": "Max tasks (default 20)."},
            },
        },
    },
    "opencode_abort_task": {
        "name": "opencode_abort_task",
        "description": "Abort a running OpenCode session.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Local task id."},
                "session_id": {"type": "string", "description": "OpenCode session id."},
            },
        },
    },
}
