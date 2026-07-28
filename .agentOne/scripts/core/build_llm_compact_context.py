from __future__ import annotations

from runtime.session.session import Session
from server.models.enums.message_enums import MessageContentType
from server.models.message import Message
from server.models.queries.query import Query

_COMPACTION_SYSTEM_PROMPT = """
Context is running low, you have been switched to a session compaction agent. 
Your job is to produce a concise, information-dense summary that preserves key context from the existing summary and incorporates relevant new information from the conversation above so the AI agent can continue working without losing important context.

Focus on:
- Key decisions made and their rationale
- Current constraints and requirements
- What has been accomplished so far
- What remains to be done
- Important context the model must remember
- File paths, function names, and specific technical details

Format as a clear, structured summary. Be specific — avoid generic statements.
"""


def build_llm_compact_context(_session: Session, message: Message) -> Query:
    query = _session.get_task("build_llm_context").call(message=message)

    # compactSizeLimit is a percentage (0–100) of messages to KEEP in full.
    pct = _session.compact_size_limit
    if pct <= 0:
        pct = 15

    # Count conversation QueryMessages (system/tool defs have source_message=None).
    conv = [qm for qm in query.related_query_messages.all() if qm.source_message_id]
    keep_count = max(1, int(len(conv) * pct / 100))

    # Remove the kept messages from the compaction query so the LLM only
    # sees the messages that need to be summarized.
    if keep_count < len(conv):
        for qm in conv[-keep_count:]:
            qm.delete()

    query.add_message(
        role="user",
        content_type=MessageContentType.TEXT,
        content=_COMPACTION_SYSTEM_PROMPT,
    )

    return query
