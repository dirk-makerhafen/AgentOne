"""Context compaction utilities — shared by compact_turn chain steps."""

from __future__ import annotations

from server.models.enums.message_enums import MessagePartType
from server.models.message import Message


_COMPACTION_SYSTEM_PROMPT = """You are a session compaction agent. Your job is to produce a concise, information-dense summary of a conversation so the AI agent can continue working without losing important context.

Focus on:
- Key decisions made and their rationale
- Current constraints and requirements
- What has been accomplished so far
- What remains to be done
- Important context the model must remember
- File paths, function names, and specific technical details

Format as a clear, structured summary. Be specific — avoid generic statements.
Target around 500-1000 tokens."""


def _format_messages_for_compaction(messages: list[Message]) -> str:
    lines = []
    for msg in reversed(messages):
        role = msg.role or "unknown"
        text_parts = []
        for part in msg.parts.all():
            if part.type == MessagePartType.COMPACTION:
                continue
            text = part.to_string() or ""
            if text:
                text_parts.append(text)
        content = "\n".join(text_parts) if text_parts else "(no content)"
        lines.append(f"[{role.upper()}]\n{content}\n")
    return "\n".join(lines)
