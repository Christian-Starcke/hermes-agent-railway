"""Hermes plugin: delegate coding work to OpenCode on Railway."""

from __future__ import annotations

from . import schemas
from . import tools as tool_handlers


def register(ctx):
    handlers = {
        "opencode_health": tool_handlers.handle_health,
        "opencode_list_agents": tool_handlers.handle_list_agents,
        "opencode_list_providers": tool_handlers.handle_list_providers,
        "opencode_create_task": tool_handlers.handle_create_task,
        "opencode_send_message": tool_handlers.handle_send_message,
        "opencode_get_task": tool_handlers.handle_get_task,
        "opencode_list_tasks": tool_handlers.handle_list_tasks,
        "opencode_abort_task": tool_handlers.handle_abort_task,
    }

    for name, handler in handlers.items():
        schema = schemas.TOOL_SCHEMAS[name]
        ctx.register_tool(
            name=name,
            toolset="opencode_delegate",
            schema=schema,
            handler=handler,
            description=schema["description"],
        )

    def poll_pending(_params, **kwargs):
        del kwargs
        from .sync import poll_pending_tasks

        return __import__("json").dumps(poll_pending_tasks())

    ctx.register_tool(
        name="opencode_poll_pending_tasks",
        toolset="opencode_delegate",
        schema={
            "name": "opencode_poll_pending_tasks",
            "description": "Refresh all pending/running OpenCode delegations from the OpenCode API.",
            "parameters": {"type": "object", "properties": {}},
        },
        handler=poll_pending,
        description="Poll pending OpenCode delegations and update local task status.",
    )
