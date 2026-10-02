"""
Parses an LLM Response to extract content, reasoning, and tool call definitions.

Supports both DEFAULT (OpenAI function-calling) and CUSTOM ([call:...] syntax)
tool call formats. Pure parse -- no side effects, no tool execution.
"""

from __future__ import annotations

import codecs
import json
import re
import traceback
from typing import Any, NotRequired, TypedDict

from runtime.session.session import Session
from runtime.tool_argument_utils import normalize_tool_arguments
from server.models.enums.message_enums import MessageContentType, MessagePartType
from server.models.queries.response import Response
from server.models.settings import AgentToolCallSyntax


class Part(TypedDict):
    """A single parsed element from the LLM response."""

    type: str
    content_type: str
    content: str | dict[str, Any]
    template_data: NotRequired[dict[str, Any]]


def _deduplicate(data: Any) -> Any:
    """Recursively convert long strings to GenericContent wrappers."""
    if isinstance(data, dict):
        return {k: _deduplicate(data=v) for k, v in data.items()}
    elif isinstance(data, (list, set)):
        return [_deduplicate(data=item) for item in data]
    elif isinstance(data, str):
        if len(data) < 128:
            return data
        from server.models.content import GenericContent

        return GenericContent.from_text(data)
    return data


CATCH_TOOL_NAME = "catch_tool_argument_error"

#: Tool names handled by the framework itself and never routed to the catch tool.
_SKIP_VALIDATION_NAMES = frozenset({"final_result", CATCH_TOOL_NAME, "catch_approval_denied"})

#: JSON-schema property types we can safely coerce from the strings LLMs emit.
_COERCION_TYPES = frozenset({"integer", "number", "boolean"})


class _ToolArgumentError(Exception):
    """Raised when a tool call fails schema validation."""


def _validate_tool_call(_session: Session, name: str, arguments: Any) -> tuple[str, Any, str | None]:
    """Validate and coerce a single tool call against the tool's JSON schema.

    LLMs frequently emit JSON strings for scalar parameters (``"depth": "2"``
    or ``"blocking": "true"``).  When the schema declares ``integer``,
    ``number`` or ``boolean`` we coerce those strings so the downstream tool
    receives the declared Python type.  Missing required arguments (without a
    schema default) and arguments that cannot be coerced are treated as errors.

    When the tool does not exist / is not allowed, or validation fails, the
    call is routed to the ``catch_tool_argument_error`` task instead: *name*
    is replaced with that tool name and the original name and arguments are
    passed along so the agent can see exactly what went wrong.

    Returns:
        A ``(name, arguments, error)`` triple.  On success ``name`` is
        unchanged and ``arguments`` may have been type-coerced.  On failure
        ``name`` is ``catch_tool_argument_error`` and ``arguments`` contains
        ``{"tool_name", "arguments"}`` (plus ``"error"``) describing the
        original call.
    """
    if name in _SKIP_VALIDATION_NAMES:
        return name, arguments, None

    def _route(error: str) -> tuple[str, dict[str, Any], str]:
        return CATCH_TOOL_NAME, {"tool_name": name, "arguments": arguments, "error": error}, error

    if not isinstance(arguments, dict):
        return _route(
            f"arguments must be a JSON object, got {type(arguments).__name__}"
        )

    bound_task = _session.get_tool(name)
    if bound_task is None:
        return _route(f"tool '{name}' does not exist or is not allowed for this agent")

    schema = bound_task.task_definition_version.function_schema or {}
    properties = schema.get("properties") or {}
    coerced: dict[str, Any] = dict(arguments)

    try:
        for key, value in list(coerced.items()):
            expected = (properties.get(key) or {}).get("type")
            if expected not in _COERCION_TYPES or not isinstance(value, str):
                continue
            stripped = value.strip()
            try:
                if expected == "integer":
                    coerced[key] = int(stripped)
                elif expected == "number":
                    coerced[key] = float(stripped)
                else:
                    coerced[key] = stripped.lower() in ["true", "yes"]
            except ValueError:
                raise _ToolArgumentError(
                    f"argument '{key}' must be a {expected}, got '{value}'"
                )

        for required in schema.get("required") or []:
            if "default" in (properties.get(required) or {}):
                continue
            if required not in coerced or coerced[required] in (None, ""):
                raise _ToolArgumentError(f"missing required argument '{required}'")
    except _ToolArgumentError as e:
        return _route(f"tool '{name}': {e}")

    return name, coerced, None


def parse_llm_response(_session: Session, response: Response) -> dict[str, Any]:
    """
    Extract content, reasoning, and normalized tool call definitions.

    For CUSTOM syntax, parses [call:tool_name(key=val, ...)] tags from
    the response content and appends them to any existing tool_calls.

    Args:
        _session:  The active agent session (used to check tool_call_syntax).
        response: The Response model returned by call_llm.

    Returns:
        A dict with keys:
            response  (Response) -- The original response model.
            parts     (list)    -- List of Part TypedDicts, each with:
                                  type, content_type, content, and optionally
                                  template_data / tool_call.
    """

    result_parts: list[Part] = []

    toolcalls: list[dict[str, Any]] = list(getattr(response, "tool_calls", []) or [])
    content: str = getattr(response, "content", "") or ""
    reasoning: str = (getattr(response, "reasoning", "") or "").strip()

    if reasoning:
        result_parts.append(Part(type=MessagePartType.REASONING, content_type=MessageContentType.TEXT, content=reasoning))

    try:
        if _session.tool_call_syntax == AgentToolCallSyntax.CUSTOM and content:
            pattern = r"\[call:(\w+)\((.*?)\)\]"
            matches = re.finditer(pattern, content)
            for match in matches:
                func_name = match.group(1)
                raw_args = match.group(2)
                kwargs: dict[str, str] = {}
                if raw_args:
                    parts_list = re.split(r",(?=(?:[^']*'[^']*')*[^']*$)", raw_args)
                    for p in parts_list:
                        if "=" in p:
                            k, v = p.split("=", 1)
                            kwargs[k.strip()] = normalize_tool_arguments(v.strip().strip("'").strip('"'))
                toolcalls.append({
                    "id": f"custom_{func_name}",
                    "function": {"name": func_name, "arguments": kwargs},
                })
        if content:
            result_parts.append(Part(type=MessagePartType.MESSAGE, content_type=MessageContentType.TEXT, content=content))

        for toolcall in toolcalls:
            function = toolcall.get("function") or {}
            name:str = function.get("name","") or toolcall.get("name","")
            arguments = function.get("arguments", toolcall.get("arguments"))
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    pass
            name, arguments, _error = _validate_tool_call(_session, name, arguments)
            toolcall["name"] = name
            toolcall["arguments"] = arguments
            result_parts.append(Part(type=MessagePartType.TOOLCALL, content_type=MessageContentType.JSON, content=toolcall))

        return dict(response=response, parts=result_parts)

    except Exception:
        from server.models.debug_log_entry import DebugLogEntry

        DebugLogEntry.objects.create(
            session=_session.model,
            event="exception",
            data={"exception": traceback.format_exc()},
        )
        raise
