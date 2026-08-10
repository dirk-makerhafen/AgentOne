"""Tests for the automated approval review of python/shell calls.

- ``approval_verdict`` (approval_decider tool): allow → auto-approve,
  deny → auto-deny + feedback, ask_human → leave halted, and fail-safe
  escalation on invalid input or a mismatched ``task_call_id``.
- ``CallScheduler._dispatch_auto_review``: only fires for python/shell,
  once per call, and honors ``extra_settings.auto_review_approvals``.
- ``CallScheduler.auto_review_approval``: spawns a decider session carrying
  the review context; escalates to a human when the decider agent is missing.
"""
import importlib.util
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from runtime.session.session import Session
from runtime.tasks.call_scheduler import CallScheduler
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.enums.task_enums import (
    TaskCallStatus, TaskCallStatusDetail, TaskType,
)
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_run import AgentTaskRun
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion
from server.models.tasks.task_instance import TaskInstance

_ROOT = Path(__file__).resolve().parents[2]


def _load_script(relpath: str):
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


def _make_agent(name: str, extra: dict | None = None) -> AgentVersionModel:
    agent = AgentModel.objects.create(name=name)
    settings = SettingsModel.objects.create(extra_settings=extra)
    av = AgentVersionModel.objects.create(agent=agent, agent_settings=settings)
    AgentModel.objects.filter(pk=agent.pk).update(latest_agent_version=av)
    agent.refresh_from_db()
    return av


@pytest.fixture
def make_python_call():
    created: list[AgentTaskCall] = []

    def _make(
        tool_name: str = "python",
        *,
        requires_approval: bool = True,
        halted: bool = True,
        source: str = "print('hello')",
        agent_extra: dict | None = None,
    ) -> AgentTaskCall:
        td, tdv = _make_tool(tool_name)
        agent_av = _make_agent(name=f"{tool_name}-agent", extra=agent_extra)
        agent_av.task_versions.add(tdv)
        agent = agent_av.agent
        session = SessionModel.objects.create(name=f"{tool_name}-session")
        sv = SessionVersionModel.objects.create(session=session, agent=agent)
        session.latest_session_version = sv
        session.save()
        td, tdv = _make_tool(tool_name)
        ti = TaskInstance.objects.create(
            task_definition_version=tdv, session=session, session_version=sv,
            requires_approval=requires_approval, priority=0, max_retries=0,
            retry_delay=0, retry_requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, time_limit=None,
        )
        call = AgentTaskCall.objects.create(
            task_definition=td, task_definition_version=tdv,
            task_instance=ti, session=session, session_version=sv,
            carguments_json={"source": source}, requires_approval=requires_approval,
            guardrail_reason="guardrail flagged this",
            max_subtask_errors=0, max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=1,
            max_retries=0, retry_delay=0, retry_requires_approval=False,
            status=TaskCallStatus.HALTED if halted else TaskCallStatus.NEW,
            status_detail=(
                TaskCallStatusDetail.HALTED_APPROVAL if halted
                else TaskCallStatusDetail.NEW
            ),
        )
        created.append(call)
        return call

    yield _make
    AgentTaskCall.objects.filter(pk__in=[c.pk for c in created]).delete()


def _decider_env(review_task_call_id: int) -> Session:
    """A runtime Session whose settings declare the review target."""
    agent = AgentModel.objects.create(name="approval_decider")
    settings = SettingsModel.objects.create()
    av = AgentVersionModel.objects.create(agent=agent, agent_settings=settings)
    AgentModel.objects.filter(pk=agent.pk).update(latest_agent_version=av)
    agent.refresh_from_db()
    session = SessionModel.objects.create(name="decider-session")
    sv = SessionVersionModel.objects.create(session=session, agent=agent)
    session.latest_session_version = sv
    session.save()
    s = SettingsModel(extra_settings={"review_task_call_id": review_task_call_id})
    s.save()
    SessionVersionModel.objects.filter(pk=sv.pk).update(session_settings=s)
    return Session(session_model=session, pinned_session_version=sv)


def _verdict_module():
    return _load_script(".agentone/scripts/decider/approval_verdict.py")


@pytest.mark.django_db
class TestApprovalVerdictTool:
    def test_allow_auto_approves(self, make_python_call, monkeypatch: MonkeyPatch):
        call = make_python_call()
        env = _decider_env(call.pk)
        monkeypatch.setattr(AgentTaskRun, "apply_async", lambda self: None)
        result = _verdict_module().approval_verdict(
            env, decision="allow", reason="reads a file", task_call_id=call.pk
        )
        assert result[0] is True
        assert result[1]["applied"] is True
        call.refresh_from_db()
        assert call.auto_review_status == "approved"
        assert call.status_detail != TaskCallStatusDetail.HALTED_APPROVAL

    def test_deny_auto_denies(self, make_python_call, monkeypatch: MonkeyPatch):
        call = make_python_call(source="rm -rf /")
        env = _decider_env(call.pk)
        monkeypatch.setattr(AgentTaskRun, "apply_async", lambda self: None)
        result = _verdict_module().approval_verdict(
            env, decision="deny", reason="destructive", task_call_id=call.pk
        )
        assert result[0] is True
        assert result[1]["applied"] is True
        call.refresh_from_db()
        assert call.auto_review_status == "denied"
        assert call.status_detail == TaskCallStatusDetail.ENDED_CANCELLED

    def test_ask_human_leaves_halted(self, make_python_call):
        call = make_python_call()
        env = _decider_env(call.pk)
        result = _verdict_module().approval_verdict(
            env, decision="ask_human", reason="ambiguous", task_call_id=call.pk
        )
        assert result[0] is True
        assert result[1]["applied"] is True
        call.refresh_from_db()
        assert call.auto_review_status == "escalated"
        assert call.status_detail == TaskCallStatusDetail.HALTED_APPROVAL

    def test_unknown_decision_escalates(self, make_python_call):
        call = make_python_call()
        env = _decider_env(call.pk)
        result = _verdict_module().approval_verdict(
            env, decision="maybe", reason="?", task_call_id=call.pk
        )
        assert result[0] is True
        assert result[1]["applied"] is False
        call.refresh_from_db()
        assert call.auto_review_status is None
        assert call.status_detail == TaskCallStatusDetail.HALTED_APPROVAL

    def test_id_mismatch_never_approves(self, make_python_call):
        call = make_python_call()
        other_call = make_python_call(tool_name="shell")
        env = _decider_env(call.pk)
        result = _verdict_module().approval_verdict(
            env, decision="allow", reason="wrong target", task_call_id=other_call.pk
        )
        assert result[0] is True
        assert result[1]["applied"] is False
        other_call.refresh_from_db()
        assert other_call.auto_review_status is None
        assert other_call.status_detail == TaskCallStatusDetail.HALTED_APPROVAL

    def test_non_python_shell_tool_escalates(self, make_python_call):
        call = make_python_call(tool_name="read")
        env = _decider_env(call.pk)
        result = _verdict_module().approval_verdict(
            env, decision="allow", reason="na", task_call_id=call.pk
        )
        assert result[0] is True
        assert result[1]["applied"] is False
        call.refresh_from_db()
        assert call.status_detail == TaskCallStatusDetail.HALTED_APPROVAL

    def test_already_decided_call_escalates(self, make_python_call):
        call = make_python_call()
        env = _decider_env(call.pk)
        AgentTaskCall.objects.filter(pk=call.pk).update(auto_review_status="denied")
        result = _verdict_module().approval_verdict(
            env, decision="allow", reason="na", task_call_id=call.pk
        )
        assert result[0] is True
        assert result[1]["applied"] is False


@pytest.mark.django_db
class TestDispatchAutoReview:
    @pytest.fixture(autouse=True)
    def _capture_celery(self, monkeypatch: MonkeyPatch):
        calls: list[tuple] = []
        monkeypatch.setattr(
            "server.tasks.task_dispatcher.celery_delay",
            lambda func, *a, **k: calls.append((func, a)),
        )
        self.captured = calls  # type: ignore[attr-defined]
        yield

    def test_python_halted_dispatches(self, make_python_call):
        call = make_python_call()
        CallScheduler._dispatch_auto_review(call.pk)
        call.refresh_from_db()
        assert call.auto_review_status == "pending"
        assert len(self.captured) == 1  # type: ignore[attr-defined]

    def test_dispatched_once(self, make_python_call):
        call = make_python_call()
        AgentTaskCall.objects.filter(pk=call.pk).update(auto_review_status="pending")
        CallScheduler._dispatch_auto_review(call.pk)
        assert len(self.captured) == 0  # type: ignore[attr-defined]

    def test_non_script_tool_not_dispatched(self, make_python_call):
        call = make_python_call(tool_name="write")
        CallScheduler._dispatch_auto_review(call.pk)
        call.refresh_from_db()
        assert call.auto_review_status is None
        assert len(self.captured) == 0  # type: ignore[attr-defined]

    def test_disabled_via_extra_settings(self, make_python_call):
        call = make_python_call(agent_extra={"auto_review_approvals": False})
        CallScheduler._dispatch_auto_review(call.pk)
        call.refresh_from_db()
        assert call.auto_review_status is None
        assert len(self.captured) == 0  # type: ignore[attr-defined]


@pytest.mark.django_db
class TestAutoReviewApproval:
    @pytest.fixture(autouse=True)
    def _capture_user_message(self, monkeypatch: MonkeyPatch):
        captured: list[dict] = []

        def _fake_add_user_message(self, parts):
            captured.append({"parts": parts, "session_pk": self.model.pk})
            from server.models.enums.message_enums import (
                MessageContentType, MessagePartType, MessageRole,
            )
            from server.models.message import Message
            msg = Message.objects.create(
                session=self.model, session_version=self.get_version_model(),
                role=MessageRole.USER,
            )
            msg.add_part(type=MessagePartType.MESSAGE, content_type=MessageContentType.TEXT, content="")
            return msg

        monkeypatch.setattr(
            "runtime.session.session.Session.add_user_message", _fake_add_user_message
        )
        self.captured = captured  # type: ignore[attr-defined]
        yield

    def test_launches_decider_session_with_context(self, make_python_call):
        _make_agent("approval_decider")
        call = make_python_call(source="import os; print(os.getcwd())")
        AgentTaskCall.objects.filter(pk=call.pk).update(auto_review_status="pending")
        CallScheduler.auto_review_approval(call.pk)
        call.refresh_from_db()
        assert call.auto_review_status == "pending"  # not escalated
        from server.models.sessions.session import SessionModel as SM
        child = SM.objects.filter(name__startswith="approval-review:").first()
        assert child is not None
        extra = child.latest_session_version.session_settings.extra_settings
        assert extra["review_task_call_id"] == call.pk
        combined = " ".join(
            p["content"] for p in self.captured[0]["parts"]  # type: ignore[index]
        )
        assert "task_call_id" in combined and str(call.pk) in combined
        assert "Allowed tools" in combined
        assert "Filesystem permissions" in combined

    def test_escalates_when_decider_missing(self, make_python_call):
        AgentModel.objects.filter(name="approval_decider").delete()
        call = make_python_call()
        CallScheduler.auto_review_approval(call.pk)
        call.refresh_from_db()
        assert call.auto_review_status == "escalated"
        assert call.status_detail == TaskCallStatusDetail.HALTED_APPROVAL
