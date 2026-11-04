"""Helpers for the ``final_result`` tool call.

Shared between the reflection fork pipeline and the provider/model smoke-test
runs so the tool-call argument extraction (including content-addressed large
bodies) lives in exactly one place.
"""
from __future__ import annotations

from typing import Any

from server.models.content import GenericContent
from server.models.enums.message_enums import MessagePartType
from server.models.message import Message


def extract_final_result_text(result: Any) -> str:
    """Extract the ``final_result`` content from a turn result.

    ``result`` may be a :class:`Message`, a string, an ``AgentTaskCall``-style
    dict, or ``None``.  Content-addressed bodies (``{"_type": "GenericContent",
    "pk": N}``) are resolved transparently so callers get the plain text.
    """
    if isinstance(result, Message):
        text = ""
        for part in result.parts.order_by("pk"):
            if getattr(part, "type", None) == MessagePartType.MESSAGE:
                content = part.content.get() if getattr(part, "content", None) else None
                text += str(content) if content else ""
            elif (
                getattr(part, "type", None) == MessagePartType.TOOLCALL
                and getattr(part, "tool_call", None)
                and getattr(part.tool_call, "task_definition", None) is not None
                and part.tool_call.task_definition.name == "final_result"
            ):
                args = part.tool_call.carguments_json or {}
                content_arg = args.get("content", "")
                if (
                    isinstance(content_arg, dict)
                    and content_arg.get("_type") == "GenericContent"
                    and "pk" in content_arg
                ):
                    try:
                        content_arg = GenericContent.objects.get(pk=content_arg["pk"]).get()
                    except Exception:  # pylint: disable=broad-exception-caught
                        pass
                text += str(content_arg)
        return text
    if isinstance(result, str):
        return result
    if isinstance(result, dict) and result.get("content") is not None:
        return str(result["content"])
    return ""
