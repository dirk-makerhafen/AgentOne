"""Slash-command tool calls back chat cards without changing the LLM prompt."""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest

from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
from server.models.enums.task_enums import TaskCallStatus

CORE_SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".agentone",
    "scripts",
    "core",
)


def _session_and_version():
    from server.models.agents.agent import AgentModel
    from server.models.agents.agent_version import AgentVersionModel
    from server.models.sessions.session import SessionModel
    from server.models.sessions.session_version import SessionVersionModel

    agent = AgentModel.objects.create(name="slash-context-agent")
    version = AgentVersionModel.objects.create(agent=agent, version_number=1)
    session = SessionModel.objects.create(name="slash-context-session")
    sv = SessionVersionModel.objects.create(
        session=session, agent=agent, pinned_agent_version=version, version_number=1
    )
    SessionModel.objects.filter(pk=session.pk).update(latest_session_version=sv)
    session.refresh_from_db()
    return session, sv


def _ended_call(session, sv):
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.tasks.task_definition import TaskDefinition

    return AgentTaskCall.objects.create(
        session=session,
        session_version=sv,
        task_definition=TaskDefinition.objects.create(name="ping"),
        status=TaskCallStatus.ENDED,
        status_detail="ENDED_SUCCESS",
        carguments_json={},
        requires_approval=False,
        max_subtask_errors=0,
        max_subtask_error_rate=0,
        limit_subtask_parallel_runs=0,
        limit_per_instance_parallel_runs=0,
        max_retries=0,
        retry_delay=0,
        retry_requires_approval=False,
    )


def _slash_message(session, sv, call):
    from server.models.message import Message

    message = Message.objects.create(
        role=MessageRole.USER, session=session, session_version=sv
    )
    message.add_part(
        type=MessagePartType.TOOLCALL,
        content_type=MessageContentType.JSON,
        content="/ping {}",
        tool_call=call,
    )
    return message


@pytest.mark.django_db
def test_linked_user_toolcall_is_serialised_as_text():
    """The UI link must not turn a user slash command into assistant tool_calls."""
    from server.models.queries.query import Query
    from server.models.queries.query_message import QueryMessage

    session, sv = _session_and_version()
    message = _slash_message(session, sv, _ended_call(session, sv))

    query = Query.objects.create(session=session, session_version=sv)
    qmessage = QueryMessage.objects.create(role=MessageRole.USER, query=query)
    qmessage.add_part(source_message_part=message.parts.get())

    payload = qmessage.to_openai_message()
    assert payload["role"] == "user"
    assert "tool_calls" not in payload
    assert "USER TOOLCALL" in str(payload["content"])


@pytest.mark.django_db
def test_build_llm_context_does_not_add_a_tool_response_for_user_commands(monkeypatch):
    monkeypatch.setattr("runtime.session_bootstrap.ensure_session_bootstrap", lambda *_a, **_k: None)
    sys.path.insert(0, CORE_SCRIPTS)
    try:
        from build_llm_context import build_llm_context
    finally:
        sys.path.remove(CORE_SCRIPTS)

    session, sv = _session_and_version()
    message = _slash_message(session, sv, _ended_call(session, sv))
    runtime = MagicMock()
    runtime.get_version_model.return_value = sv
    runtime.system_prompt_chain = []
    runtime.tool_call_syntax = "openai"
    runtime.max_history_messages = 5
    runtime.aimodel.requires_reasoning_echo = False

    query = build_llm_context(runtime, message)

    roles = list(query.related_query_messages.values_list("role", flat=True))
    assert "tool" not in roles
    user_payload = next(
        qm.to_openai_message()
        for qm in query.related_query_messages.all()
        if qm.role == MessageRole.USER
    )
    assert "tool_calls" not in user_payload
