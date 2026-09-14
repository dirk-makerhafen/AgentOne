"""Tests for the ``ask_user`` question tool loop.

- Question gate: a valid ``ask_user`` call is parked for approval;
  malformed questions and other tools pass through untouched.
- ``answer_question_call``: partial answers are recorded (still halted),
  complete answers approve the call so the tool result feeds back to the LLM.
- Denying a question reuses the approval-denial feedback path.
- The API ``answer`` action accepts answers and approves on completion.
"""
import importlib.util
from pathlib import Path

import pytest

from runtime.tasks.call_fsm import TaskCallStateMachine
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

QUESTIONS = [
    {
        "question": "How should I format the output?",
        "header": "Format",
        "options": [
            {"label": "Summary", "description": "Brief overview of key points"},
            {"label": "Detailed", "description": "Full explanation with examples"},
        ],
        "multiSelect": False,
    },
    {
        "question": "Which sections should I include?",
        "header": "Sections",
        "options": [
            {"label": "Introduction", "description": "Opening context"},
            {"label": "Conclusion", "description": "Final summary"},
        ],
        "multiSelect": True,
    },
]


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


def _make_setup(*, questions=None):
    agent = AgentModel.objects.create(name="ask-agent")
    settings = SettingsModel.objects.create()
    av = AgentVersionModel.objects.create(agent=agent, agent_settings=settings)
    AgentModel.objects.filter(pk=agent.pk).update(latest_agent_version=av)

    session = SessionModel.objects.create(name="ask-session")
    sv = SessionVersionModel.objects.create(session=session, agent=agent)
    session.latest_session_version = sv
    session.save()

    td, tdv = _make_tool("ask_user")
    ti = TaskInstance.objects.create(
        task_definition_version=tdv, session=session, session_version=sv,
        requires_approval=False, priority=0, max_retries=0, retry_delay=0,
        retry_requires_approval=False, max_subtask_errors=0,
        max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
        limit_per_instance_parallel_runs=1, time_limit=None,
    )
    call = AgentTaskCall.objects.create(
        task_definition=tdv.task_definition, task_definition_version=tdv,
        task_instance=ti, session=session, session_version=sv,
        carguments_json={"questions": questions if questions is not None else QUESTIONS},
        requires_approval=False,
        max_subtask_errors=0, max_subtask_error_rate=0,
        limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=1,
        max_retries=0, retry_delay=0, retry_requires_approval=False,
        status=TaskCallStatus.WAITING,
        status_detail=TaskCallStatusDetail.WAITING_DEPENDENCY,
    )
    return session, sv, td, tdv, ti, call


def _halt(call):
    CallScheduler._question_gate_check(call.pk)
    call.refresh_from_db()
    assert TaskCallStateMachine.request_approval(call.pk) is True
    call.refresh_from_db()
    assert call.status_detail == TaskCallStatusDetail.HALTED_APPROVAL
    return call


@pytest.mark.django_db
class TestAskUserScript:
    def test_success(self):
        module = _load_script(".agentone/scripts/core/ask_user.py")
        ok, result = module.ask_user(None, QUESTIONS, answers={
            "How should I format the output?": "Detailed",
            "Which sections should I include?": ["Introduction"],
        })
        assert ok is True
        assert result["status"] == "success"
        assert result["answers"]["How should I format the output?"] == "Detailed"
        assert "Detailed" in result["summary"]

    def test_no_answers_errors(self):
        module = _load_script(".agentone/scripts/core/ask_user.py")
        ok, result = module.ask_user(None, QUESTIONS)
        assert ok is False
        assert result["status"] == "error"
        assert "No user answers" in result["message"]

    def test_invalid_questions_error(self):
        module = _load_script(".agentone/scripts/core/ask_user.py")
        ok, result = module.ask_user(
            None, [{"question": "X?"}], answers={"X?": "y"})
        assert ok is False
        assert "options" in result["message"]


@pytest.mark.django_db
class TestQuestionGate:
    def test_valid_questions_park_for_approval(self):
        _, _, _, _, _, call = _make_setup()
        CallScheduler._question_gate_check(call.pk)
        call.refresh_from_db()
        assert call.requires_approval is True
        assert "question" in (call.guardrail_reason or "").lower()

    def test_gate_strips_llm_supplied_answers(self):
        _, _, _, _, _, call = _make_setup()
        AgentTaskCall.objects.filter(pk=call.pk).update(
            carguments_json={
                "questions": QUESTIONS,
                "answers": {"How should I format the output?": "Sneaky"},
            }
        )
        CallScheduler._question_gate_check(call.pk)
        call.refresh_from_db()
        assert call.requires_approval is True
        assert "answers" not in call.carguments_json

    def test_gate_then_request_approval_halts(self):
        _, _, _, _, _, call = _make_setup()
        _halt(call)

    def test_invalid_questions_pass_through(self):
        _, _, _, _, _, call = _make_setup(
            questions=[{"question": "Which?", "header": "Q", "options": []}]
        )
        CallScheduler._question_gate_check(call.pk)
        call.refresh_from_db()
        assert call.requires_approval is False

    def test_other_tools_untouched(self):
        session, sv, _, _, _, _ = _make_setup()
        td, tdv = _make_tool("shell")
        ti = TaskInstance.objects.create(
            task_definition_version=tdv, session=session, session_version=sv,
            requires_approval=False, priority=0, max_retries=0, retry_delay=0,
            retry_requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, time_limit=None,
        )
        other = AgentTaskCall.objects.create(
            task_definition=td, task_definition_version=tdv,
            task_instance=ti, session=session, session_version=sv,
            carguments_json={"source": "ls"}, requires_approval=False,
            max_subtask_errors=0, max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=1,
            max_retries=0, retry_delay=0, retry_requires_approval=False,
            status=TaskCallStatus.WAITING,
            status_detail=TaskCallStatusDetail.WAITING_DEPENDENCY,
        )
        CallScheduler._question_gate_check(other.pk)
        other.refresh_from_db()
        assert other.requires_approval is False


@pytest.mark.django_db
class TestAnswerQuestionCall:
    def test_partial_answer_recorded_still_halted(self):
        _, _, _, _, _, call = _make_setup()
        _halt(call)
        ok, detail = CallScheduler.answer_question_call(
            call.pk, {"How should I format the output?": "Summary"}
        )
        assert (ok, detail) == (True, "recorded")
        call.refresh_from_db()
        assert call.status_detail == TaskCallStatusDetail.HALTED_APPROVAL
        assert call.carguments_json["answers"] == {
            "How should I format the output?": "Summary"
        }

    def test_complete_answer_approves(self, monkeypatch):
        monkeypatch.setattr(AgentTaskRun, "apply_async", lambda self: None)
        _, _, _, _, _, call = _make_setup()
        _halt(call)
        ok, detail = CallScheduler.answer_question_call(call.pk, {
            "How should I format the output?": "Detailed",
            "Which sections should I include?": ["Introduction", "Conclusion"],
        })
        assert (ok, detail) == (True, "answered")
        call.refresh_from_db()
        assert call.status_detail in (
            TaskCallStatusDetail.WAITING_QUEUE,
            TaskCallStatusDetail.ACTIVE_QUEUED,
        )
        assert call.carguments_json["answers"] == {
            "How should I format the output?": "Detailed",
            "Which sections should I include?": ["Introduction", "Conclusion"],
        }

    def test_answers_accumulate_across_calls(self, monkeypatch):
        monkeypatch.setattr(AgentTaskRun, "apply_async", lambda self: None)
        _, _, _, _, _, call = _make_setup()
        _halt(call)
        assert CallScheduler.answer_question_call(
            call.pk, {"How should I format the output?": "Summary"}
        ) == (True, "recorded")
        assert CallScheduler.answer_question_call(
            call.pk, {"Which sections should I include?": ["Conclusion"]}
        ) == (True, "answered")

    def test_free_text_answer_accepted(self, monkeypatch):
        monkeypatch.setattr(AgentTaskRun, "apply_async", lambda self: None)
        _, _, _, _, _, call = _make_setup()
        _halt(call)
        ok, detail = CallScheduler.answer_question_call(call.pk, {
            "How should I format the output?": "A haiku, please",
            "Which sections should I include?": ["Introduction"],
        })
        assert (ok, detail) == (True, "answered")

    def test_empty_answer_rejected(self):
        _, _, _, _, _, call = _make_setup()
        _halt(call)
        ok, detail = CallScheduler.answer_question_call(
            call.pk, {"How should I format the output?": "  "}
        )
        assert ok is False
        call.refresh_from_db()
        assert call.status_detail == TaskCallStatusDetail.HALTED_APPROVAL

    def test_unknown_question_rejected(self):
        _, _, _, _, _, call = _make_setup()
        _halt(call)
        ok, _ = CallScheduler.answer_question_call(
            call.pk, {"What is the meaning of life?": "42"}
        )
        assert ok is False

    def test_unknown_call(self):
        assert CallScheduler.answer_question_call(999999, {"Q": "A"})[0] is False

    def test_non_halted_call_rejected(self):
        _, _, _, _, _, call = _make_setup()
        ok, _ = CallScheduler.answer_question_call(call.pk, {"Q": "A"})
        assert ok is False

    def test_tool_result_carries_answers(self, monkeypatch):
        """End-to-end: recorded answers become a successful tool result."""
        monkeypatch.setattr(AgentTaskRun, "apply_async", lambda self: None)
        _, _, _, _, _, call = _make_setup()
        _halt(call)
        CallScheduler.answer_question_call(call.pk, {
            "How should I format the output?": "Summary",
            "Which sections should I include?": ["Introduction"],
        })
        call.refresh_from_db()
        module = _load_script(".agentone/scripts/core/ask_user.py")
        ok, result = module.ask_user(
            None,
            call.carguments_json["questions"],
            answers=call.carguments_json["answers"],
        )
        assert ok is True
        assert result["status"] == "success"
        assert result["answers"] == {
            "How should I format the output?": "Summary",
            "Which sections should I include?": ["Introduction"],
        }
        assert "Summary" in result["summary"]

    def test_deny_question_cancels(self):
        session, sv, td, tdv, ti, call = _make_setup()
        _halt(call)
        assert CallScheduler.deny_taskcall(call.pk, feedback="not now") is True
        call.refresh_from_db()
        assert call.status_detail == TaskCallStatusDetail.ENDED_CANCELLED


@pytest.mark.django_db
class TestQuestionCard:
    def _card(self, session):
        from unittest.mock import MagicMock
        from runtime.session.session import Session
        from ui.main.chat.cards.question import QuestionCard

        class MockParent:
            def __init__(self):
                self._instance = MagicMock()
                self.live_session = None

            def _add_child(self, child):
                pass

        # Keep a strong reference — PyHtmlView only holds a weakref.
        self._runtime = Session(session_model=session)
        card = QuestionCard(subject=self._runtime, parent=MockParent())
        card.update = lambda: None
        return card

    def test_pending_items(self):
        session, _, _, _, _, call = _make_setup()
        _halt(call)
        items = self._card(session).pending_items
        assert len(items) == 2
        assert items[0]["question"] == "How should I format the output?"
        assert items[0]["header"] == "Format"
        assert items[0]["multiSelect"] is False
        assert items[0]["options"] == [
            {"oidx": 0, "label": "Summary",
             "description": "Brief overview of key points"},
            {"oidx": 1, "label": "Detailed",
             "description": "Full explanation with examples"},
        ]
        assert items[0]["answered"] is False
        assert items[1]["multiSelect"] is True

    def test_submit_option_records_label(self):
        session, _, _, _, _, call = _make_setup()
        _halt(call)
        self._card(session).submit_option(call.pk, 0, 1)
        call.refresh_from_db()
        assert call.carguments_json["answers"] == {
            "How should I format the output?": "Detailed"
        }
        assert call.status_detail == TaskCallStatusDetail.HALTED_APPROVAL
        items = self._card(session).pending_items
        assert items[0]["answered"] is True
        assert items[0]["answer_text"] == "Detailed"

    def test_submit_option_bad_index_ignored(self):
        session, _, _, _, _, call = _make_setup()
        _halt(call)
        self._card(session).submit_option(call.pk, 0, 99)
        call.refresh_from_db()
        assert "answers" not in call.carguments_json

    def test_submit_multiple_approves_when_complete(self, monkeypatch):
        monkeypatch.setattr(AgentTaskRun, "apply_async", lambda self: None)
        session, _, _, _, _, call = _make_setup()
        _halt(call)
        card = self._card(session)
        card.submit_option(call.pk, 0, 0)
        card.submit_multiple(call.pk, 1, '["0", "1"]')
        call.refresh_from_db()
        assert call.carguments_json["answers"] == {
            "How should I format the output?": "Summary",
            "Which sections should I include?": ["Introduction", "Conclusion"],
        }
        assert call.status_detail != TaskCallStatusDetail.HALTED_APPROVAL

    def test_submit_text_records_free_text(self):
        session, _, _, _, _, call = _make_setup()
        _halt(call)
        self._card(session).submit_text(call.pk, 0, "  A haiku, please  ")
        call.refresh_from_db()
        assert call.carguments_json["answers"] == {
            "How should I format the output?": "A haiku, please"
        }

    def test_submit_blank_text_ignored(self):
        session, _, _, _, _, call = _make_setup()
        _halt(call)
        self._card(session).submit_text(call.pk, 0, "   ")
        call.refresh_from_db()
        assert "answers" not in call.carguments_json

    def test_decline_cancels(self):
        session, _, _, _, _, call = _make_setup()
        _halt(call)
        self._card(session).decline(call.pk, "not now")
        call.refresh_from_db()
        assert call.status_detail == TaskCallStatusDetail.ENDED_CANCELLED

    def test_template_renders(self):
        import jinja2
        from ui.main.chat.cards.question import QuestionCard
        session, _, _, _, _, call = _make_setup()
        _halt(call)
        card = self._card(session)
        env = jinja2.Environment(autoescape=True)
        html = env.from_string(QuestionCard.TEMPLATE_STR).render(pyview=card)
        assert "Questions for you" in html
        assert "Which sections should I include?" in html
        assert "Introduction" in html
        assert "Decline" in html
        assert "pyview.submit_option" in html
        assert "pyview.submit_multiple" in html
        # After answering, the question renders its answer instead of buttons.
        card.submit_option(call.pk, 0, 0)
        html = env.from_string(QuestionCard.TEMPLATE_STR).render(pyview=card)
        assert "Summary" in html
        assert "pyview.submit_option" not in html
@pytest.mark.django_db
class TestAnswerApi:
    def test_answer_partial_then_complete(self, auth_client, monkeypatch):
        from server.models.tasks.agent_task_run import AgentTaskRun as _ATR
        monkeypatch.setattr(_ATR, "apply_async", lambda self: None)
        _, _, _, _, _, call = _make_setup()
        _halt(call)

        resp = auth_client.post(
            f"/api/v1/task-calls/{call.id}/answer/",
            {"answers": {"How should I format the output?": "Summary"}},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data == {"status": "recorded"}

        resp = auth_client.post(
            f"/api/v1/task-calls/{call.id}/answer/",
            {"answers": {"Which sections should I include?": ["Conclusion"]}},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data == {"status": "answered"}

    def test_answer_unknown_call_returns_404(self, auth_client):
        resp = auth_client.post(
            "/api/v1/task-calls/999999/answer/",
            {"answers": {"Q": "A"}},
            format="json",
        )
        assert resp.status_code == 404

    def test_answer_non_halted_returns_409(self, auth_client):
        _, _, _, _, _, call = _make_setup()
        resp = auth_client.post(
            f"/api/v1/task-calls/{call.id}/answer/",
            {"answers": {"How should I format the output?": "Summary"}},
            format="json",
        )
        assert resp.status_code == 409
