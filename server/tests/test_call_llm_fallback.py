"""Tests for the provider-fallback path in ``call_llm`` and the
``sibling_aimodels`` helper it relies on.

``call_llm`` is loaded by path (like the routing test) so its module globals
(``run_streaming_query``, ``RateLimitChecker``, ``Query``) can be patched
without touching the real network or DB round-trips.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase

from runtime.rate_limiter import RateLimitError, RateLimitResult
from runtime.session.aimodel_picker import sibling_aimodels
from server.models.providers.api_key import ApiKey
from server.models.providers.api_provider import ApiProvider
from server.models.providers.ai_model import AiModel
from server.models.queries.query import QueryStatus
from server.models.queries.response import ResponseStatus

# pylint: disable=protected-access  # exercising internal helpers

CALL_LLM_PATH = (Path(__file__).resolve().parent.parent.parent / ".agentone" / "scripts" / "core" / "call_llm.py")


def _load_call_llm():
    spec = importlib.util.spec_from_file_location("agentone_call_llm_fallback_under_test", CALL_LLM_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _StubSession:
    """Minimal session stand-in that records re-pins."""

    def __init__(self, aimodel=None):
        self.aimodel = aimodel
        self.repinned = []

    def set_aimodel(self, model):
        self.repinned.append(model)
        self.aimodel = model


class SiblingAimodelsTest(TestCase):
    def setUp(self):
        self.p1 = ApiProvider.objects.create(name="p1")
        self.p2 = ApiProvider.objects.create(name="p2")
        ApiKey.objects.create(api_provider=self.p1, key="k1", enabled=True)
        ApiKey.objects.create(api_provider=self.p2, key="k2", enabled=True)
        self.alpha_p1 = AiModel.objects.create(api_provider=self.p1, name="Alpha", provider_model_id="sql-alpha")
        self.alpha_p2 = AiModel.objects.create(api_provider=self.p2, name="Alpha", provider_model_id="apisql-alpha")
        self.beta = AiModel.objects.create(api_provider=self.p1, name="Beta", provider_model_id="beta")

    def test_returns_other_provider_serving_same_name(self):
        siblings = sibling_aimodels(self.alpha_p1)
        self.assertEqual(siblings, [self.alpha_p2])

    def test_single_provider_model_has_no_siblings(self):
        self.assertEqual(sibling_aimodels(self.beta), [])

    def test_exclude_skips_previously_tried(self):
        self.assertEqual(sibling_aimodels(self.alpha_p1, exclude=[self.alpha_p2.pk]), [])

    def test_orders_least_loaded_first(self):
        with mock.patch.object(self.p1, "requests_last_minute", return_value=0), mock.patch.object(
            self.p2, "requests_last_minute", return_value=5
        ):
            # p1 (load 0) must be preferred before p2 (load 5).
            self.assertEqual(sibling_aimodels(self.alpha_p2), [self.alpha_p1])


class FallbackLoopTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.call_llm = _load_call_llm()

    def setUp(self):
        self.p1 = ApiProvider.objects.create(name="p1")
        self.p2 = ApiProvider.objects.create(name="p2")
        ApiKey.objects.create(api_provider=self.p1, key="k1", enabled=True)
        ApiKey.objects.create(api_provider=self.p2, key="k2", enabled=True)
        self.alpha_p1 = AiModel.objects.create(api_provider=self.p1, name="Alpha", provider_model_id="sql-alpha")
        self.alpha_p2 = AiModel.objects.create(api_provider=self.p2, name="Alpha", provider_model_id="apisql-alpha")

    def _stub_query(self):
        return SimpleNamespace(
            pk=1,
            apikey=None,
            status=QueryStatus.WAITING,
            session_version=None,
            refresh_from_db=lambda: None,
        )

    def _ok(self):
        return SimpleNamespace(status=ResponseStatus.SUCCESS)

    def test_falls_back_to_sibling_and_repins(self):
        response = self._ok()
        with mock.patch.object(self.call_llm, "RateLimitChecker") as checker, mock.patch.object(
            self.call_llm, "Query"
        ) as query_model:
            checker.check.return_value = RateLimitResult(selected_key=None)
            query_model.objects.filter.return_value.update.return_value = 1
            module = self.call_llm
            with mock.patch.object(module, "run_streaming_query", side_effect=[RuntimeError("boom"), response]) as stream:
                session = _StubSession(aimodel=self.alpha_p1)
                result = module._call_with_fallback(
                    session=session, query=self._stub_query(), messages=[], tools=[]
                )
        self.assertIs(result, response)
        self.assertEqual(stream.call_count, 2)
        self.assertEqual(stream.call_args_list[0].kwargs["aimodel"], self.alpha_p1)
        self.assertEqual(stream.call_args_list[1].kwargs["aimodel"], self.alpha_p2)
        # Session re-pinned to the working provider.
        self.assertEqual(session.aimodel, self.alpha_p2)
        self.assertEqual(session.repinned, [self.alpha_p2])
        # Query rows got the ACTIVE + ACTIVE(force) + SUCCESS transitions.
        self.assertEqual(query_model.objects.filter.return_value.update.call_count, 3)

    def test_mid_stream_failure_propagates_without_retry(self):
        partial = RuntimeError("connection reset after start")
        partial.streamed_content = "partial output"
        with mock.patch.object(self.call_llm, "RateLimitChecker") as checker, mock.patch.object(
            self.call_llm, "Query"
        ):
            checker.check.return_value = RateLimitResult(selected_key=None)
            with mock.patch.object(self.call_llm, "run_streaming_query", side_effect=partial) as stream:
                session = _StubSession(aimodel=self.alpha_p1)
                with self.assertRaises(RuntimeError):
                    self.call_llm._call_with_fallback(session=session, query=self._stub_query(), messages=[], tools=[])
        self.assertEqual(stream.call_count, 1)
        self.assertEqual(session.repinned, [])

    def test_rate_limited_pinned_skips_to_working_sibling(self):
        response = self._ok()
        with mock.patch.object(self.call_llm, "RateLimitChecker") as checker, mock.patch.object(
            self.call_llm, "Query"
        ):
            checker.check.side_effect = [
                RateLimitError("provider:over_cap"),
                RateLimitResult(selected_key=None),
            ]
            with mock.patch.object(self.call_llm, "run_streaming_query", return_value=response):
                session = _StubSession(aimodel=self.alpha_p1)
                result = self.call_llm._call_with_fallback(
                    session=session, query=self._stub_query(), messages=[], tools=[]
                )
        self.assertIs(result, response)
        self.assertEqual(session.aimodel, self.alpha_p2)

    def test_all_rate_limited_parks_on_rate_limit_error(self):
        with mock.patch.object(self.call_llm, "RateLimitChecker") as checker, mock.patch.object(
            self.call_llm, "Query"
        ):
            checker.check.side_effect = [
                RateLimitError("provider:over_cap"),
                RateLimitError("provider:over_cap"),
            ]
            with mock.patch.object(self.call_llm, "run_streaming_query") as stream:
                session = _StubSession(aimodel=self.alpha_p1)
                with self.assertRaises(RateLimitError):
                    self.call_llm._call_with_fallback(
                        session=session, query=self._stub_query(), messages=[], tools=[]
                    )
        self.assertEqual(stream.call_count, 0)
        self.assertEqual(session.repinned, [])