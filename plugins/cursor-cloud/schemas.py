"""JSON schemas for cursor-cloud plugin tools."""

TOOL_SCHEMAS = {
    "cursor_list_repositories": {
        "name": "cursor_list_repositories",
        "description": "List GitHub repositories accessible to Cursor Cloud Agents.",
        "parameters": {"type": "object", "properties": {}},
    },
    "cursor_create_agent": {
        "name": "cursor_create_agent",
        "description": (
            "Delegate a coding task to a Cursor Cloud Agent. Creates a remote agent that "
            "works on a GitHub repository. Never merge pull requests automatically — report "
            "back to the user for approval."
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
                    "description": "Detailed instructions for the Cursor agent.",
                },
                "repository": {
                    "type": "string",
                    "description": "GitHub repo URL or owner/repo slug.",
                },
                "base_ref": {
                    "type": "string",
                    "description": "Branch or ref to start from (default: main).",
                },
                "acceptance_criteria": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Checklist the Cursor agent must satisfy.",
                },
                "auto_create_pr": {
                    "type": "boolean",
                    "description": "Open a PR when done (default true). Do not merge it.",
                },
                "model_id": {
                    "type": "string",
                    "description": "Optional Cursor model id from cursor_list_models.",
                },
            },
            "required": ["objective", "prompt", "repository"],
        },
    },
    "cursor_get_agent": {
        "name": "cursor_get_agent",
        "description": "Get Cursor Cloud Agent metadata and refresh the linked local task status.",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Cursor agent id (bc-...)."},
                "task_id": {
                    "type": "string",
                    "description": "Optional local task id instead of agent_id.",
                },
            },
        },
    },
    "cursor_list_agents": {
        "name": "cursor_list_agents",
        "description": "List recent Cursor Cloud Agents.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max agents to return (default 20)."},
            },
        },
    },
    "cursor_create_run": {
        "name": "cursor_create_run",
        "description": "Send a follow-up instruction to an existing Cursor Cloud Agent.",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Cursor agent id."},
                "prompt": {"type": "string", "description": "Follow-up instruction text."},
                "task_id": {"type": "string", "description": "Optional local task id to update."},
            },
            "required": ["agent_id", "prompt"],
        },
    },
    "cursor_get_run": {
        "name": "cursor_get_run",
        "description": "Get status and result for a specific Cursor agent run.",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "run_id": {"type": "string"},
            },
            "required": ["agent_id", "run_id"],
        },
    },
    "cursor_cancel_agent": {
        "name": "cursor_cancel_agent",
        "description": "Cancel the active Cursor run and archive the agent.",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "run_id": {"type": "string", "description": "Optional run id to cancel first."},
                "task_id": {"type": "string", "description": "Optional local task id."},
            },
            "required": ["agent_id"],
        },
    },
    "cursor_list_tasks": {
        "name": "cursor_list_tasks",
        "description": "List locally tracked Hermes→Cursor delegations.",
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
    "cursor_list_models": {
        "name": "cursor_list_models",
        "description": (
            "List Cursor Cloud Agent models you can pass to cursor_create_agent as model_id, "
            "including supported parameters and variants."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    "cursor_get_account": {
        "name": "cursor_get_account",
        "description": "Get information about the authenticated Cursor API key (GET /v1/me).",
        "parameters": {"type": "object", "properties": {}},
    },
}
