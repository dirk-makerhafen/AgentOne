"""Reproduction: does the switched key stick across MULTIPLE turns?"""
from __future__ import annotations
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from runtime.session.session import Session
from runtime.rate_limiter import RateLimitChecker, RateLimitError
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.enums.task_enums import (
    TaskCallStatus,
    TaskCallStatusDetail,
    TaskExecutionMode,
)
from server.models.providers.api_key import ApiKey
from server.models.providers.api_provider import ApiProvider
from server.models.providers.ai_model import AiModel
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion
from server.models.tasks.task_instance import TaskInstance


class MultiTurnStickinessTest(TestCase):
    def setUp(self):
        self.provider = ApiProvider.objects.create(name="google")
        self.key_a = ApiKey.objects.create(api_provider=self.provider, key="ka", enabled=True)
        self.key_b = ApiKey.objects.create(api_provider=self.provider, key="kb", enabled=True)
        self.model = AiModel.objects.create(api_provider=self.provider, name="Alpha", provider_model_id="sql-alpha")
        self.agent = AgentModel.objects.create(name="ag")
        self.av = AgentVersionModel.objects.create(agent=self.agent, agent_settings=SettingsModel.objects.create())
        self.session = SessionModel.objects.create(name="s")
        self.sv = SessionVersionModel.objects.create(session=self.session, agent=self.agent, pinned_agent_version=self.av)
        SessionModel.objects.filter(pk=self.session.pk).update(latest_session_version=self.sv)
        self.session.refresh_from_db()

        self.tdv_call = TaskDefinitionVersion.objects.create(
            task_definition=TaskDefinition.objects.create(name="call_llm"),
            description="", function_schema={}, task_type="TASK",
            task_execution_mode=TaskExecutionMode.FUNCTION, requires_approval=False,
        )
        self.tdv_decide = TaskDefinitionVersion.objects.create(
            task_definition=TaskDefinition.objects.create(name="decide_next_step"),
            description="", function_schema={}, task_type="TASK",
            task_execution_mode=TaskExecutionMode.FUNCTION, requires_approval=False,
        )

    def _cooldown(self, key, seconds):
        ApiKey.objects.filter(pk=key.pk).update(rate_limit_until=timezone.now() + timedelta(seconds=seconds))

    def _taskcall(self, session_version, instance, status_detail=TaskCallStatusDetail.WAITING_RATELIMIT):
        return AgentTaskCall.objects.create(
            session=self.session, session_version=session_version, task_instance=instance,
            requires_approval=False, max_subtask_errors=0, max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=0,
            max_retries=0, retry_delay=0, retry_requires_approval=False,
            status=TaskCallStatus.WAITING, status_detail=status_detail,
        )

    def _chain(self, session_version):
        """A minimal process_turn chain: root -> [call_llm, decide_next_step]."""
        root = TaskInstance.objects.create(
            session=self.session, session_version=session_version,
            requires_approval=False, max_subtask_errors=0, max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=0,
            max_retries=0, retry_delay=0, retry_requires_approval=False,
        )
        call_llm = TaskInstance.objects.create(
            session=self.session, session_version=session_version,
            task_definition_version=self.tdv_call, requires_approval=False,
            max_subtask_errors=0, max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=0,
            max_retries=0, retry_delay=0, retry_requires_approval=False,
        )
        decide = TaskInstance.objects.create(
            session=self.session, session_version=session_version,
            task_definition_version=self.tdv_decide, requires_approval=False,
            max_subtask_errors=0, max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=0,
            max_retries=0, retry_delay=0, retry_requires_approval=False,
        )
        root.child_instances.add(call_llm, decide)
        return root, call_llm, decide

    def test_switched_key_sticks_across_turns(self):
        runtime = Session(session_model=self.session)
        runtime.set_aimodel(self.model)
        # turn 1: adopt A, then A cools
        RateLimitChecker.check(self.model, session=runtime)
        self._cooldown(self.key_a, 3000)
        try:
            RateLimitChecker.check(self.model, session=runtime)
        except RateLimitError:
            pass
        self.assertEqual(runtime.current_provider_api_key(self.model).pk, self.key_a.pk)

        # user switches to B -> new version with preferred B, checker returns B
        runtime.set_preferred_api_key(self.key_b)
        print("== TURN AFTER SWITCH ==")
        r1 = RateLimitChecker.check(self.model, session=runtime)
        print("TURN1 selected:", r1.selected_key.pk, "preferred:", runtime.preferred_api_key().pk if runtime.preferred_api_key() else None)

        # the DB latest version now carries preferred B...
        db_session = SessionModel.objects.get(pk=self.session.pk)
        print("DB latest version:", db_session.latest_session_version_id,
              "== sv used?", db_session.latest_session_version == runtime.get_version_model())

        # turn 2: a NEW runtime built the way the WORKER does when a NEW
        # message arrives and dispatches from latest session version.
        worker_session = Session(session_model=SessionModel.objects.get(pk=self.session.pk))
        worker_session.set_aimodel(self.model)
        r2 = RateLimitChecker.check(self.model, session=worker_session)
        print("TURN2 selected:", r2.selected_key.pk,
              "preferred:", worker_session.preferred_api_key().pk if worker_session.preferred_api_key() else None)

        # turn 3: same again
        worker_session3 = Session(session_model=SessionModel.objects.get(pk=self.session.pk))
        worker_session3.set_aimodel(self.model)
        r3 = RateLimitChecker.check(self.model, session=worker_session3)
        print("TURN3 selected:", r3.selected_key.pk,
              "preferred:", worker_session3.preferred_api_key().pk if worker_session3.preferred_api_key() else None)

        self.assertEqual(r1.selected_key.pk, self.key_b.pk)
        self.assertEqual(r2.selected_key.pk, self.key_b.pk)
        self.assertEqual(r3.selected_key.pk, self.key_b.pk)

    def test_repoint_moves_whole_chain_to_latest(self):
        """Regression: switching the key must re-point the ENTIRE chain (root +
        sibling calls like decide_next_step), not just the parked call, so the
        next query dispatched by decide_next_step uses the switched key."""
        from runtime.tasks.call_scheduler import CallScheduler

        runtime = Session(session_model=self.session)
        runtime.set_aimodel(self.model)
        RateLimitChecker.check(self.model, session=runtime)  # adopt A
        self._cooldown(self.key_a, 3000)
        old_sv = runtime.get_version_model()

        root, call_llm, decide = self._chain(old_sv)
        parked = self._taskcall(old_sv, call_llm)
        decide_call = self._taskcall(
            old_sv, decide,
            status_detail=TaskCallStatusDetail.WAITING_DEPENDENCY,
        )
        print("old sv:", old_sv.pk, "root:", root.pk, "call_llm:", call_llm.pk)

        # User clicks "Switch to key B" -> new version + release(repoint=True).
        runtime.set_preferred_api_key(self.key_b)
        latest = SessionModel.objects.get(pk=self.session.pk).latest_session_version
        print("latest:", latest.pk)
        with patch("runtime.tasks.call_fsm._publish_call_event"), patch.object(
            CallScheduler, "start_new_taskrun"
        ):
            released = CallScheduler.release_waiting_ratelimit_calls(
                self.session, repoint=True
            )

        self.assertEqual(released, 1)
        # The parked call AND the sibling decide_next_step call move to latest.
        parked.refresh_from_db()
        decide_call.refresh_from_db()
        call_llm.refresh_from_db()
        root.refresh_from_db()
        decide.refresh_from_db()
        print("parked sv:", parked.session_version_id, "decide sv:", decide_call.session_version_id)
        self.assertEqual(parked.session_version_id, latest.pk)
        self.assertEqual(decide_call.session_version_id, latest.pk)
        self.assertEqual(call_llm.session_version_id, latest.pk)
        self.assertEqual(decide.session_version_id, latest.pk)

        # The next query (decide_next_step dispatch) is created against latest
        # and therefore selects the switched key B.
        cont = Session(session_model=self.session, pinned_session_version=latest)
        r = RateLimitChecker.check(self.model, session=cont)
        print("CONTINUATION selected:", r.selected_key.pk)
        self.assertEqual(r.selected_key.pk, self.key_b.pk)
