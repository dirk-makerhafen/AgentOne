"""Tests for the provider-level and model-level rate-limit gates.

These tiers were silently disabled (``return False, ""``) and their count
helpers used broken ORM joins.  This file proves:

* a provider-wide cap (``limit_parallel_calls``) blocks *every* key of that
  provider, while each key's own quota/cooldown state stays independent;
* the provider parallel cap counts only that provider's active runs;
* a model-level cap blocks only that model, not siblings on the same provider.
"""
from __future__ import annotations

from django.test import TestCase

from runtime.session.session import Session
from runtime.rate_limiter import RateLimitChecker, RateLimitError

from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.enums.task_enums import TaskRunStatus
from server.models.providers.api_key import ApiKey
from server.models.providers.api_provider import ApiProvider
from server.models.providers.ai_model import AiModel
from server.models.queries.query import Query
from server.models.queries.response import Response
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_run import AgentTaskRun


# pylint: disable=too-many-instance-attributes, duplicate-code
#   setUp fixtures / helper types intentionally mirror sibling tests.


class ProviderGateTest(TestCase):
    """Fixtures: one provider, two keys, one model, one idle agent/session."""

    def setUp(self):
        self.provider = ApiProvider.objects.create(name="gate-p1")
        self.key_a = ApiKey.objects.create(
            api_provider=self.provider, key="k1", enabled=True
        )
        self.key_b = ApiKey.objects.create(
            api_provider=self.provider, key="k2", enabled=True
        )
        self.model = AiModel.objects.create(
            api_provider=self.provider, name="Alpha", provider_model_id="gate-alpha"
        )
        self.agent = AgentModel.objects.create(name="gate-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent,
            agent_settings=SettingsModel.objects.create(),
        )
        self.session = SessionModel.objects.create(name="gate-session")
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

    def _pinned_to(self, model: AiModel) -> SessionVersionModel:
        """A session version whose settings pin *model* (copy-on-write)."""
        runtime = Session(session_model=self.session)
        runtime.set_aimodel(model)
        return runtime.get_version_model()

    def _active_run(self, session_version: SessionVersionModel) -> AgentTaskRun:
        call = AgentTaskCall.objects.create(
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
        )
        return AgentTaskRun.objects.create(
            agent_task_call=call,
            session=self.session,
            session_version=session_version,
            requires_approval=False,
            max_subtask_errors=0,
            max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=0,
            status=TaskRunStatus.ACTIVE,
        )

    # ---------------------------------------------------------------- parallel

    def test_provider_parallel_cap_blocks_all_provider_keys(self):
        self.provider.limit_parallel_calls = 1
        self.provider.save()

        self.assertTrue(self.provider.active_call_count() == 0)
        self.assertFalse(self.provider.is_rate_limited()[0])

        run = self._active_run(self._pinned_to(self.model))

        self.assertEqual(self.provider.active_call_count(), 1)
        limited, reason = self.provider.is_rate_limited()
        self.assertTrue(limited)
        self.assertEqual(reason, "parallel_calls:1/1")

        # The gate trips regardless of which key selection would reach — even
        # with both keys healthy, the checker raises at the provider tier.
        for runtime in (None, Session(session_model=self.session)):
            with self.assertRaises(RateLimitError) as ctx:
                RateLimitChecker.check(self.model, session=runtime)
            self.assertIn("provider:parallel_calls", str(ctx.exception))

        # Per-key quotas stay independent: the provider cap does not leak into
        # each key's own is_rate_limited.
        self.assertFalse(self.key_a.is_rate_limited()[0])
        self.assertFalse(self.key_b.is_rate_limited()[0])

        # Once the run is no longer ACTIVE the provider frees up.
        AgentTaskRun.objects.filter(pk=run.pk).update(status=TaskRunStatus.SUCCESS)
        self.assertFalse(self.provider.is_rate_limited()[0])
        result = RateLimitChecker.check(self.model)
        self.assertIsNotNone(result.selected_key)

    def test_provider_parallel_cap_cares_only_about_its_own_runs(self):
        other = ApiProvider.objects.create(name="gate-p2")
        ApiKey.objects.create(api_provider=other, key="k-other", enabled=True)
        other_model = AiModel.objects.create(
            api_provider=other, name="Other", provider_model_id="gate-other"
        )

        self.provider.limit_parallel_calls = 1
        self.provider.save()

        # An ACTIVE run on *another* provider must not trip this cap.
        self._active_run(self._pinned_to(other_model))
        self.assertEqual(self.provider.active_call_count(), 0)
        self.assertFalse(self.provider.is_rate_limited()[0])

    # ------------------------------------------------------------------ rpm

    def test_provider_request_cap_blocks_all_keys(self):
        self.provider.limit_request_per_minute = 1
        self.provider.save()
        sv = self._pinned_to(self.model)
        Response.objects.create(
            session=self.session,
            session_version=sv,
            aimodel=self.model,
            status="SUCCESS",
        )

        limited, reason = self.provider.is_rate_limited()
        self.assertTrue(limited)
        self.assertEqual(reason, "rpm:1/1")

        for runtime in (None, Session(session_model=self.session)):
            with self.assertRaises(RateLimitError) as ctx:
                RateLimitChecker.check(self.model, session=runtime)
            self.assertIn("provider:rpm", str(ctx.exception))

        # Keys unaffected individually while the provider is at its cap.
        self.assertFalse(self.key_a.is_rate_limited()[0])
        self.assertFalse(self.key_b.is_rate_limited()[0])

    # ---------------------------------------------------------------- key-load

    def test_key_active_call_count_counts_its_own_active_queries(self):
        sv = self._pinned_to(self.model)
        Query.objects.create(
            session=self.session, session_version=sv, apikey=self.key_b, status="ACTIVE"
        )
        self.assertEqual(self.key_a.active_call_count(), 0)
        self.assertEqual(self.key_b.active_call_count(), 1)


class ModelGateTest(TestCase):
    """Model-level caps are independent of provider caps and sibling models."""

    def setUp(self):
        self.provider = ApiProvider.objects.create(name="model-gate-p1")
        ApiKey.objects.create(api_provider=self.provider, key="k1", enabled=True)
        self.model_a = AiModel.objects.create(
            api_provider=self.provider, name="Alpha", provider_model_id="mg-alpha"
        )
        self.model_b = AiModel.objects.create(
            api_provider=self.provider, name="Beta", provider_model_id="mg-beta"
        )
        self.agent = AgentModel.objects.create(name="model-gate-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent,
            agent_settings=SettingsModel.objects.create(),
        )
        self.session = SessionModel.objects.create(name="model-gate-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session,
            agent=self.agent,
            pinned_agent_version=self.av,
        )
        SessionModel.objects.filter(pk=self.session.pk).update(
            latest_session_version=self.sv
        )
        self.session.refresh_from_db()

    def _pinned_to(self, model: AiModel) -> SessionVersionModel:
        runtime = Session(session_model=self.session)
        runtime.set_aimodel(model)
        return runtime.get_version_model()

    def _active_run(self, session_version: SessionVersionModel) -> AgentTaskRun:
        call = AgentTaskCall.objects.create(
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
        )
        return AgentTaskRun.objects.create(
            agent_task_call=call,
            session=self.session,
            session_version=session_version,
            requires_approval=False,
            max_subtask_errors=0,
            max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=0,
            status=TaskRunStatus.ACTIVE,
        )

    def test_model_parallel_cap_blocks_only_that_model(self):
        self.model_a.limit_parallel_calls = 1
        self.model_a.save()
        self._active_run(self._pinned_to(self.model_a))

        limited, reason = self.model_a.is_rate_limited()
        self.assertTrue(limited)
        self.assertEqual(reason, "parallel_calls:1/1")

        # Provider and sibling model are unaffected.
        self.assertFalse(self.provider.is_rate_limited()[0])
        self.assertFalse(self.model_b.is_rate_limited()[0])

        with self.assertRaises(RateLimitError) as ctx:
            RateLimitChecker.check(self.model_a)
        self.assertIn("model:parallel_calls", str(ctx.exception))

        # The sibling still dispatches and picks the shared healthy key.
        result = RateLimitChecker.check(self.model_b)
        self.assertIsNotNone(result.selected_key)

    def test_model_request_cap_blocks_only_that_model(self):
        self.model_a.limit_request_per_minute = 1
        self.model_a.save()
        sv = self._pinned_to(self.model_a)
        Response.objects.create(
            session=self.session,
            session_version=sv,
            aimodel=self.model_a,
            status="SUCCESS",
        )

        limited, reason = self.model_a.is_rate_limited()
        self.assertTrue(limited)
        self.assertEqual(reason, "rpm:1/1")
        self.assertFalse(self.model_b.is_rate_limited()[0])
        self.assertFalse(self.provider.is_rate_limited()[0])
