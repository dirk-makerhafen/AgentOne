"""Tests for soft session pause (``SessionModel.is_paused``)."""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from runtime.session.session import Session
from runtime.tasks.call_scheduler import CallScheduler
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.enums.message_enums import (
    MessageContentType,
    MessagePartType,
    MessageRole,
)
from server.models.content import GenericContent
from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail
from server.models.message import Message, MessagePart
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel
from server.models.tasks.agent_task_call import AgentTaskCall
from server.tasks.tick_scheduler import _compact_idle_sessions, _release_queued_calls


class SessionPauseTest(TestCase):
    def setUp(self):
        self.agent = AgentModel.objects.create(name="pause-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent,
            agent_settings=SettingsModel.objects.create(
                max_history_messages=100,
                auto_compact_min_tokens=200,
                auto_compact_idle_seconds=60,
            ),
        )
        self.session = SessionModel.objects.create(name="pause-session")
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
        self.rt = Session(session_model=self.session)

    def _call(self, detail=TaskCallStatusDetail.WAITING_QUEUE):
        return AgentTaskCall.objects.create(
            session=self.session,
            session_version=self.sv,
            status=TaskCallStatus.WAITING,
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

    def test_pause_sets_flag_without_deactivation(self):
        self.rt.pause()
        self.session.refresh_from_db()
        self.assertTrue(self.session.is_paused)
        # Pause is not deactivation: active stays True, no session_end semantics.
        self.assertTrue(self.session.is_active)

    def test_start_new_taskrun_blocked_while_paused(self):
        call = self._call()
        self.rt.pause()
        with patch.object(
            CallScheduler, "_pick_up_and_create_run"
        ) as pick_up:
            CallScheduler.start_new_taskrun(call.pk)
            pick_up.assert_not_called()
        call.refresh_from_db()
        self.assertEqual(call.status_detail, TaskCallStatusDetail.WAITING_QUEUE)

    def test_tick_release_skips_paused_and_resumes_after(self):
        call = self._call()
        self.rt.pause()
        with patch.object(CallScheduler, "start_new_taskrun") as start:
            _release_queued_calls()
            start.assert_not_called()
        # Unpause without the resume() side-effect release so the queued
        # call is still WAITING_QUEUE when the tick runs.
        SessionModel.objects.filter(pk=self.session.pk).update(is_paused=False)
        with patch.object(CallScheduler, "start_new_taskrun") as start:
            _release_queued_calls()
            start.assert_called_with(call.pk)

    def test_resume_triggers_immediate_release(self):
        self._call()
        self.rt.pause()
        with patch.object(
            CallScheduler, "_release_next_queued_call"
        ) as release:
            self.rt.resume()
            release.assert_called_once()
        self.session.refresh_from_db()
        self.assertFalse(self.session.is_paused)

    def test_compact_skips_paused_session(self):
        from datetime import timedelta

        from django.utils import timezone

        prev = None
        for _ in range(3):
            m = Message.objects.create(
                session=self.session, session_version=self.sv,
                role=MessageRole.USER,
            )
            MessagePart.objects.create(
                message=m,
                type=MessagePartType.MESSAGE,
                content=GenericContent.from_text("x" * 2000),
                content_type=MessageContentType.TEXT,
            )
            Message.objects.filter(pk=m.pk).update(prev_message=prev)
            prev = m
        Message.objects.filter(session_id=self.session.pk).update(
            created_at=timezone.now() - timedelta(minutes=10)
        )
        self.rt.pause()

        class FakeTask:
            def __init__(self):
                self.delay_kwargs = None

            def delay(self, *args, **kwargs):
                self.delay_kwargs = kwargs
                return None

        fake = FakeTask()
        with patch.object(Session, "get_task", return_value=fake):
            _compact_idle_sessions()
        self.assertIsNone(fake.delay_kwargs)
