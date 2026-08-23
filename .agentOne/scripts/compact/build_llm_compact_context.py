from __future__ import annotations
from typing import List

from runtime.session.session import Session
from server.models.enums.message_enums import MessageContentType, MessageRole, MessagePartType
from server.models.message import Message
from server.models.queries.query import Query
from server.models.queries.query_message import QueryMessage
import time
from server.models.enums.session_enums import SessionType

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

    from server.history_limiter import find_compaction_boundary

    # Query-free: compute the newest message to compact from the message
    # chain, so the compaction fork only summarizes the old (compacted) range.
    boundary = find_compaction_boundary(_session, _session.get_last_message())
    if not boundary:
        return dict(response=response, parts=parts, message=message, **kwargs)

    agent_version = _session.agent.get_version_model()
    if not agent_version:
        return {"error": "Current agent version not found"}

    session_name = f"p{_session.model.pk}:compaction:{int(time.time())}"
    child_sv = agent_version.get_or_create_session(
        name=session_name,
        description=f"Session compaction for {_session.name} at {int(time.time())}",
        workspace=_session.workspace,
        parent_session_version=_session.get_version_model(),
        session_type=SessionType.SUBTASK_FORK,
    )

    # The compaction fork carries the same (oversized) context that triggered
    # *this* compaction — so it would immediately exceed the auto-compact
    # limit itself and spawn yet another compaction fork (infinite chain).
    # Fork off the inherited session settings but pin auto_compact_limit to 0.
    from server.models.settings import SettingsModel
    from server.models.sessions.session_version import SessionVersionModel

    if child_sv.session_settings:
        fork_settings = agent_version.clone_settings(child_sv.session_settings, auto_compact_limit=0)
    else:
        fork_settings = SettingsModel(auto_compact_limit=0)
        fork_settings.save()
    SessionVersionModel.objects.filter(pk=child_sv.pk).update(session_settings=fork_settings)
    child_sv.session_settings = fork_settings
    child_session = Session(session_model=child_sv.session, pinned_session_version=child_sv)
    child_version = child_session.get_version_model()
    fork_msg = Message.objects.create(role=MessageRole.USER, session=child_version.session, session_version=child_version, prev_message=boundary)
    fork_msg.add_part(
        type=MessagePartType.MESSAGE,
        content_type=MessageContentType.TEXT,
        content="IMPORTANT: Context is running low, you have been switched to a session compaction agent.",
    )
    prompt_parts = [
        {
            "type": MessagePartType.MESSAGE,
            "content_type": MessageContentType.TEXT,
            "content": f"""Your job is to produce a concise, information-dense summary that preserves key context from the existing summary and incorporates relevant new information from the conversation above so the AI agent can continue working without losing important context.

Focus on:
- Key decisions made and their rationale
- Current constraints and requirements
- What has been accomplished so far
- What remains to be done
- Important context the model must remember
- File paths, function names, and specific technical details

Format as a clear, structured summary. Be specific — avoid generic statements.

When you are done, call the final_result tool with the summary as its content argument."""
        },
    ]

    compact_result = child_session.add_user_message(parts=prompt_parts)
    return dict(
        child_session_pk=child_sv.session.pk,
        boundary_pk=boundary.pk,
        result=compact_result
    )
     
