"""
Parses an LLM Response to extract content, reasoning, and tool call definitions.

Supports both DEFAULT (OpenAI function-calling) and CUSTOM ([call:...] syntax)
tool call formats. Pure parse — no side effects, no tool execution.
"""

import json
import re
import traceback
from runtime.agents.session import Session
from server.models.queries.response import Response
from server.models.settings import AgentToolCallSyntax


def extract_tool_calls(session: Session, response: Response) -> dict:
    """
    Extract content, reasoning, and normalized tool call definitions.

    For CUSTOM syntax, parses [call:tool_name(key=val, ...)] tags from
    the response content and appends them to any existing tool_calls.

    Args:
        session:  The active agent session (used to check tool_call_syntax).
        response: The Response model returned by call_llm.

    Returns:
        A dict with keys:
            content    (str)  — The text output from the LLM.
            reasoning  (str)  — Reasoning/thinking tokens, if any.
            tool_calls (list) — Normalized list of {id, name, arguments} dicts,
                                where arguments is already parsed from JSON.
    """
    toolcalls = list(getattr(response, "tool_calls", []) or [])
    content = getattr(response, "content", "") or ""
    reasoning = getattr(response, "reasoning", "") or ""

    try:
        if session.tool_call_syntax == AgentToolCallSyntax.CUSTOM and content:
            pattern = r"\[call:(\w+)\((.*?)\)\]"
            matches = re.finditer(pattern, content)
            for match in matches:
                func_name = match.group(1)
                raw_args = match.group(2)
                kwargs = {}
                if raw_args:
                    parts = re.split(
                        r",(?=(?:[^']*'[^']*')*[^']*$)", raw_args
                    )
                    for p in parts:
                        if "=" in p:
                            k, v = p.split("=", 1)
                            kwargs[k.strip()] = v.strip().strip("'").strip('"')
                toolcalls.append({
                    "id": f"custom_{func_name}",
                    "function": {"name": func_name, "arguments": kwargs},
                })

        normalized = []
        for tc in toolcalls:
            func_name = tc["function"]["name"]
            args = tc["function"]["arguments"]
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            normalized.append({
                "id": tc.get("id", ""),
                "name": func_name,
                "arguments": args,
            })

        return {"content": content, "reasoning": reasoning, "tool_calls": normalized}

    except Exception:
        from server.models.debug_log_entry import DebugLogEntry
        DebugLogEntry.objects.create(
            session=session.model,
            event="exception",
            data={"exception": traceback.format_exc()},
        )
        raise
