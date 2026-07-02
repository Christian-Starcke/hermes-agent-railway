"""Hermes plugin: delegate and track work via Paperclip."""

from __future__ import annotations

from . import schemas
from . import tools as tool_handlers


def register(ctx):
    handlers = {
        "paperclip_health": tool_handlers.handle_health,
        "paperclip_list_agents": tool_handlers.handle_list_agents,
        "paperclip_create_issue": tool_handlers.handle_create_issue,
        "paperclip_assign_issue": tool_handlers.handle_assign_issue,
        "paperclip_get_issue": tool_handlers.handle_get_issue,
        "paperclip_list_issues": tool_handlers.handle_list_issues,
        "paperclip_add_comment": tool_handlers.handle_add_comment,
        "paperclip_cancel_issue": tool_handlers.handle_cancel_issue,
        "paperclip_delegate_coding_task": tool_handlers.handle_delegate_coding_task,
    }

    for name, handler in handlers.items():
        schema = schemas.TOOL_SCHEMAS[name]
        ctx.register_tool(
            name=name,
            toolset="paperclip",
            schema=schema,
            handler=handler,
            description=schema["description"],
        )
