"""Tests for approval-denial feedback back to the LLM.

- ``catch_approval_denied`` core tool returns the denial message.
- ``CallScheduler.deny_taskcall`` cancels a halted call and, when the call is
  wired into a conversation, dispatches a ``catch_approval_denied`` report call
  and re-points the message part + waiting result references to it.
- The API ``deny`` action accepts an optional ``feedback`` body field.
"""
import importlib.util
from pathlib import Path

import pytest

from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.enums.message_enums import MessageRole
from server.models.enums.session_enums import SessionType
from server.models.enums.task_enums import (
    TaskCallStatus, TaskCallStatusDetail, TaskRunStatus, TaskType,
)
from server.models.message import Message
from server.models.queries.response import Response
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_run import AgentTaskRun
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion
from server.models.tasks.task_instance import TaskInstance
from runtime.tasks.call_scheduler import CallScheduler

_ROOT = Path(__file__).resolve().parents[2]


def _load_script(relpath: str):
    """Load a manifest script module the same way registry/loader does."""
    spec = importlib.util.spec_from_file_location(
        relpath.replace("/", "_").replace(".", "_"),
        _ROOT / relpath,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _make_tool(name: str, task_type: TaskType = TaskType.TOOL):
    td = TaskDefinition.objects.create(name=name)
    tdv = TaskDefinitionVersion.objects.create(
        task_definition=td, task_type=task_type,
        description=name, function_schema={},
    )
    return td, tdv


def _make_setup(*, report_tool: bool = True):
    """Agent + session + a ``dangerous_tool`` definition.

    When ``report_tool`` is True the agent also has the
    ``catch_approval_denied`` tool registered. It is registered as a
    TASK (like in production) so ``get_tool`` does not resolve it and the
    dispatch must fall back to ``get_task``.
    """
    agent = AgentModel.objects.create(name="deny-agent")
    settings = SettingsModel.objects.create()
    av = AgentVersionModel.objects.create(agent=agent, agent_settings=settings)
    if report_tool:
        _, report_tdv = _make_tool("catch_approval_denied", TaskType.TASK)
        av.task_versions.add(report_tdv)
    AgentModel.objects.filter(pk=agent.pk).update(latest_agent_version=av)
    agent.refresh_from_db()

    session = SessionModel.objects.create(name="deny-session")
    sv = SessionVersionModel.objects.create(session=session, agent=agent)
    session.latest_session_version = sv
    session.save()

    td, tdv = _make_tool("dangerous_tool")
    ti = TaskInstance.objects.create(
        task_definition_version=tdv, session=session, session_version=sv,
        requires_approval=True, priority=0, max_retries=0, retry_delay=0,
        retry_requires_approval=False, max_subtask_errors=0,
        max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
        limit_per_instance_parallel_runs=1, time_limit=None,
    )
    return session, sv, td, tdv, ti


def _make_halted_call(session, sv, tdv, ti, *, reason="risky command"):
    return AgentTaskCall.objects.create(
        task_definition=tdv.task_definition, task_definition_version=tdv,
        task_instance=ti, session=session, session_version=sv,
        carguments_json={"source": "rm -rf /"}, requires_approval=True,
        guardrail_reason=reason,
        max_subtask_errors=0, max_subtask_error_rate=0,
        limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=1,
        max_retries=0, retry_delay=0, retry_requires_approval=False,
        status=TaskCallStatus.HALTED,
        status_detail=TaskCallStatusDetail.HALTED_APPROVAL,
    )


def _link_to_message(session, sv, call):
    msg = Message.objects.create(
        session=session, session_version=sv, role=MessageRole.ASSISTANT,
    )
    return msg.add_part(
        type="toolcall", content_type="TEXT", content="", tool_call=call,
    )


def _make_waiting_run(session, sv, tdv, call):
    run = AgentTaskRun.objects.create(
        agent_task_call=call, task_definition_version=tdv,
        session=session, session_version=sv, arguments_json={},
        requires_approval=False, max_subtask_errors=0,
        max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
        limit_per_instance_parallel_runs=1, priority=0,
        status=TaskRunStatus.WAITING_RESULTTASKS,
    )
    run.taskrun_result_references.add(call)
    return run


@pytest.mark.django_db
class TestCatchApprovalDeniedScript:
    def test_returns_error_with_reason_and_feedback(self):
        module = _load_script(".agentone/scripts/core/catch_approval_denied.py")
        ok, result = module.catch_approval_denied(
            None, "shell", reason="risky command", feedback="use read-only"
        )
        assert ok is False
        assert result["status"] == "error"
        assert "shell" in result["message"]
        assert "NOT executed" in result["message"]
        assert "risky command" in result["message"]
        assert "use read-only" in result["message"]

    def test_omits_empty_reason_and_feedback(self):
        module = _load_script(".agentone/scripts/core/catch_approval_denied.py")
        ok, result = module.catch_approval_denied(None, "shell")
        assert ok is False
        assert "Reason:" not in result["message"]
        assert "feedback:" not in result["message"].lower()


@pytest.mark.django_db
class TestDenyTaskcall:
    def test_deny_cancels_and_repoints(self):
        session, sv, td, tdv, ti = _make_setup()
        call = _make_halted_call(session, sv, tdv, ti)
        part = _link_to_message(session, sv, call)
        run = _make_waiting_run(session, sv, tdv, call)

        assert CallScheduler.deny_taskcall(call.pk, feedback="use a safer command") is True

        call.refresh_from_db()
        assert call.status == TaskCallStatus.ENDED
        assert call.status_detail == TaskCallStatusDetail.ENDED_CANCELLED

        report = AgentTaskCall.objects.filter(
            task_definition__name="catch_approval_denied"
        ).first()
        assert report is not None
        assert report.carguments_json == {
            "tool_name": "dangerous_tool",
            "reason": "risky command",
            "feedback": "use a safer command",
        }

        part.refresh_from_db()
        assert part.tool_call_id == report.pk

        refs = [c.pk for c in run.taskrun_result_references.all()]
        assert refs == [report.pk]

    def test_deny_without_feedback(self):
        session, sv, td, tdv, ti = _make_setup()
        call = _make_halted_call(session, sv, tdv, ti)
        _link_to_message(session, sv, call)

        assert CallScheduler.deny_taskcall(call.pk) is True

        report = AgentTaskCall.objects.filter(
            task_definition__name="catch_approval_denied"
        ).first()
        assert report is not None
        assert report.carguments_json["feedback"] == ""

    def test_deny_without_message_part_cancels_only(self):
        session, sv, td, tdv, ti = _make_setup()
        call = _make_halted_call(session, sv, tdv, ti)

        assert CallScheduler.deny_taskcall(call.pk) is True
        call.refresh_from_db()
        assert call.status_detail == TaskCallStatusDetail.ENDED_CANCELLED
        assert not AgentTaskCall.objects.filter(
            task_definition__name="catch_approval_denied"
        ).exists()

    def test_deny_without_report_tool_cancels_only(self):
        session, sv, td, tdv, ti = _make_setup(report_tool=False)
        call = _make_halted_call(session, sv, tdv, ti)
        _link_to_message(session, sv, call)

        assert CallScheduler.deny_taskcall(call.pk) is True
        call.refresh_from_db()
        assert call.status_detail == TaskCallStatusDetail.ENDED_CANCELLED
        assert not AgentTaskCall.objects.filter(
            task_definition__name="catch_approval_denied"
        ).exists()

    def test_deny_unknown_call(self):
        assert CallScheduler.deny_taskcall(999999) is False


@pytest.mark.django_db
class TestIngestDispatchesTaskTypeCatchTool:
    """Recovery tools registered as TASK-type (hidden from the LLM tool list)
    must still dispatch through ``ingest_assistant_message`` via the
    ``get_task`` fallback (``get_tool`` alone returns None for them)."""

    def test_dispatches_catch_tool_argument_error(self):
        agent = AgentModel.objects.create(name="ingest-agent")
        settings = SettingsModel.objects.create()
        av = AgentVersionModel.objects.create(agent=agent, agent_settings=settings)
        _, catch_tdv = _make_tool("catch_tool_argument_error", TaskType.TASK)
        av.task_versions.add(catch_tdv)
        AgentModel.objects.filter(pk=agent.pk).update(latest_agent_version=av)
        agent.refresh_from_db()

        session = SessionModel.objects.create(name="ingest-session")
        sv = SessionVersionModel.objects.create(session=session, agent=agent)
        session.latest_session_version = sv
        session.save()

        response = Response.objects.create(session=session, session_version=sv)
        module = _load_script(".agentone/scripts/core/ingest_assistant_message.py")
        parts = [{
            "type": "TOOLCALL",
            "content_type": "JSON",
            "content": {
                "name": "catch_tool_argument_error",
                "arguments": {"tool_name": "shell", "error": "bad argument"},
            },
        }]
        result = module.ingest_assistant_message(
            session.get_runtime(), response, parts
        )
        part = result["message"].parts.first()
        assert part is not None
        assert part.tool_call is not None
        assert part.tool_call.task_definition.name == "catch_tool_argument_error"
        assert part.tool_call.carguments_json == {
            "tool_name": "shell",
            "error": "bad argument",
        }


@pytest.mark.django_db
class TestIngestSetsTurnShapeFlags:
    """``ingest_assistant_message`` reports the turn shape (computed on the
    final mutated parts, after the ``final_result`` rewrite) so downstream
    steps need not read ``parts`` themselves."""

    def _make_session(self):
        agent = AgentModel.objects.create(name="flags-agent")
        settings = SettingsModel.objects.create()
        av = AgentVersionModel.objects.create(agent=agent, agent_settings=settings)
        _, catch_tdv = _make_tool("catch_tool_argument_error", TaskType.TASK)
        av.task_versions.add(catch_tdv)
        AgentModel.objects.filter(pk=agent.pk).update(latest_agent_version=av)
        agent.refresh_from_db()

        session = SessionModel.objects.create(name="flags-session")
        sv = SessionVersionModel.objects.create(session=session, agent=agent)
        session.latest_session_version = sv
        session.save()
        response = Response.objects.create(session=session, session_version=sv)
        return session, sv, response

    def test_text_only_turn(self):
        session, sv, response = self._make_session()
        module = _load_script(".agentone/scripts/core/ingest_assistant_message.py")
        result = module.ingest_assistant_message(
            session.get_runtime(), response,
            [{"type": "MESSAGE", "content_type": "TEXT", "content": "hello"}],
        )
        assert result["has_tool_calls"] is False
        assert result["has_message"] is True

    def test_toolcall_turn(self):
        session, sv, response = self._make_session()
        module = _load_script(".agentone/scripts/core/ingest_assistant_message.py")
        parts = [{
            "type": "TOOLCALL",
            "content_type": "JSON",
            "content": {
                "name": "catch_tool_argument_error",
                "arguments": {"tool_name": "shell", "error": "bad argument"},
            },
        }]
        result = module.ingest_assistant_message(
            session.get_runtime(), response, parts
        )
        assert result["has_tool_calls"] is True
        assert result["has_message"] is False


@pytest.mark.django_db
class TestApprovalVerdictEndsSession:
    """``approval_verdict`` is a session-ending tool: once dispatched, the
    review session is marked complete without a follow-up LLM round trip to
    emit ``final_result``."""

    def _make_verdict_session(self):
        agent = AgentModel.objects.create(name="verdict-agent")
        settings = SettingsModel.objects.create()
        av = AgentVersionModel.objects.create(agent=agent, agent_settings=settings)
        _, verdict_tdv = _make_tool("approval_verdict", TaskType.TOOL)
        av.task_versions.add(verdict_tdv)
        AgentModel.objects.filter(pk=agent.pk).update(latest_agent_version=av)
        agent.refresh_from_db()

        parent = SessionModel.objects.create(name="verdict-parent")
        session = SessionModel.objects.create(
            name="verdict-review",
            parent_session=parent,
            session_type=SessionType.SUBTASK_FORK,
        )
        sv = SessionVersionModel.objects.create(session=session, agent=agent)
        session.latest_session_version = sv
        session.save()
        return session, sv

    def test_ingest_sets_has_final_result(self):
        session, sv = self._make_verdict_session()
        response = Response.objects.create(session=session, session_version=sv)
        module = _load_script(".agentone/scripts/core/ingest_assistant_message.py")
        parts = [{
            "type": "TOOLCALL",
            "content_type": "JSON",
            "content": {
                "name": "approval_verdict",
                "arguments": {"approved": True, "reason": "looks safe"},
            },
        }]
        result = module.ingest_assistant_message(
            session.get_runtime(), response, parts
        )
        assert result["has_final_result"] is True
        assert result["message"].parts.first().tool_call is not None
        assert (
            result["message"].parts.first().tool_call.task_definition.name
            == "approval_verdict"
        )

    def test_ingest_does_not_set_has_final_result_for_other_tools(self):
        session, sv = self._make_verdict_session()
        response = Response.objects.create(session=session, session_version=sv)
        module = _load_script(".agentone/scripts/core/ingest_assistant_message.py")
        parts = [{
            "type": "TOOLCALL",
            "content_type": "JSON",
            "content": {
                "name": "approval_verdict",
                "arguments": {"approved": True, "reason": "ok"},
            },
        }]
        parts[0]["content"]["name"] = "some_other_tool"
        result = module.ingest_assistant_message(
            session.get_runtime(), response, parts
        )
        assert "has_final_result" not in result

    def test_decide_next_step_deactivates_after_verdict(self):
        decide_next_step = _load_script(".agentone/scripts/core/decide_next_step.py").decide_next_step
        session, sv = self._make_verdict_session()
        rt = session.get_runtime()
        msg = Message.objects.create(
            session=session, session_version=sv, role=MessageRole.ASSISTANT
        )
        result = decide_next_step(rt, response=None, parts=[], message=msg, has_final_result=True)
        assert result == msg
        session.refresh_from_db()
        assert session.is_active is False


@pytest.mark.django_db
class TestDenyApiFeedback:
    def _make_halted_call(self, auth_client) -> AgentTaskCall:
        agent = AgentModel.objects.create(name="deny-api-agent")
        session = SessionModel.objects.create(name="deny-api-session")
        sv = SessionVersionModel.objects.create(session=session, agent=agent)
        session.latest_session_version = sv
        session.save()
        td = TaskDefinition.objects.create(name="deny-api-task")
        tdv = TaskDefinitionVersion.objects.create(
            task_definition=td, task_type=TaskType.TOOL,
            description="test", function_schema={},
        )
        ti = TaskInstance.objects.create(
            task_definition_version=tdv, session=session, session_version=sv,
            requires_approval=True, priority=0, max_retries=0, retry_delay=0,
            retry_requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, time_limit=None,
        )
        return AgentTaskCall.objects.create(
            task_definition=td, task_definition_version=tdv,
            task_instance=ti, session=session, session_version=sv,
            carguments_json={}, requires_approval=True,
            max_subtask_errors=0, max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=1,
            max_retries=0, retry_delay=0, retry_requires_approval=False,
            status=TaskCallStatus.HALTED,
            status_detail=TaskCallStatusDetail.HALTED_APPROVAL,
        )

    def test_deny_with_feedback_body(self, auth_client):
        call = self._make_halted_call(auth_client)
        resp = auth_client.post(
            f'/api/v1/task-calls/{call.id}/deny/',
            {'feedback': 'please use a read-only command'},
            format='json',
        )
        assert resp.status_code == 200
        assert resp.data['status'] == 'denied'
        call.refresh_from_db()
        assert call.status_detail == TaskCallStatusDetail.ENDED_CANCELLED

    def test_deny_without_feedback(self, auth_client):
        call = self._make_halted_call(auth_client)
        resp = auth_client.post(f'/api/v1/task-calls/{call.id}/deny/')
        assert resp.status_code == 200
        assert resp.data['status'] == 'denied'
        call.refresh_from_db()
        assert call.status_detail == TaskCallStatusDetail.ENDED_CANCELLED
