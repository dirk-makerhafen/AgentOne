"""Tests for the provider-level and model-level rate-limit gates.

These tiers were silently disabled (``return False, ""``) and their count
helpers used broken ORM joins.  This file proves:

* provider caps (``limit_parallel_calls``, request/token windows) are
  **PER API KEY** — one busy key never blocks a free sibling, and the
  provider is only "rate limited" when *every* enabled key is at its cap;
* the provider parallel census counts ACTIVE queries stamped to that key,
  not AgentTaskRuns, and an in-flight call never counts against itself;
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


# pylint: disable=too-many-instance-attributes, duplicate-code, protected-access
#   setUp fixtures / helper types intentionally mirror sibling tests;
#   tests legitimately stamp the runtime's _current_taskrun to simulate an
#   in-flight run for the self-exclusion regression tests.


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

    def test_provider_parallel_cap_is_per_key(self):
        """Provider parallel caps are PER API KEY: a busy key never blocks a sibling."""
        self.provider.limit_parallel_calls = 1
        self.provider.save()

        # Key A occupies its single parallel slot via a live ACTIVE query.
        sv = self._pinned_to(self.model)
        Query.objects.create(
            session=self.session, session_version=sv, apikey=self.key_a, status="ACTIVE"
        )

        # Key A alone is at its cap...
        limited, reason = self.provider.is_rate_limited(apikey=self.key_a)
        self.assertTrue(limited)
        self.assertEqual(reason, "parallel_calls:1/1")

        # ...but the sibling key still has capacity, so the provider as a whole
        # is NOT limited and the checker routes the next call to key B.
        self.assertFalse(self.provider.is_rate_limited(apikey=self.key_b)[0])
        self.assertFalse(self.provider.is_rate_limited()[0])
        result = RateLimitChecker.check(self.model)
        self.assertIsNotNone(result.selected_key)
        self.assertEqual(result.selected_key.pk, self.key_b.pk)

        # Once key B also fills up, the provider parks the next call.
        Query.objects.create(
            session=self.session, session_version=sv, apikey=self.key_b, status="ACTIVE"
        )
        self.assertTrue(self.provider.is_rate_limited()[0])
        with self.assertRaises(RateLimitError) as ctx:
            RateLimitChecker.check(self.model)
        self.assertIn("provider:parallel_calls", str(ctx.exception))

        # Per-key quotas stay independent: the provider's per-key windows
        # never leak into each key's own is_rate_limited.
        self.assertFalse(self.key_a.is_rate_limited()[0])
        self.assertFalse(self.key_b.is_rate_limited()[0])

        # Once both ACTIVE queries are gone the provider frees up again.
        Query.objects.update(status="SUCCESS")
        self.assertFalse(self.provider.is_rate_limited()[0])
        result = RateLimitChecker.check(self.model)
        self.assertIsNotNone(result.selected_key)

    def test_provider_parallel_cap_does_not_count_self(self):
        """A check from inside an ACTIVE run must not count its own in-flight call.

        ``RateLimitChecker.check`` runs BEFORE ``call_llm`` stamps the query
        with the selected key and flips it to ACTIVE, so the WAITING query
        being admitted never counts against any key — a single LLM call at
        ``limit_parallel_calls=1`` can't lock itself out even though the
        run was already marked ACTIVE.
        """
        self.provider.limit_parallel_calls = 1
        self.provider.save()

        sv = self._pinned_to(self.model)
        runtime = Session(session_model=self.session)
        runtime._current_taskrun = self._active_run(sv)

        result = RateLimitChecker.check(self.model, session=runtime)
        self.assertIsNotNone(result.selected_key)
        chosen = result.selected_key.pk
        self.assertIn(chosen, (self.key_a.pk, self.key_b.pk))

        # Live ACTIVE queries stamped to the chosen key consume its slot:
        # occupying key A forces the next call onto the free key B...
        Query.objects.create(
            session=self.session,
            session_version=sv,
            apikey_id=chosen,
            status="ACTIVE",
        )
        result2 = RateLimitChecker.check(self.model)
        self.assertIsNotNone(result2.selected_key)
        self.assertNotEqual(result2.selected_key.pk, chosen)

        # ...and occupying both keys parks the third call.
        Query.objects.create(
            session=self.session,
            session_version=sv,
            apikey=result2.selected_key,
            status="ACTIVE",
        )
        with self.assertRaises(RateLimitError):
            RateLimitChecker.check(self.model)

    def test_provider_parallel_cap_cares_only_about_its_own_keys(self):
        other = ApiProvider.objects.create(name="gate-p2")
        other_key = ApiKey.objects.create(api_provider=other, key="k-other", enabled=True)
        other_model = AiModel.objects.create(
            api_provider=other, name="Other", provider_model_id="gate-other"
        )

        self.provider.limit_parallel_calls = 1
        self.provider.save()

        # An ACTIVE query on the *other* provider's key must not trip this cap.
        Query.objects.create(
            session=self.session,
            session_version=self._pinned_to(other_model),
            apikey=other_key,
            status="ACTIVE",
        )
        result = RateLimitChecker.check(self.model)
        self.assertIsNotNone(result.selected_key)
        self.assertEqual(result.selected_key.api_provider_id, self.provider.pk)

    # ------------------------------------------------------------------ rpm

    def test_provider_request_cap_is_per_key(self):
        """Provider request windows are per key, scoped via ``query__apikey``."""
        self.provider.limit_request_per_minute = 1
        self.provider.save()
        sv = self._pinned_to(self.model)

        query_a = Query.objects.create(
            session=self.session, session_version=sv, apikey=self.key_a, status="SUCCESS"
        )
        Response.objects.create(
            query=query_a,
            session=self.session,
            session_version=sv,
            aimodel=self.model,
            status="SUCCESS",
        )

        # Key A has used its only request this minute...
        limited, reason = self.provider.is_rate_limited(apikey=self.key_a)
        self.assertTrue(limited)
        self.assertEqual(reason, "rpm:1/1")

        # ...but key B has not, so the provider stays open and the checker
        # routes the call to key B.
        self.assertFalse(self.provider.is_rate_limited(apikey=self.key_b)[0])
        self.assertFalse(self.provider.is_rate_limited()[0])
        result = RateLimitChecker.check(self.model)
        self.assertEqual(result.selected_key.pk, self.key_b.pk)

        # Key B burning its own request parks the next call.
        query_b = Query.objects.create(
            session=self.session, session_version=sv, apikey=self.key_b, status="SUCCESS"
        )
        Response.objects.create(
            query=query_b,
            session=self.session,
            session_version=sv,
            aimodel=self.model,
            status="SUCCESS",
        )
        self.assertTrue(self.provider.is_rate_limited()[0])
        with self.assertRaises(RateLimitError) as ctx:
            RateLimitChecker.check(self.model)
        self.assertIn("provider:rpm", str(ctx.exception))

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

    def test_model_parallel_cap_does_not_count_self(self):
        self.model_a.limit_parallel_calls = 1
        self.model_a.save()

        sv = self._pinned_to(self.model_a)
        run = self._active_run(sv)

        runtime = Session(session_model=self.session)
        runtime._current_taskrun = run
        self.assertFalse(self.model_a.is_rate_limited(exclude_taskrun_id=run.pk)[0])
        result = RateLimitChecker.check(self.model_a, session=runtime)
        self.assertIsNotNone(result.selected_key)

        # A different ACTIVE run on the same model still trips the cap.
        runtime2 = Session(session_model=self.session)
        runtime2._current_taskrun = self._active_run(sv)
        with self.assertRaises(RateLimitError) as ctx:
            RateLimitChecker.check(self.model_a, session=runtime2)
        self.assertIn("model:parallel_calls", str(ctx.exception))

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
