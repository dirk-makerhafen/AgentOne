"""Tests for the rate-limit handling surfaced in the UI:

* escalating, quota-aware API-key cooldowns (``ApiKey.record_provider_cooldown``)
* the release helper used by the rate-limit card
  (``CallScheduler.release_waiting_ratelimit_calls``)
* the rate-limit card's data builders (alternatives, wait time)
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from runtime.session.session import Session
from runtime.rate_limiter import RateLimitChecker, RateLimitError

from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail
from server.models.queries.query import Query
from server.models.providers.api_key import ApiKey
from server.models.providers.api_provider import ApiProvider
from server.models.providers.ai_model import AiModel
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel
from server.models.tasks.agent_task_call import AgentTaskCall

from ui.main.chat.cards.rate_limit import RateLimitCard, _humanize_seconds

# pylint: disable=protected-access  # exercising internal builders


class ApiKeyEscalatingCooldownTest(TestCase):
    """Consecutive 429s escalate; success resets; quota reads as long wait."""

    def setUp(self):
        self.provider = ApiProvider.objects.create(name="p1")
        self.key = ApiKey.objects.create(api_provider=self.provider, key="k1", enabled=True)

    def _wait(self) -> float:
        self.key.refresh_from_db()
        return (self.key.rate_limit_until - timezone.now()).total_seconds()

    def test_explicit_delay_then_escalates(self):
        self.key.record_provider_cooldown(58)
        self.assertAlmostEqual(self._wait(), 58, delta=2)
        self.key.record_provider_cooldown(58)
        self.key.refresh_from_db()
        self.assertEqual(self.key.rate_limit_hits, 2)
        self.assertAlmostEqual(self._wait(), 116, delta=2)

    def test_default_cooldown_escalates_without_delay(self):
        self.key.record_provider_cooldown(None, reason="Rate limit exceeded")
        self.assertAlmostEqual(self._wait(), 60, delta=2)
        self.key.record_provider_cooldown(None, reason="Rate limit exceeded")
        self.assertAlmostEqual(self._wait(), 120, delta=2)
        self.key.record_provider_cooldown(None, reason="Rate limit exceeded")
        self.assertAlmostEqual(self._wait(), 240, delta=2)

    def test_quota_exhaustion_gets_long_default(self):
        self.key.record_provider_cooldown(None, reason="You have exceeded your daily quota")
        self.assertAlmostEqual(self._wait(), 3600, delta=2)
        self.assertEqual(self.key.rate_limit_hits, 1)

    def test_escalation_level_capped(self):
        # Multiplier stops doubling after 4th consecutive hit (8x ceiling).
        for _ in range(10):
            self.key.record_provider_cooldown(60)
        self.key.refresh_from_db()
        self.assertEqual(self.key.rate_limit_hits, 10)
        self.assertAlmostEqual(self._wait(), 480, delta=2)

    def test_clear_resets_hits(self):
        self.key.record_provider_cooldown(60)
        self.key.record_provider_cooldown(60)
        self.key.clear_provider_cooldown()
        self.key.refresh_from_db()
        self.assertIsNone(self.key.rate_limit_until)
        self.assertEqual(self.key.rate_limit_hits, 0)
        # Next 429 starts back at the base cooldown.
        self.key.record_provider_cooldown(60)
        self.assertAlmostEqual(self._wait(), 60, delta=2)


class ReleaseWaitingRatelimitHelperTest(TestCase):
    """The switch-then-release path used by the rate-limit card."""

    def setUp(self):
        self.p1 = ApiProvider.objects.create(name="p1")
        self.p2 = ApiProvider.objects.create(name="p2")
        ApiKey.objects.create(api_provider=self.p1, key="k1", enabled=True)
        ApiKey.objects.create(api_provider=self.p2, key="k2", enabled=True)
        self.alpha_p1 = AiModel.objects.create(
            api_provider=self.p1, name="Alpha", provider_model_id="sql-alpha"
        )
        self.alpha_p2 = AiModel.objects.create(
            api_provider=self.p2, name="Alpha", provider_model_id="apisql-alpha"
        )
        self.agent = AgentModel.objects.create(name="ratelimit-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent,
            agent_settings=SettingsModel.objects.create(),
        )
        self.session = SessionModel.objects.create(name="ratelimit-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session,
            agent=self.agent,
            pinned_agent_version=self.av,
        )
        SessionModel.objects.filter(pk=self.session.pk).update(
            latest_session_version=self.sv
        )
        self.session.refresh_from_db()
        AgentModel.objects.filter(pk=self.agent.pk).update(latest_agent_version=self.av)

    def _parked_call(self, session_version) -> AgentTaskCall:
        return AgentTaskCall.objects.create(
            session=self.session,
            session_version=session_version,
            requires_approval=False,
            max_subtask_errors=0,
            max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=0,
            max_retries=0,
            retry_delay=0,
            retry_requires_approval=False,
            status=TaskCallStatus.WAITING,
            status_detail=TaskCallStatusDetail.WAITING_RATELIMIT,
        )

    def test_repoints_and_releases_parked_call_after_switch(self):
        from runtime.tasks.call_scheduler import CallScheduler

        session = Session(session_model=self.session)
        session.set_aimodel(self.alpha_p1)
        old_sv = session.get_version_model()
        call = self._parked_call(old_sv)

        # User switches the provider from the rate-limit card, then releases.
        session.set_aimodel(self.alpha_p2)
        latest = self.session.latest_session_version
        with patch("runtime.tasks.call_fsm._publish_call_event"), patch.object(
            CallScheduler, "start_new_taskrun"
        ) as start:
            released = CallScheduler.release_waiting_ratelimit_calls(
                self.session, repoint=True
            )

        self.assertEqual(released, 1)
        call.refresh_from_db()
        self.assertEqual(call.session_version_id, latest.pk)
        self.assertEqual(call.status_detail, TaskCallStatusDetail.WAITING_QUEUE)
        start.assert_called_once_with(call.pk)

    def test_stays_parked_when_new_model_still_blocked(self):
        from runtime.tasks.call_scheduler import CallScheduler

        # Block the key the session will resolve to before switching.
        ApiKey.objects.filter(api_provider=self.p2).update(
            rate_limit_until=timezone.now() + timedelta(seconds=3000)
        )
        session = Session(session_model=self.session)
        session.set_aimodel(self.alpha_p1)
        old_sv = session.get_version_model()
        old_sv_pk = old_sv.pk  # copy-on-write mutates the object's pk below
        call = self._parked_call(old_sv)

        session.set_aimodel(self.alpha_p2)
        with patch("runtime.tasks.call_fsm._publish_call_event"), patch.object(
            CallScheduler, "start_new_taskrun"
        ) as start:
            released = CallScheduler.release_waiting_ratelimit_calls(
                self.session, repoint=True
            )

        self.assertEqual(released, 0)
        call.refresh_from_db()
        # Not re-pointed, not released — the card keeps offering alternatives.
        self.assertEqual(call.session_version_id, old_sv_pk)
        self.assertEqual(call.status_detail, TaskCallStatusDetail.WAITING_RATELIMIT)
        start.assert_not_called()


class MockParent:
    """Minimal Chat stand-in for building the card in isolation."""

    def __init__(self):
        self._instance = MagicMock()
        self.composer_box = MagicMock()

    def _add_child(self, child):
        pass


class RateLimitCardTest(TestCase):
    def setUp(self):
        self.p1 = ApiProvider.objects.create(name="p1")
        self.p2 = ApiProvider.objects.create(name="p2")
        ApiKey.objects.create(api_provider=self.p1, key="k1", enabled=True)
        ApiKey.objects.create(api_provider=self.p2, key="k2", enabled=True)
        self.alpha_sql = AiModel.objects.create(
            api_provider=self.p1, name="Alpha", provider_model_id="sql-alpha"
        )
        self.alpha_apisql = AiModel.objects.create(
            api_provider=self.p2, name="Alpha", provider_model_id="apisql-alpha"
        )
        self.beta = AiModel.objects.create(
            api_provider=self.p1, name="Beta", provider_model_id="beta"
        )
        self.agent = AgentModel.objects.create(name="card-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent,
            agent_settings=SettingsModel.objects.create(),
        )
        self.session = SessionModel.objects.create(name="card-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session,
            agent=self.agent,
            pinned_agent_version=self.av,
        )
        SessionModel.objects.filter(pk=self.session.pk).update(
            latest_session_version=self.sv
        )
        self.session.refresh_from_db()

    def _card(self) -> RateLimitCard:
        # Keep a strong reference to the subject — PyHtmlView only holds a
        # weakref, and an unreferenced Session would be GC'd (subject dies).
        self._runtime = Session(session_model=self.session)
        return RateLimitCard(subject=self._runtime, parent=MockParent())

    def test_humanize_seconds(self):
        self.assertEqual(_humanize_seconds(45), "45s")
        self.assertEqual(_humanize_seconds(125), "2m 5s")
        self.assertEqual(_humanize_seconds(120), "2m")

    def test_cooldown_wait_returns_min_remaining(self):
        k_short = ApiKey.objects.create(api_provider=self.p1, key="short", enabled=True)
        ApiKey.objects.create(api_provider=self.p1, key="long", enabled=True)
        k_short.record_provider_cooldown(60)
        ApiKey.objects.filter(api_provider=self.p1).filter(key__in=["long"]).update(
            rate_limit_until=timezone.now() + timedelta(seconds=600)
        )
        wait = RateLimitCard._cooldown_wait_seconds(self.p1)
        self.assertIsNotNone(wait)
        self.assertGreaterEqual(wait, 55)  # min window wins, not the long one

    def test_provider_alternatives_lists_sibling(self):
        card = self._card()
        rows = {r["provider"]: r for r in card._provider_rows(self.alpha_sql)}
        self.assertIn("p2", rows)
        self.assertEqual(rows["p2"]["keys_text"], "1 key")
        self.assertEqual(rows["p2"]["provider_id"], self.p2.pk)

    def test_provider_alternatives_flag_cooling_key(self):
        ApiKey.objects.filter(api_provider=self.p2).update(
            rate_limit_until=timezone.now() + timedelta(seconds=300)
        )
        card = self._card()
        rows = {r["provider"]: r for r in card._provider_rows(self.alpha_sql)}
        self.assertIn("cooling", rows["p2"]["keys_text"])

    def test_model_alternatives_excludes_current(self):
        card = self._card()
        rows = {r["name"]: r for r in card._model_rows(self.alpha_sql)}
        self.assertIn("Beta", rows)
        self.assertNotIn("Alpha", rows)

    def test_pending_calls_snapshot_and_blocked(self):
        from server.models.tasks.agent_task_call import AgentTaskCall

        pinned = Session(session_model=self.session)
        pinned.set_aimodel(self.alpha_sql)
        AgentTaskCall.objects.create(
            session=self.session,
            session_version=pinned.get_version_model(),
            requires_approval=False,
            max_subtask_errors=0,
            max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=0,
            max_retries=0,
            retry_delay=0,
            retry_requires_approval=False,
            status=TaskCallStatus.WAITING,
            status_detail=TaskCallStatusDetail.WAITING_RATELIMIT,
        )
        card = self._card()
        snap = card._snapshot
        self.assertEqual(snap["pending_count"], 1)
        self.assertEqual(snap["blocked"]["model"], "Alpha")
        self.assertEqual(snap["blocked"]["provider"], "p1")

    def test_blocked_wait_text_reflects_cooldown(self):
        pinned = Session(session_model=self.session)
        pinned.set_aimodel(self.alpha_sql)
        fixed = timezone.now()
        with patch("django.utils.timezone.now", return_value=fixed):
            ApiKey.objects.filter(api_provider=self.p1).update(
                rate_limit_until=fixed + timedelta(seconds=125)
            )
            card = self._card()
            self.assertEqual(card._blocked_info(self.alpha_sql)["wait_text"], "2m 5s")

    def test_no_alternatives_when_single_provider(self):
        card = self._card()
        self.assertEqual(card._provider_rows(self.beta), [])


class ReleaseRoundTripTest(TestCase):
    """End-to-end: a parked call is re-pointed and released by the helper."""

    def test_happy_path_via_real_fsm(self):
        from runtime.tasks.call_scheduler import CallScheduler

        provider = ApiProvider.objects.create(name="p1")
        ApiKey.objects.create(api_provider=provider, key="k1", enabled=True)
        model = AiModel.objects.create(
            api_provider=provider, name="Alpha", provider_model_id="sql-alpha"
        )
        agent = AgentModel.objects.create(name="rt-agent")
        av = AgentVersionModel.objects.create(
            agent=agent, agent_settings=SettingsModel.objects.create()
        )
        session = SessionModel.objects.create(name="rt-session")
        sv = SessionVersionModel.objects.create(
            session=session, agent=agent, pinned_agent_version=av
        )
        SessionModel.objects.filter(pk=session.pk).update(latest_session_version=sv)
        session.refresh_from_db()

        runtime = Session(session_model=session)
        runtime.set_aimodel(model)
        pinned = runtime.get_version_model()
        call = AgentTaskCall.objects.create(
            session=session,
            session_version=pinned,
            requires_approval=False,
            max_subtask_errors=0,
            max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=0,
            max_retries=0,
            retry_delay=0,
            retry_requires_approval=False,
            status=TaskCallStatus.WAITING,
            status_detail=TaskCallStatusDetail.WAITING_RATELIMIT,
        )
        latest = session.latest_session_version
        with patch("runtime.tasks.call_fsm._publish_call_event"), patch.object(
            CallScheduler, "start_new_taskrun"
        ) as start:
            released = CallScheduler.release_waiting_ratelimit_calls(session)
        self.assertEqual(released, 1)
        start.assert_called_once_with(call.pk)
        call.refresh_from_db()
        self.assertEqual(call.session_version_id, latest.pk)
        self.assertEqual(call.status_detail, TaskCallStatusDetail.WAITING_QUEUE)


class MultiKeySessionTest(TestCase):
    """Shared fixtures: one provider, two keys, one model."""

    def setUp(self):
        self.provider = ApiProvider.objects.create(name="google")
        self.key_a = ApiKey.objects.create(
            api_provider=self.provider, key="ka", enabled=True
        )
        self.key_b = ApiKey.objects.create(
            api_provider=self.provider, key="kb", enabled=True
        )
        self.model = AiModel.objects.create(
            api_provider=self.provider, name="Alpha", provider_model_id="sql-alpha"
        )
        self.agent = AgentModel.objects.create(name="mk-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent,
            agent_settings=SettingsModel.objects.create(),
        )
        self.session = SessionModel.objects.create(name="mk-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session, agent=self.agent, pinned_agent_version=self.av,
        )
        SessionModel.objects.filter(pk=self.session.pk).update(
            latest_session_version=self.sv
        )
        self.session.refresh_from_db()

    def _runtime(self) -> Session:
        return Session(session_model=self.session)

    def _adopt(self, runtime: Session) -> None:
        """Run the checker once so the session adopts its sticky key."""
        result = RateLimitChecker.check(self.model, session=runtime)
        self.assertIsNotNone(result.selected_key)

    def _cooldown(self, key: ApiKey, seconds: int) -> None:
        ApiKey.objects.filter(pk=key.pk).update(
            rate_limit_until=timezone.now() + timedelta(seconds=seconds)
        )


class KeyStickinessTest(MultiKeySessionTest):
    """Default = strict per-key cooldown; failover/max-wait rotate keys."""

    def test_default_sticks_to_adopted_key(self):
        runtime = self._runtime()
        runtime.set_aimodel(self.model)
        self._adopt(runtime)
        self.assertEqual(
            runtime.current_provider_api_key(self.model).pk, self.key_a.pk
        )
        # Strict default never rotates to the healthy sibling key.
        self._cooldown(self.key_a, 3000)
        with self.assertRaises(RateLimitError):
            RateLimitChecker.check(self.model, session=runtime)
        self.assertEqual(
            runtime.current_provider_api_key(self.model).pk, self.key_a.pk
        )

    def test_auto_failover_rotates_to_ready_key(self):
        runtime = self._runtime()
        runtime.set_aimodel(self.model)
        self._adopt(runtime)
        self._cooldown(self.key_a, 3000)
        runtime.set_auto_failover_keys(True)
        result = RateLimitChecker.check(self.model, session=runtime)
        self.assertEqual(result.selected_key.pk, self.key_b.pk)
        self.assertEqual(runtime.preferred_api_key().pk, self.key_b.pk)

    def test_max_wait_rotates_when_wait_exceeds(self):
        runtime = self._runtime()
        runtime.set_aimodel(self.model)
        self._adopt(runtime)
        self._cooldown(self.key_a, 300)
        runtime.set_key_max_wait_seconds(5)
        result = RateLimitChecker.check(self.model, session=runtime)
        self.assertEqual(result.selected_key.pk, self.key_b.pk)

    def test_max_wait_keeps_waiting_when_within_budget(self):
        runtime = self._runtime()
        runtime.set_aimodel(self.model)
        self._adopt(runtime)
        self._cooldown(self.key_a, 300)
        runtime.set_key_max_wait_seconds(600)
        with self.assertRaises(RateLimitError):
            RateLimitChecker.check(self.model, session=runtime)
        # Still on the sticky key.
        self.assertEqual(
            runtime.current_provider_api_key(self.model).pk, self.key_a.pk
        )

    def test_failover_parks_when_all_keys_cooling(self):
        runtime = self._runtime()
        runtime.set_aimodel(self.model)
        runtime.set_auto_failover_keys(True)
        self._cooldown(self.key_a, 3000)
        self._cooldown(self.key_b, 3000)
        with self.assertRaises(RateLimitError):
            RateLimitChecker.check(self.model, session=runtime)

    def test_current_key_derived_from_last_query_when_no_preference(self):
        runtime = self._runtime()
        runtime.set_aimodel(self.model)
        Query.objects.create(
            session=self.session,
            session_version=runtime.get_version_model(),
            apikey=self.key_b,
        )
        self.assertEqual(
            runtime.current_provider_api_key(self.model).pk, self.key_b.pk
        )

    def test_rotation_honors_explicit_switch_key(self):
        runtime = self._runtime()
        runtime.set_aimodel(self.model)
        runtime.set_preferred_api_key(self.key_b)
        result = RateLimitChecker.check(self.model, session=runtime)
        self.assertEqual(result.selected_key.pk, self.key_b.pk)


class KeyStickinessReleaseTest(MultiKeySessionTest):
    """The release path honours the session's key-stickiness policy."""

    def _parked_call(self, session_version) -> AgentTaskCall:
        return AgentTaskCall.objects.create(
            session=self.session,
            session_version=session_version,
            requires_approval=False,
            max_subtask_errors=0,
            max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=0,
            max_retries=0,
            retry_delay=0,
            retry_requires_approval=False,
            status=TaskCallStatus.WAITING,
            status_detail=TaskCallStatusDetail.WAITING_RATELIMIT,
        )

    def test_strict_keeps_parked_even_with_ready_sibling_key(self):
        from runtime.tasks.call_scheduler import CallScheduler

        runtime = self._runtime()
        runtime.set_aimodel(self.model)
        self._adopt(runtime)
        self._cooldown(self.key_a, 3000)

        call = self._parked_call(runtime.get_version_model())
        with patch("runtime.tasks.call_fsm._publish_call_event"), patch.object(
            CallScheduler, "start_new_taskrun"
        ) as start:
            released = CallScheduler.release_waiting_ratelimit_calls(
                self.session, repoint=True
            )
        self.assertEqual(released, 0)
        call.refresh_from_db()
        self.assertEqual(call.status_detail, TaskCallStatusDetail.WAITING_RATELIMIT)
        start.assert_not_called()

    def test_explicit_switch_key_releases_in_strict_mode(self):
        """The card's "Switch key" action (strict default) must unblock the
        parked call by moving the session onto the chosen ready key."""
        from runtime.tasks.call_scheduler import CallScheduler

        runtime = self._runtime()
        runtime.set_aimodel(self.model)
        self._adopt(runtime)
        self._cooldown(self.key_a, 3000)

        call = self._parked_call(runtime.get_version_model())
        # Simulate the card action: pick key B explicitly (no failover on).
        runtime.set_preferred_api_key(self.key_b)
        with patch("runtime.tasks.call_fsm._publish_call_event"), patch.object(
            CallScheduler, "start_new_taskrun"
        ) as start:
            released = CallScheduler.release_waiting_ratelimit_calls(
                self.session, repoint=True
            )
        self.assertEqual(released, 1)
        call.refresh_from_db()
        self.assertEqual(call.status_detail, TaskCallStatusDetail.WAITING_QUEUE)
        start.assert_called_once_with(call.pk)
        # The card would now show key B as current and B is ready, so no wait.
        self.assertEqual(
            self._runtime().current_provider_api_key(self.model).pk, self.key_b.pk
        )

    def test_card_switch_key_action_releases_and_hides_card(self):
        """End-to-end through the card action itself."""
        from runtime.tasks.call_scheduler import CallScheduler

        runtime = self._runtime()
        runtime.set_aimodel(self.model)
        self._adopt(runtime)
        self._cooldown(self.key_a, 3000)
        call = self._parked_call(runtime.get_version_model())

        card = RateLimitCard(subject=runtime, parent=MockParent())
        with patch("runtime.tasks.call_fsm._publish_call_event"), patch.object(
            CallScheduler, "start_new_taskrun"
        ):
            card.switch_to_key(self.key_b.pk)

        call.refresh_from_db()
        self.assertEqual(call.status_detail, TaskCallStatusDetail.WAITING_QUEUE)
        self.assertEqual(card.pending_count, 0)

    def test_failover_releases_via_ready_sibling_key(self):
        from runtime.tasks.call_scheduler import CallScheduler

        runtime = self._runtime()
        runtime.set_aimodel(self.model)
        self._adopt(runtime)
        self._cooldown(self.key_a, 3000)
        runtime.set_auto_failover_keys(True)

        call = self._parked_call(runtime.get_version_model())
        with patch("runtime.tasks.call_fsm._publish_call_event"), patch.object(
            CallScheduler, "start_new_taskrun"
        ) as start:
            released = CallScheduler.release_waiting_ratelimit_calls(
                self.session, repoint=True
            )
        self.assertEqual(released, 1)
        call.refresh_from_db()
        self.assertEqual(call.status_detail, TaskCallStatusDetail.WAITING_QUEUE)
        start.assert_called_once_with(call.pk)
        # The session now sticks to the sibling key that unblocked it.
        self.assertEqual(self._runtime().preferred_api_key().pk, self.key_b.pk)

    def test_key_row_statuses_and_strict_wait(self):
        from unittest.mock import patch as freeze_patch

        runtime = self._runtime()
        runtime.set_aimodel(self.model)
        self._adopt(runtime)
        fixed = timezone.now()
        with freeze_patch("django.utils.timezone.now", return_value=fixed):
            ApiKey.objects.filter(pk=self.key_a.pk).update(
                rate_limit_until=fixed + timedelta(seconds=125)
            )

            card = RateLimitCard(subject=runtime, parent=MockParent())
            rows = card._key_rows(self.model)
            current = next(r for r in rows if r["current"])
            self.assertIn("cooling", current["status_text"])
            ready = [r for r in rows if not r["current"]]
            self.assertEqual(len(ready), 1)
            self.assertEqual(ready[0]["status_text"], "ready")

            info = card._blocked_info(self.model)
            self.assertEqual(info["wait_text"], "2m 5s")
            self.assertFalse(info["resuming"])

    def test_auto_failover_wait_reports_resuming_when_ready_key_exists(self):
        runtime = self._runtime()
        runtime.set_aimodel(self.model)
        self._adopt(runtime)
        ApiKey.objects.filter(pk=self.key_a.pk).update(
            rate_limit_until=timezone.now() + timedelta(seconds=125)
        )
        runtime.set_auto_failover_keys(True)

        card = RateLimitCard(subject=runtime, parent=MockParent())
        info = card._blocked_info(self.model)
        self.assertEqual(info["wait_text"], "")
        self.assertTrue(info["resuming"])


class SwitchKeyMovesWholeChainTest(MultiKeySessionTest):
    """Regression: a key switch must re-point the *entire* chain subtree —
    not just the parked call — so ``decide_next_step``'s next ``process_turn``
    still uses the switched key on the following query.
    """

    def _chain(self, session_version):
        """A minimal process_turn chain: root -> [call_llm, decide_next_step]."""
        from server.models.tasks.task_definition import TaskDefinition
        from server.models.tasks.task_definition_version import TaskDefinitionVersion
        from server.models.tasks.task_instance import TaskInstance
        from server.models.enums.task_enums import TaskExecutionMode

        tdv_call = TaskDefinitionVersion.objects.create(
            task_definition=TaskDefinition.objects.create(name="call_llm"),
            description="", function_schema={}, task_type="TASK",
            task_execution_mode=TaskExecutionMode.FUNCTION, requires_approval=False,
        )
        tdv_decide = TaskDefinitionVersion.objects.create(
            task_definition=TaskDefinition.objects.create(name="decide_next_step"),
            description="", function_schema={}, task_type="TASK",
            task_execution_mode=TaskExecutionMode.FUNCTION, requires_approval=False,
        )
        root = TaskInstance.objects.create(
            session=self.session, session_version=session_version,
            requires_approval=False, max_subtask_errors=0, max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=0,
            max_retries=0, retry_delay=0, retry_requires_approval=False,
        )
        call_llm = TaskInstance.objects.create(
            session=self.session, session_version=session_version,
            task_definition_version=tdv_call, requires_approval=False,
            max_subtask_errors=0, max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=0,
            max_retries=0, retry_delay=0, retry_requires_approval=False,
        )
        decide = TaskInstance.objects.create(
            session=self.session, session_version=session_version,
            task_definition_version=tdv_decide, requires_approval=False,
            max_subtask_errors=0, max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=0,
            max_retries=0, retry_delay=0, retry_requires_approval=False,
        )
        root.child_instances.add(call_llm, decide)
        return root, call_llm, decide

    def _parked_call(self, session_version) -> AgentTaskCall:
        return AgentTaskCall.objects.create(
            session=self.session,
            session_version=session_version,
            requires_approval=False,
            max_subtask_errors=0,
            max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=0,
            max_retries=0,
            retry_delay=0,
            retry_requires_approval=False,
            status=TaskCallStatus.WAITING,
            status_detail=TaskCallStatusDetail.WAITING_RATELIMIT,
        )

    def test_repoints_and_releases_whole_chain_to_latest(self):
        from runtime.tasks.call_scheduler import CallScheduler
        from server.models.tasks.agent_task_call import AgentTaskCall

        runtime = self._runtime()
        runtime.set_aimodel(self.model)
        self._adopt(runtime)
        self._cooldown(self.key_a, 3000)
        old_sv = runtime.get_version_model()

        root, call_llm, decide = self._chain(old_sv)
        parked = self._parked_call(old_sv)
        AgentTaskCall.objects.filter(pk=parked.pk).update(task_instance=call_llm)
        parked.refresh_from_db()
        decide_call = AgentTaskCall.objects.create(
            session=self.session,
            session_version=old_sv,
            task_instance=decide,
            requires_approval=False,
            max_subtask_errors=0,
            max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=0,
            max_retries=0,
            retry_delay=0,
            retry_requires_approval=False,
            status=TaskCallStatus.WAITING,
            status_detail=TaskCallStatusDetail.WAITING_DEPENDENCY,
        )

        # Card's "Switch key" action: stick to B, release with repoint.
        runtime.set_preferred_api_key(self.key_b)
        latest = SessionModel.objects.get(pk=self.session.pk).latest_session_version
        with patch("runtime.tasks.call_fsm._publish_call_event"), patch.object(
            CallScheduler, "start_new_taskrun"
        ):
            released = CallScheduler.release_waiting_ratelimit_calls(
                self.session, repoint=True
            )
        self.assertEqual(released, 1)

        # Parked call AND its chain sibling decide_next_step move to latest.
        parked.refresh_from_db()
        decide_call.refresh_from_db()
        decide.refresh_from_db()
        self.assertEqual(parked.session_version_id, latest.pk)
        self.assertEqual(decide_call.session_version_id, latest.pk)
        self.assertEqual(decide.session_version_id, latest.pk)

        # The next query (dispatched by decide_next_step) uses the switched key.
        cont = Session(session_model=self.session, pinned_session_version=latest)
        r = RateLimitChecker.check(self.model, session=cont)
        self.assertEqual(r.selected_key.pk, self.key_b.pk)