"""
Dispatches tool calls via BoundTask and records the resulting AgentTaskCall objects.

Receives the dict from parse_llm_response and enriches it with task_calls
so that decide_next_step can link them to the assistant message.
"""

from __future__ import annotations

from typing import Any

from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
from server.models.message import Message
from server.models.queries.response import Response
from runtime.session.session import Session


#: Tools whose call alone ends the turn — the session needs no follow-up LLM
#: round trip to emit ``final_result``. ``approval_verdict`` is the
#: approval_decider's single decision tool: once it is dispatched the verdict
#: is applied to the parent call, so waiting for a second LLM response just to
#: produce ``final_result`` would waste an API round trip.
_SESSION_ENDING_TOOLS = frozenset({"approval_verdict"})

#: Framework-generated parts that are never an agent call attempt and must not
#: count as ``tool_call_allowlist`` violations.  ``catch_tool_argument_error``
#: is judged separately by its embedded original tool name (see below).
_FRAMEWORK_NON_ATTEMPT_TOOLS = frozenset({"catch_approval_denied"})


def _attempted_tool_name(part: dict[str, Any]) -> str | None:
    """Return the tool the agent actually tried to call for a TOOLCALL part.

    ``parse_llm_response`` reroutes invalid/disallowed calls to
    ``catch_tool_argument_error`` — the agent's *intent* is the embedded
    original name, so that is what the allowlist is judged against (a
    ``read`` with bad arguments is still an attempted ``read``).  Returns
    *None* for framework-generated parts that are not a call attempt at all.
    """
    content = part.get("content") or {}
    name = content.get("name", "")
    if name in _FRAMEWORK_NON_ATTEMPT_TOOLS:
        return None
    if name == "catch_tool_argument_error":
        args = content.get("arguments") or {}
        attempted = args.get("tool_name")
        return attempted if isinstance(attempted, str) and attempted else name
    return name


def _allowlist_violations(parts: list[dict[str, Any]], allowlist: list[str]) -> list[str]:
    """Return attempted tool names outside *allowlist*, preserving order.

    Pure helper (no side effects) so it stays unit-testable without a DB.
    """
    allowed = set(allowlist)
    violated: list[str] = []
    for part in parts:
        if part.get("type") != MessagePartType.TOOLCALL:
            continue
        attempted = _attempted_tool_name(part)
        if attempted is not None and attempted not in allowed and attempted not in violated:
            violated.append(attempted)
    return violated


def ingest_assistant_message(
    _session: Session, response: Response, parts: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    For each normalized tool call, create a BoundTask and dispatch it.

    Skips tools not in the session's allowedToolNames. Each dispatched
    call is appended to parsed["task_calls"] as an AgentTaskCall.

    Args:
        _session:  The active agent session.
        response: The Response model returned by call_llm.
        parts:    List from parse_llm_response of Parts.
                  Each Part is a dict with minimal keys:
                    type, content_type, content
                  If type is "toolcall", also contains a tool_call key.

    Returns:
        The same dict enriched with a "task_calls" key -- a list of
        AgentTaskCall objects that the framework will execute and resolve.
    """

    prev_message = _session.get_last_message()

    sv = _session.get_version_model()
    message = Message.objects.create(
        session=sv.session,
        session_version=sv,
        response=response,
        role=MessageRole.ASSISTANT,
        prev_message=prev_message,
    )

    has_final_result = False

    # Strict call-time allowlist (SettingsModel.tool_call_allowlist): the
    # advertised tool set is intentionally left untouched so the LLM request —
    # and with it the provider KV/prompt cache — stays identical.  Violating
    # calls are never dispatched; they are recorded as parts (audit trail)
    # and flagged so decide_next_step aborts the session instead of looping
    # on soft catch-tool retries.  None (default) = no restriction.
    allowlist = _session._get_session_setting("tool_call_allowlist")
    violated: list[str] = _allowlist_violations(parts, allowlist) if allowlist is not None else []

    for part in parts:
        if part["type"] == MessagePartType.TOOLCALL:
            if part["content"]["name"] == "final_result" and "final_result" not in violated:
                has_final_result = True
                part["type"] = MessagePartType.MESSAGE
                part["content_type"] = MessageContentType.TEXT
                part["content"] = part["content"]["arguments"].get("content", "")
            elif _attempted_tool_name(part) in violated:
                # Off-allowlist attempt: record the part, never execute it.
                pass
            else:
                # Framework recovery tools (e.g. ``catch_tool_argument_error``,
                # ``catch_approval_denied``) are registered as TASK-type so the
                # LLM never sees them as callable; resolve via get_task too.
                bound_task = _session.get_tool(part["content"]["name"]) or _session.get_task(part["content"]["name"])
                if bound_task:
                    part["tool_call"] = bound_task.delay(**part["content"]["arguments"])
                    if part["content"]["name"] in _SESSION_ENDING_TOOLS:
                        has_final_result = True

        message.add_part(
            type=part["type"],
            content_type=part["content_type"],
            content=part["content"],
            template_data=part.get("template_data", None),
            tool_call=part.get("tool_call", None),
        )

    from runtime.events import publish_model_event
    publish_model_event(message, "create")

    result = dict(
        response=response,
        parts=parts,
        message=message,
        # Turn-shape flags, computed on the final mutated list (after the
        # final_result rewrite and tool_call attachment above) so downstream
        # steps need not read parts themselves.  Unconditional (unlike
        # has_final_result) so decide can distinguish "no tools" from
        # "flag lost in transit".
        has_tool_calls=any("tool_call" in part for part in parts),
        has_message=any(part["type"] == MessagePartType.MESSAGE for part in parts),
    )
    if has_final_result:
        result["has_final_result"] = True
    if violated:
        result["tool_allowlist_violated"] = violated
    return result
