"""Cancelled / unresolved tool calls must never reach the LLM prompt.

Regression: a blocking ``delegate_task`` was cancelled while its child session
kept running.  The next turn serialised the cancelled tool call with
``get_result(timeout=0, recursive=True)`` and failed with
``TimeoutError: TaskRunResult not ready`` instead of dropping the pair.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest

from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
from server.models.enums.task_enums import (
    TaskCallStatus,
    TaskCallStatusDetail,
    TaskRunStatus,
    TaskType,
)

CORE_SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".agentone",
    "scripts",
    "core",
)

CALL_KWARGS = {
    "requires_approval": False,
    "max_subtask_errors": 0,
    "max_subtask_error_rate": 0,
    "limit_subtask_parallel_runs": 0,
    "limit_per_instance_parallel_runs": 0,
    "max_retries": 0,
    "retry_delay": 0,
    "retry_requires_approval": False,
}
RUN_KWARGS = {
    "requires_approval": False,
    "max_subtask_errors": 0,
    "max_subtask_error_rate": 0,
    "limit_subtask_parallel_runs": 0,
    "limit_per_instance_parallel_runs": 0,
}


def _session_and_version():
    from server.models.agents.agent import AgentModel
    from server.models.agents.agent_version import AgentVersionModel
    from server.models.sessions.session import SessionModel
    from server.models.sessions.session_version import SessionVersionModel

    agent = AgentModel.objects.create(name="cancel-context-agent")
    version = AgentVersionModel.objects.create(agent=agent, version_number=1)
    session = SessionModel.objects.create(name="cancel-context-session")
    sv = SessionVersionModel.objects.create(
        session=session, agent=agent, pinned_agent_version=version, version_number=1
    )
    SessionModel.objects.filter(pk=session.pk).update(latest_session_version=sv)
    session.refresh_from_db()
    return session, sv


def _task_call(session, sv, status_detail, result_json=None, result_run=True):
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.tasks.agent_task_run import AgentTaskRun
    from server.models.tasks.task_definition import TaskDefinition
    from server.models.tasks.task_definition_version import TaskDefinitionVersion
    from server.models.tasks.task_instance import TaskInstance

    td = TaskDefinition.objects.create(name=f"tool-{TaskDefinition.objects.count()}")
    tdv = TaskDefinitionVersion.objects.create(
        task_definition=td, description="t", function_schema={}, task_type=TaskType.TOOL
    )
    TaskDefinition.objects.filter(pk=td.pk).update(latest_task_version=tdv)
    ti = TaskInstance.objects.create(
        task_definition_version=tdv, session=session, session_version=sv, **CALL_KWARGS
    )
    call = AgentTaskCall.objects.create(
        task_instance=ti,
        task_definition=td,
        task_definition_version=tdv,
        session=session,
        session_version=sv,
        carguments_json={},
        status=TaskCallStatus.ENDED,
        status_detail=status_detail,
        **CALL_KWARGS,
    )
    if result_run:
        run = AgentTaskRun.objects.create(
            agent_task_call=call,
            task_instance=ti,
            task_definition_version=tdv,
            session=session,
            session_version=sv,
            status=TaskRunStatus.SUCCESS,
            result_json=result_json if result_json is not None else {"ok": True},
            **RUN_KWARGS,
        )
        AgentTaskCall.objects.filter(pk=call.pk).update(taskcall_result_run=run)
        call.refresh_from_db()
    return call


def _assistant_message(session, sv, call):
    from server.models.message import Message

    message = Message.objects.create(
        role=MessageRole.ASSISTANT, session=session, session_version=sv
    )
    message.add_part(
        type=MessagePartType.MESSAGE,
        content_type=MessageContentType.TEXT,
        content="checking",
    )
    message.add_part(
        type=MessagePartType.TOOLCALL,
        content_type=MessageContentType.JSON,
        content="tool call",
        tool_call=call,
    )
    return message


def _runtime(session, sv):
    runtime = MagicMock()
    runtime.model = session
    runtime.get_version_model.return_value = sv
    runtime.system_prompt_chain = []
    runtime.tool_call_syntax = "openai"
    runtime.max_history_messages = 5
    runtime.aimodel.requires_reasoning_echo = False
    return runtime


def _build_context(runtime, message, monkeypatch):
    monkeypatch.setattr("runtime.session_bootstrap.ensure_session_bootstrap", lambda *_a, **_k: None)
    monkeypatch.syspath_prepend(CORE_SCRIPTS)
    from build_llm_context import build_llm_context

    return build_llm_context(runtime, message)


@pytest.mark.django_db
def test_cancelled_tool_call_is_dropped_with_its_tool_response(monkeypatch):
    from server.models.debug_log_entry import DebugLogEntry

    session, sv = _session_and_version()
    call = _task_call(session, sv, TaskCallStatusDetail.ENDED_CANCELLED)
    message = _assistant_message(session, sv, call)

    query = _build_context(_runtime(session, sv), message, monkeypatch)

    payloads = [qm.to_openai_message() for qm in query.related_query_messages.order_by("pk")]
    assert all(p.get("role") != "tool" for p in payloads)
    assistant = next(p for p in payloads if p.get("role") == MessageRole.ASSISTANT)
    assert "tool_calls" not in assistant
    assert "checking" in str(assistant["content"])
    assert DebugLogEntry.objects.filter(
        session=session, event="tool_call_not_prompt_ready"
    ).exists()


@pytest.mark.django_db
def test_live_nested_result_is_dropped_without_partial_result(monkeypatch):
    """ENDED_SUCCESS parent whose nested child is still ACTIVE is not ready."""
    from server.models.tasks.agent_task_call import AgentTaskCall

    session, sv = _session_and_version()
    child = _task_call(session, sv, TaskCallStatusDetail.ACTIVE_RUNNING, result_run=False)
    AgentTaskCall.objects.filter(pk=child.pk).update(
        status=TaskCallStatus.ACTIVE, status_detail=TaskCallStatusDetail.ACTIVE_RUNNING
    )
    child.refresh_from_db()
    parent = _task_call(
        session,
        sv,
        TaskCallStatusDetail.ENDED_SUCCESS,
        result_json={"_type": "AgentTaskCall", "pk": child.pk},
    )
    message = _assistant_message(session, sv, parent)

    query = _build_context(_runtime(session, sv), message, monkeypatch)

    payloads = [qm.to_openai_message() for qm in query.related_query_messages.order_by("pk")]
    assert all(p.get("role") != "tool" for p in payloads)
    assistant = next(p for p in payloads if p.get("role") == MessageRole.ASSISTANT)
    assert "tool_calls" not in assistant


@pytest.mark.django_db
def test_query_message_returns_none_for_not_ready_tool_call():
    """Direct construction path must not raise or invent a partial result."""
    from server.models.queries.query import Query
    from server.models.queries.query_message import QueryMessage

    session, sv = _session_and_version()
    call = _task_call(session, sv, TaskCallStatusDetail.ENDED_STOPPED)
    message = _assistant_message(session, sv, call)

    query = Query.objects.create(session=session, session_version=sv)
    qmsg = QueryMessage.objects.create(role="tool", query=query)
    qmsg.add_part(source_message_part=message.parts.filter(type=MessagePartType.TOOLCALL).get())

    assert qmsg.to_openai_message() is None


@pytest.mark.django_db
def test_successful_tool_call_is_kept(monkeypatch):
    session, sv = _session_and_version()
    call = _task_call(
        session, sv, TaskCallStatusDetail.ENDED_SUCCESS, result_json={"ok": True}
    )
    message = _assistant_message(session, sv, call)

    query = _build_context(_runtime(session, sv), message, monkeypatch)

    payloads = [qm.to_openai_message() for qm in query.related_query_messages.order_by("pk")]
    tool = next(p for p in payloads if p.get("role") == "tool")
    assert tool["tool_call_id"] == f"tc-{call.pk}"
    assert "ok" in tool["content"]
    assistant = next(p for p in payloads if p.get("role") == MessageRole.ASSISTANT)
    assert [t["id"] for t in assistant["tool_calls"]] == [f"tc-{call.pk}"]
