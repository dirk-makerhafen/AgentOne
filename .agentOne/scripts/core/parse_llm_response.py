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
                toolcalls.append(
                    {
                        "id": f"custom_{func_name}",
                        "function": {"name": func_name, "arguments": kwargs},
                    }
                )
        if content:
            result_parts.append(Part(type=MessagePartType.MESSAGE, content_type=MessageContentType.TEXT, content=content))

        for toolcall in toolcalls:
            if isinstance(toolcall["arguments"], str):
                try:
                    toolcall["arguments"] = json.loads(toolcall["arguments"])
                except json.JSONDecodeError:
                    pass
            result_parts.append(
                Part(type=MessagePartType.TOOLCALL, content_type=MessageContentType.JSON, content=toolcall)
            )

        return dict(
            response=response,
            parts=result_parts,
        )

    except Exception:
        from server.models.debug_log_entry import DebugLogEntry

        DebugLogEntry.objects.create(
            session=_session.model,
            event="exception",
            data={"exception": traceback.format_exc()},
        )
        raise
