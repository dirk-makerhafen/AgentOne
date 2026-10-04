"""Tests for idle-triggered compaction (``tick_scheduler._compact_idle_sessions``)."""
from __future__ import annotations

import importlib.util
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from runtime.session.session import Session
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.content import GenericContent
from server.models.enums.message_enums import (
    MessageContentType,
    MessagePartType,
    MessageRole,
)
from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail
from server.models.message import Message, MessagePart
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel
from server.models.tasks.agent_task_call import AgentTaskCall
from server.tasks.tick_scheduler import _compact_idle_sessions

BUILD_COMPACT_PATH = (
    Path(__file__).parent.parent.parent
    / ".agentone"
    / "scripts"
    / "compact"
    / "build_llm_compact_context.py"
)


def _load_build_module():
    spec = importlib.util.spec_from_file_location(
        "agentone_build_compact_under_test", BUILD_COMPACT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeCompactTask:
    """Stand-in for the ``compact_turn`` bound task — records ``delay`` kwargs."""

    def __init__(self):
        self.delay_kwargs = None

    def delay(self, *args, **kwargs):
        self.delay_kwargs = kwargs
        return None


class IdleCompactionTest(TestCase):
    def setUp(self):
        self.agent = AgentModel.objects.create(name="test-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent,
            agent_settings=SettingsModel.objects.create(
                max_history_messages=100,
                auto_compact_min_tokens=200,
                auto_compact_idle_seconds=60,
            ),
        )
        self.session = SessionModel.objects.create(name="test-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session,
            agent=self.agent,
            pinned_agent_version=self.av,
        )
        SessionModel.objects.filter(pk=self.session.pk).update(
            latest_session_version=self.sv
        )
        AgentModel.objects.filter(pk=self.agent.pk).update(
            latest_agent_version=self.av
        )
        self.session.refresh_from_db()
        self.fake_task = FakeCompactTask()
        patcher = patch.object(Session, "get_task", return_value=self.fake_task)
        self.mock_get_task = patcher.start()
        self.addCleanup(patcher.stop)

    def _msg(self, text: str) -> Message:
        msg = Message.objects.create(
            session=self.session,
            session_version=self.sv,
            role=MessageRole.USER,
        )
        MessagePart.objects.create(
            message=msg,
            type=MessagePartType.MESSAGE,
            content=GenericContent.from_text(text),
            content_type=MessageContentType.TEXT,
        )
        return msg

    def _link(self, messages: list[Message]) -> None:
        prev = None
        for m in messages:
            Message.objects.filter(pk=m.pk).update(prev_message=prev)
            prev = m

    def _backdate(self, minutes: int = 10) -> None:
        Message.objects.filter(session_id=self.session.pk).update(
            created_at=timezone.now() - timedelta(minutes=minutes)
        )

    def _call(self, status: str, detail: str) -> AgentTaskCall:
        return AgentTaskCall.objects.create(
            session=self.session,
            session_version=self.sv,
            status=status,
            status_detail=detail,
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

    def _big_session(self, n: int = 3) -> list[Message]:
        msgs = [self._msg("x" * 2000) for _ in range(n)]
        self._link(msgs)
        return msgs

    def test_idle_oversized_dispatches_with_idle_trigger(self):
        msgs = self._big_session()
        self._backdate()
        _compact_idle_sessions()
        self.assertIsNotNone(self.fake_task.delay_kwargs)
        self.assertTrue(self.fake_task.delay_kwargs["idle_trigger"])
        self.assertEqual(
            self.fake_task.delay_kwargs["message"].pk, msgs[-1].pk
        )

    def test_fresh_activity_does_not_dispatch(self):
        self._big_session()
        _compact_idle_sessions()
        self.assertIsNone(self.fake_task.delay_kwargs)

    def test_below_min_tokens_does_not_dispatch(self):
        msgs = [self._msg("hi") for _ in range(3)]
        self._link(msgs)
        self._backdate()
        _compact_idle_sessions()
        self.assertIsNone(self.fake_task.delay_kwargs)

    def test_live_turn_blocks_dispatch(self):
        self._big_session()
        self._backdate()
        self._call(TaskCallStatus.ACTIVE, TaskCallStatusDetail.ACTIVE_RUNNING)
        _compact_idle_sessions()
        self.assertIsNone(self.fake_task.delay_kwargs)

    def test_queued_work_blocks_dispatch(self):
        self._big_session()
        self._backdate()
        self._call(TaskCallStatus.WAITING, TaskCallStatusDetail.WAITING_QUEUE)
        _compact_idle_sessions()
        self.assertIsNone(self.fake_task.delay_kwargs)

    def test_approval_halt_counts_as_idle(self):
        # Halted for approval: no live work, so the session is idle-eligible.
        # The boundary guard keeps the undecided toolcall live at run time.
        self._big_session()
        self._backdate()
        self._call(TaskCallStatus.HALTED, TaskCallStatusDetail.HALTED_APPROVAL)
        _compact_idle_sessions()
        self.assertIsNotNone(self.fake_task.delay_kwargs)

    def test_paused_session_is_hands_off(self):
        self._big_session()
        self._backdate()
        self._call(TaskCallStatus.HALTED, TaskCallStatusDetail.HALTED_PAUSED)
        _compact_idle_sessions()
        self.assertIsNone(self.fake_task.delay_kwargs)

    def test_single_message_has_no_boundary(self):
        # One message always fits the keep budget — nothing to compact.
        self._big_session(n=1)
        self._backdate()
        _compact_idle_sessions()
        self.assertIsNone(self.fake_task.delay_kwargs)

    def test_unset_knobs_opt_out(self):
        agent = AgentModel.objects.create(name="plain-agent")
        av = AgentVersionModel.objects.create(
            agent=agent,
            agent_settings=SettingsModel.objects.create(
                max_history_messages=100
            ),
        )
        session = SessionModel.objects.create(name="plain-session")
        sv = SessionVersionModel.objects.create(
            session=session, agent=agent, pinned_agent_version=av
        )
        SessionModel.objects.filter(pk=session.pk).update(
            latest_session_version=sv
        )
        AgentModel.objects.filter(pk=agent.pk).update(latest_agent_version=av)
        prev = None
        for _ in range(3):
            m = Message.objects.create(
                session=session, session_version=sv, role=MessageRole.USER
            )
            MessagePart.objects.create(
                message=m,
                type=MessagePartType.MESSAGE,
                content=GenericContent.from_text("x" * 2000),
                content_type=MessageContentType.TEXT,
            )
            Message.objects.filter(pk=m.pk).update(prev_message=prev)
            prev = m
        Message.objects.filter(session_id=session.pk).update(
            created_at=timezone.now() - timedelta(minutes=10)
        )
        _compact_idle_sessions()
        self.assertIsNone(self.fake_task.delay_kwargs)

    def test_stale_idle_trigger_passes_through_quietly(self):
        # A turn started between dispatch and run: build must no-op with no
        # side effects (no INFO notice, no compaction fork session).
        mod = _load_build_module()
        msgs = self._big_session()  # fresh timestamps — no longer idle
        runtime = Session(session_model=self.session)
        info_before = Message.objects.filter(
            session_id=self.session.pk, role=MessageRole.INFO
        ).count()
        sessions_before = SessionModel.objects.count()
        out = mod.build_llm_compact_context(
            runtime, msgs[-1], idle_trigger=True
        )
        self.assertEqual(out["message"].pk, msgs[-1].pk)
        self.assertEqual(
            Message.objects.filter(
                session_id=self.session.pk, role=MessageRole.INFO
            ).count(),
            info_before,
        )
        self.assertEqual(SessionModel.objects.count(), sessions_before)
