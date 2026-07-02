"""JSON schemas for paperclip plugin tools."""

TOOL_SCHEMAS = {
    "paperclip_health": {
        "name": "paperclip_health",
        "description": "Check Paperclip API connectivity and database health.",
        "parameters": {"type": "object", "properties": {}},
    },
    "paperclip_list_agents": {
        "name": "paperclip_list_agents",
        "description": "List agents in the configured Paperclip company (workers like Cursor Cloud).",
        "parameters": {"type": "object", "properties": {}},
    },
    "paperclip_create_issue": {
        "name": "paperclip_create_issue",
        "description": "Create a new issue/task in Paperclip.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Issue title (required)."},
                "description": {"type": "string", "description": "Detailed task description / prompt."},
                "status": {
                    "type": "string",
                    "description": "Initial status (default: todo).",
                },
                "priority": {
                    "type": "string",
                    "description": "low, medium, high, or critical (default: medium).",
                },
                "assignee_agent_id": {
                    "type": "string",
                    "description": "Agent UUID to assign. Defaults to PAPERCLIP_DEFAULT_AGENT_ID.",
                },
                "parent_id": {"type": "string", "description": "Optional parent issue UUID."},
                "project_id": {"type": "string", "description": "Optional project UUID."},
                "goal_id": {"type": "string", "description": "Optional goal UUID."},
            },
            "required": ["title"],
        },
    },
    "paperclip_assign_issue": {
        "name": "paperclip_assign_issue",
        "description": "Assign an issue to an agent and set status to todo.",
        "parameters": {
            "type": "object",
            "properties": {
                "issue_id": {"type": "string", "description": "Issue UUID or identifier (e.g. PAP-42)."},
                "assignee_agent_id": {
                    "type": "string",
                    "description": "Agent UUID. Defaults to PAPERCLIP_DEFAULT_AGENT_ID.",
                },
            },
            "required": ["issue_id"],
        },
    },
    "paperclip_get_issue": {
        "name": "paperclip_get_issue",
        "description": "Get full issue details including status, comments, and work products.",
        "parameters": {
            "type": "object",
            "properties": {
                "issue_id": {"type": "string", "description": "Issue UUID or identifier (e.g. PAP-42)."},
            },
            "required": ["issue_id"],
        },
    },
    "paperclip_list_issues": {
        "name": "paperclip_list_issues",
        "description": "List issues in the Paperclip company with optional filters.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by status or comma-separated list (e.g. todo,in_progress).",
                },
                "assignee_agent_id": {"type": "string", "description": "Filter by assigned agent."},
                "query": {"type": "string", "description": "Full-text search."},
                "limit": {"type": "integer", "description": "Max results (default 25)."},
            },
        },
    },
    "paperclip_add_comment": {
        "name": "paperclip_add_comment",
        "description": "Add a comment to a Paperclip issue.",
        "parameters": {
            "type": "object",
            "properties": {
                "issue_id": {"type": "string"},
                "comment": {"type": "string", "description": "Comment body."},
            },
            "required": ["issue_id", "comment"],
        },
    },
    "paperclip_cancel_issue": {
        "name": "paperclip_cancel_issue",
        "description": "Cancel/interrupt work on an in-progress Paperclip issue.",
        "parameters": {
            "type": "object",
            "properties": {
                "issue_id": {"type": "string"},
                "reason": {"type": "string", "description": "Optional cancellation reason."},
            },
            "required": ["issue_id"],
        },
    },
    "paperclip_delegate_coding_task": {
        "name": "paperclip_delegate_coding_task",
        "description": (
            "Delegate repository coding work via Paperclip: creates an issue with a detailed prompt, "
            "assigns it to the Cursor worker agent, and returns the issue id (e.g. PAP-42). "
            "Paperclip heartbeats invoke Cursor — do not call cursor_create_agent when Paperclip mode is on."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "objective": {"type": "string", "description": "Short title for the task."},
                "prompt": {"type": "string", "description": "Detailed instructions for the coding agent."},
                "repository": {
                    "type": "string",
                    "description": "GitHub repo URL or owner/repo slug (for agent routing and context).",
                },
                "acceptance_criteria": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Checklist the agent must satisfy.",
                },
                "assignee_agent_id": {
                    "type": "string",
                    "description": "Override worker agent UUID. Otherwise uses repo map or default.",
                },
                "priority": {"type": "string", "description": "low, medium, high, critical."},
            },
            "required": ["objective", "prompt", "repository"],
        },
    },
}
