"""Tool handlers for the paperclip Hermes plugin."""

from __future__ import annotations

import json
import os
from typing import Any

try:
    from .paperclip_client import PaperclipAPIError, PaperclipClient
except ImportError:
    from paperclip_client import PaperclipAPIError, PaperclipClient


def _delegation_mode() -> str:
    return (os.environ.get("PAPERCLIP_DELEGATION_MODE") or "direct").strip().lower()


def _default_agent_id() -> str | None:
    value = (os.environ.get("PAPERCLIP_DEFAULT_AGENT_ID") or "").strip()
    return value or None


def _agent_map() -> dict[str, str]:
    raw = (os.environ.get("PAPERCLIP_AGENT_MAP") or "").strip()
    mapping: dict[str, str] = {}
    if not raw:
        return mapping
    for part in raw.split(","):
        piece = part.strip()
        if not piece or ":" not in piece:
            continue
        repo, agent_id = piece.split(":", 1)
        mapping[repo.strip().lower()] = agent_id.strip()
    return mapping


def _resolve_agent_id(repository: str | None, explicit: str | None = None) -> str | None:
    if explicit:
        return explicit.strip()
    if repository:
        slug = PaperclipClient.repository_slug(repository).lower()
        mapped = _agent_map().get(slug)
        if mapped:
            return mapped
    return _default_agent_id()


def _allowed_repo(repository: str) -> bool:
    allowlist = os.environ.get("PAPERCLIP_ALLOWED_REPOS", "").strip()
    if not allowlist:
        return True
    slug = PaperclipClient.repository_slug(repository).lower()
    allowed = {item.strip().lower() for item in allowlist.split(",") if item.strip()}
    return slug in allowed or repository.strip().lower() in allowed


def _build_description(prompt: str, repository: str, acceptance_criteria: list[str] | None) -> str:
    repo_url = PaperclipClient.normalize_repository(repository)
    lines = [
        prompt.strip(),
        "",
        f"Repository: {repo_url}",
        "",
        "Constraints:",
        "- Do not merge any pull request unless explicitly instructed.",
        "- Report what you changed and how to verify it.",
    ]
    if acceptance_criteria:
        lines.append("")
        lines.append("Acceptance criteria:")
        lines.extend(f"- {item}" for item in acceptance_criteria)
    return "\n".join(lines)


def _issue_summary(issue_payload: Any) -> dict[str, Any]:
    if not isinstance(issue_payload, dict):
        return {"raw": issue_payload}
    issue = issue_payload.get("issue") if "issue" in issue_payload else issue_payload
    if not isinstance(issue, dict):
        return {"raw": issue_payload}
    return {
        "id": issue.get("id"),
        "identifier": issue.get("identifier"),
        "title": issue.get("title"),
        "status": issue.get("status"),
        "priority": issue.get("priority"),
        "assigneeAgentId": issue.get("assigneeAgentId"),
        "description": issue.get("description"),
    }


def handle_health(params: dict[str, Any], **kwargs: Any) -> str:
    del params, kwargs
    try:
        client = PaperclipClient()
        data = client.health()
        return json.dumps({"success": True, "health": data, "delegation_mode": _delegation_mode()})
    except PaperclipAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_list_agents(params: dict[str, Any], **kwargs: Any) -> str:
    del params, kwargs
    try:
        client = PaperclipClient()
        data = client.list_agents()
        return json.dumps({"success": True, "agents": data})
    except PaperclipAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_create_issue(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        title = str(params.get("title") or "").strip()
        if not title:
            return json.dumps({"success": False, "error": "title is required"})

        payload: dict[str, Any] = {
            "title": title,
            "status": params.get("status") or "todo",
            "priority": params.get("priority") or "medium",
        }
        if params.get("description"):
            payload["description"] = str(params["description"])
        for key, field in (
            ("parent_id", "parentId"),
            ("project_id", "projectId"),
            ("goal_id", "goalId"),
        ):
            if params.get(key):
                payload[field] = params[key]

        assignee = _resolve_agent_id(None, params.get("assignee_agent_id"))
        if assignee:
            payload["assigneeAgentId"] = assignee

        client = PaperclipClient()
        created = client.create_issue(payload)
        return json.dumps({"success": True, "issue": _issue_summary(created), "raw": created})
    except PaperclipAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_assign_issue(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        issue_id = str(params.get("issue_id") or "").strip()
        if not issue_id:
            return json.dumps({"success": False, "error": "issue_id is required"})
        assignee = _resolve_agent_id(None, params.get("assignee_agent_id"))
        if not assignee:
            return json.dumps({"success": False, "error": "assignee_agent_id or PAPERCLIP_DEFAULT_AGENT_ID required"})

        client = PaperclipClient()
        updated = client.update_issue(
            issue_id,
            {"assigneeAgentId": assignee, "status": "todo"},
        )
        return json.dumps({"success": True, "issue": _issue_summary(updated), "raw": updated})
    except PaperclipAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_get_issue(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        issue_id = str(params.get("issue_id") or "").strip()
        if not issue_id:
            return json.dumps({"success": False, "error": "issue_id is required"})
        client = PaperclipClient()
        data = client.get_issue(issue_id)
        return json.dumps({"success": True, "issue": _issue_summary(data), "raw": data})
    except PaperclipAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_list_issues(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        client = PaperclipClient()
        data = client.list_issues(
            status=str(params["status"]) if params.get("status") else None,
            assignee_agent_id=str(params["assignee_agent_id"]) if params.get("assignee_agent_id") else None,
            limit=int(params.get("limit") or 25),
            query=str(params["query"]) if params.get("query") else None,
        )
        issues = data if isinstance(data, list) else data.get("issues", data)
        return json.dumps({"success": True, "issues": issues})
    except PaperclipAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_add_comment(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        issue_id = str(params.get("issue_id") or "").strip()
        comment = str(params.get("comment") or "").strip()
        if not issue_id or not comment:
            return json.dumps({"success": False, "error": "issue_id and comment are required"})
        client = PaperclipClient()
        updated = client.update_issue(issue_id, {"comment": comment})
        return json.dumps({"success": True, "issue": _issue_summary(updated), "raw": updated})
    except PaperclipAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_cancel_issue(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        issue_id = str(params.get("issue_id") or "").strip()
        if not issue_id:
            return json.dumps({"success": False, "error": "issue_id is required"})
        reason = str(params.get("reason") or "Cancelled by Hermes operator.").strip()
        client = PaperclipClient()
        updated = client.update_issue(
            issue_id,
            {
                "status": "cancelled",
                "comment": reason,
                "interrupt": True,
            },
        )
        return json.dumps({"success": True, "issue": _issue_summary(updated), "raw": updated})
    except PaperclipAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})


def handle_delegate_coding_task(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    if _delegation_mode() not in ("paperclip", "paperclip_only"):
        return json.dumps(
            {
                "success": False,
                "error": (
                    "PAPERCLIP_DELEGATION_MODE is not set to 'paperclip'. "
                    "Use cursor_create_agent for direct delegation or set PAPERCLIP_DELEGATION_MODE=paperclip."
                ),
            }
        )

    try:
        repository = str(params.get("repository") or os.environ.get("PAPERCLIP_DEFAULT_REPOSITORY", "")).strip()
        if not repository:
            return json.dumps({"success": False, "error": "repository is required"})
        if not _allowed_repo(repository):
            return json.dumps({"success": False, "error": f"repository not allowed: {repository}"})

        objective = str(params.get("objective") or "").strip()
        prompt = str(params.get("prompt") or "").strip()
        if not objective or not prompt:
            return json.dumps({"success": False, "error": "objective and prompt are required"})

        criteria = params.get("acceptance_criteria") or []
        if not isinstance(criteria, list):
            criteria = [str(criteria)]
        criteria = [str(item) for item in criteria]

        assignee = _resolve_agent_id(repository, params.get("assignee_agent_id"))
        if not assignee:
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        "No worker agent configured. Set PAPERCLIP_DEFAULT_AGENT_ID or "
                        "PAPERCLIP_AGENT_MAP for this repository."
                    ),
                }
            )

        description = _build_description(prompt, repository, criteria)
        payload: dict[str, Any] = {
            "title": objective[:200],
            "description": description,
            "status": "todo",
            "priority": params.get("priority") or "high",
            "assigneeAgentId": assignee,
        }

        client = PaperclipClient()
        created = client.create_issue(payload)
        summary = _issue_summary(created)
        return json.dumps(
            {
                "success": True,
                "issue": summary,
                "message": (
                    f"Delegated to Paperclip issue {summary.get('identifier') or summary.get('id')}. "
                    "Paperclip will wake the assigned worker on the next heartbeat."
                ),
                "raw": created,
            }
        )
    except PaperclipAPIError as exc:
        return json.dumps({"success": False, "error": str(exc), "details": exc.body})
