"""Hermes plugin: delegate coding work to Cursor Cloud Agents."""

from __future__ import annotations

from . import schemas
from . import tools as tool_handlers


def register(ctx):
    handlers = {
        "cursor_list_repositories": tool_handlers.handle_list_repositories,
        "cursor_list_models": tool_handlers.handle_list_models,
        "cursor_get_account": tool_handlers.handle_get_account,
        "cursor_create_agent": tool_handlers.handle_create_agent,
        "cursor_get_agent": tool_handlers.handle_get_agent,
        "cursor_list_agents": tool_handlers.handle_list_agents,
        "cursor_create_run": tool_handlers.handle_create_run,
        "cursor_get_run": tool_handlers.handle_get_run,
        "cursor_cancel_agent": tool_handlers.handle_cancel_agent,
        "cursor_list_tasks": tool_handlers.handle_list_tasks,
    }

    for name, handler in handlers.items():
        schema = schemas.TOOL_SCHEMAS[name]
        ctx.register_tool(
            name=name,
            toolset="cursor_cloud",
            schema=schema,
            handler=handler,
            description=schema["description"],
        )

    def poll_pending(_params, **kwargs):
        del kwargs
        from .webhook import poll_pending_tasks

        return __import__("json").dumps(poll_pending_tasks())

    ctx.register_tool(
        name="cursor_poll_pending_tasks",
        toolset="cursor_cloud",
        schema={
            "name": "cursor_poll_pending_tasks",
            "description": "Refresh all pending/running Cursor delegations from the Cursor API.",
            "parameters": {"type": "object", "properties": {}},
        },
        handler=poll_pending,
        description="Poll pending Cursor delegations and update local task status.",
    )
