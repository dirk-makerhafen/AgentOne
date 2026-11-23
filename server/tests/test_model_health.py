"""Tests for the observed model/key/provider health layer.

Covers the error classifier, the persisted status transitions, picker
filtering, and the call_llm wiring that records failures on the Response.
"""
from __future__ import annotations

import importlib.util
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from runtime.llm_errors import (
    ModelUnavailableError,
    classify_llm_error,
    extract_retry_after_seconds,
)
from runtime.rate_limiter import RateLimitChecker, RateLimitResult
from runtime.session.aimodel_picker import (
    model_groups,
    pick_aimodel,
    selectable_aimodels,
    sibling_aimodels,
)
from server.models.enums.provider_enums import HealthStatus
from server.models.providers.ai_model_offering import AiModelOffering as AiModel
from server.models.providers.api_key import ApiKey
from server.models.providers.api_provider import ApiProvider
from server.models.queries.query import QueryStatus
from server.models.queries.response import ResponseStatus

CALL_LLM_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / ".agentone" / "scripts" / "core" / "call_llm.py"
)
CALL_LLM_DIRECT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / ".agentone" / "scripts" / "subagents" / "call_llm_direct.py"
)


def _load_call_llm():
    spec = importlib.util.spec_from_file_location(
        "agentone_call_llm_health_under_test", CALL_LLM_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_call_llm_direct():
    spec = importlib.util.spec_from_file_location(
        "agentone_call_llm_direct_health_under_test", CALL_LLM_DIRECT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _StubSession:
    def __init__(self, aimodel=None):
        self.aimodel = aimodel
        self.repinned = []

    def set_aimodel(self, model):
        self.repinned.append(model)
        self.aimodel = model


class _StubQuery(SimpleNamespace):
    """Query stand-in supporting the instance-level ``atomic_update`` path."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.updates: list[dict] = []

    def atomic_update(self, **fields):
        self.updates.append(fields)
        return 1


class LLMErrorClassificationTest(TestCase):
    def test_model_not_found_is_sticky_model_scope(self):
        from litellm.exceptions import NotFoundError

        info = classify_llm_error(
            NotFoundError(message="model not found", model="x", llm_provider="openai")
        )
        self.assertEqual(info.kind, "model_not_found")
        self.assertEqual(info.scope, "model")
        self.assertEqual(info.health_status, HealthStatus.UNAVAILABLE)
        self.assertTrue(info.sticky)

    def test_auth_is_sticky_key_scope(self):
        from litellm.exceptions import AuthenticationError

        info = classify_llm_error(
            AuthenticationError(message="bad key", model="x", llm_provider="openai")
        )
        self.assertEqual(info.kind, "auth")
        self.assertEqual(info.scope, "key")
        self.assertEqual(info.health_status, HealthStatus.AUTH_ERROR)
        self.assertTrue(info.sticky)

    def test_rate_limit_is_key_scope_and_transient(self):
        from litellm.exceptions import RateLimitError

        info = classify_llm_error(
            RateLimitError(message="slow down", model="x", llm_provider="openai")
        )
        self.assertEqual(info.kind, "rate_limit")
        self.assertEqual(info.scope, "key")
        self.assertFalse(info.sticky)

    def test_context_length_bad_request_does_not_poison_model(self):
        from litellm.exceptions import BadRequestError

        info = classify_llm_error(
            BadRequestError(
                message="This model's maximum context length is 8192 tokens",
                model="x",
                llm_provider="openai",
            )
        )
        self.assertEqual(info.kind, "bad_request")
        self.assertEqual(info.scope, "request")
        self.assertEqual(info.health_status, "")

    def test_unsupported_model_bad_request_is_config_error(self):
        from litellm.exceptions import BadRequestError

        info = classify_llm_error(
            BadRequestError(
                message="This model does not support tool calls",
                model="x",
                llm_provider="openai",
            )
        )
        self.assertEqual(info.kind, "bad_request")
        self.assertEqual(info.health_status, HealthStatus.CONFIG_ERROR)
        self.assertTrue(info.config_like)

    def test_server_error_is_degraded_model_scope(self):
        from litellm.exceptions import InternalServerError

        info = classify_llm_error(
            InternalServerError(message="boom", model="x", llm_provider="openai")
        )
        self.assertEqual(info.kind, "server")
        self.assertEqual(info.scope, "model")
        self.assertEqual(info.health_status, HealthStatus.DEGRADED)

    def test_retry_after_header_is_extracted(self):
        exc = SimpleNamespace(
            message="rate limited",
            response=SimpleNamespace(headers={"retry-after": "42"}),
        )
        self.assertEqual(extract_retry_after_seconds(exc), 42.0)


class HealthMixinTest(TestCase):
    def setUp(self):
        self.provider = ApiProvider.objects.create(name="p1")
        self.model = AiModel.objects.create(
            api_provider=self.provider, name="Alpha", provider_model_id="alpha"
        )

    def test_unavailable_blocks_until_cleared(self):
        self.model.record_health_error(
            HealthStatus.UNAVAILABLE, "404", sticky=True
        )
        self.model.refresh_from_db()
        self.assertTrue(self.model.health_blocks_calls())
        self.model.clear_health()
        self.assertFalse(self.model.health_blocks_calls())

    def test_degraded_blocks_until_retry_at(self):
        self.model.record_health_error(
            HealthStatus.DEGRADED, "timeout", retry_after_seconds=60
        )
        self.model.refresh_from_db()
        self.assertTrue(self.model.health_blocks_calls())
        AiModel.objects.filter(pk=self.model.pk).update(
            status_retry_at=timezone.now() - timedelta(seconds=1)
        )
        self.model.refresh_from_db()
        self.assertFalse(self.model.health_blocks_calls())

    def test_success_clears_failure(self):
        self.model.record_health_error(
            HealthStatus.DEGRADED, "timeout", retry_after_seconds=60
        )
        self.model.record_health_success()
        self.model.refresh_from_db()
        self.assertEqual(self.model.status, HealthStatus.HEALTHY)
        self.assertEqual(self.model.consecutive_failures, 0)
        self.assertFalse(self.model.health_blocks_calls())

    def test_health_labels(self):
        self.assertEqual(self.model.health_label, "")
        self.model.status = HealthStatus.UNAVAILABLE
        self.assertEqual(self.model.health_label, "unavailable")
        self.model.status = HealthStatus.RATE_LIMITED
        self.assertEqual(self.model.health_label, "rate limited")
        self.model.status = HealthStatus.AUTH_ERROR
        self.assertEqual(self.model.health_label, "auth error")

    def test_temporary_label_expires_with_retry_window(self):
        self.model.record_health_error(
            HealthStatus.DEGRADED, "timeout", retry_after_seconds=60
        )
        self.assertEqual(self.model.health_label, "degraded")
        self.model.status_retry_at = timezone.now() - timedelta(seconds=1)
        self.assertEqual(self.model.health_label, "")


class PickerHealthTest(TestCase):
    def setUp(self):
        self.p1 = ApiProvider.objects.create(name="p1")
        self.p2 = ApiProvider.objects.create(name="p2")
        ApiKey.objects.create(api_provider=self.p1, key="k1", enabled=True)
        ApiKey.objects.create(api_provider=self.p2, key="k2", enabled=True)
        self.alpha_p1 = AiModel.objects.create(
            api_provider=self.p1, name="Alpha", provider_model_id="a1"
        )
        self.alpha_p2 = AiModel.objects.create(
            api_provider=self.p2, name="Alpha", provider_model_id="a2"
        )

    def test_unavailable_member_is_not_selectable(self):
        self.alpha_p1.record_health_error(
            HealthStatus.UNAVAILABLE, "404", sticky=True
        )
        selectable = {m.pk for m in selectable_aimodels()}
        self.assertNotIn(self.alpha_p1.pk, selectable)
        self.assertIn(self.alpha_p2.pk, selectable)

    def test_pick_prefers_healthy_sibling(self):
        self.alpha_p1.record_health_error(
            HealthStatus.UNAVAILABLE, "404", sticky=True
        )
        for _ in range(5):
            self.assertEqual(pick_aimodel("Alpha"), self.alpha_p2)

    def test_all_blocked_returns_none(self):
        self.alpha_p1.record_health_error(HealthStatus.UNAVAILABLE, "404", sticky=True)
        self.alpha_p2.record_health_error(HealthStatus.UNAVAILABLE, "404", sticky=True)
        self.assertIsNone(pick_aimodel("Alpha"))

    def test_sibling_list_excludes_blocked(self):
        self.alpha_p1.record_health_error(
            HealthStatus.AUTH_ERROR, "401", sticky=True
        )
        self.assertEqual(sibling_aimodels(self.alpha_p2), [])

    def test_group_hidden_when_all_members_blocked(self):
        self.assertIn("Alpha", {g.name for g in model_groups()})
        self.alpha_p1.record_health_error(
            HealthStatus.UNAVAILABLE, "404", sticky=True
        )
        self.alpha_p2.record_health_error(
            HealthStatus.UNAVAILABLE, "404", sticky=True
        )
        self.assertNotIn("Alpha", {g.name for g in model_groups()})


class RateLimiterHealthTest(TestCase):
    def setUp(self):
        self.provider = ApiProvider.objects.create(name="p1")
        self.key = ApiKey.objects.create(
            api_provider=self.provider, key="k1", enabled=True
        )
        self.model = AiModel.objects.create(
            api_provider=self.provider, name="Alpha", provider_model_id="alpha"
        )

    def test_unavailable_model_raises_model_unavailable(self):
        self.model.record_health_error(
            HealthStatus.UNAVAILABLE, "404", sticky=True
        )
        with self.assertRaises(ModelUnavailableError):
            RateLimitChecker.check(self.model)

    def test_all_keys_auth_failed_raises_model_unavailable(self):
        self.key.record_health_error(
            HealthStatus.AUTH_ERROR, "401", sticky=True
        )
        self.model.refresh_from_db()
        self.assertEqual(self.model.status, HealthStatus.UNKNOWN)
        with self.assertRaises(ModelUnavailableError):
            RateLimitChecker.check(self.model)

    def test_one_good_key_keeps_provider_usable(self):
        self.key.record_health_error(
            HealthStatus.AUTH_ERROR, "401", sticky=True
        )
        ApiKey.objects.create(
            api_provider=self.provider, key="k2", enabled=True
        )
        result = RateLimitChecker.check(self.model)
        self.assertIsNotNone(result.selected_key)
        self.assertNotEqual(result.selected_key.pk, self.key.pk)

    def test_new_key_unblocks_stale_provider_auth_error(self):
        """A rotated key makes the provider usable without a manual clear."""
        self.key.record_health_error(
            HealthStatus.AUTH_ERROR, "401", sticky=True
        )
        self.provider.record_health_error(
            HealthStatus.AUTH_ERROR, "401", sticky=True
        )
        self.assertTrue(self.provider.is_rate_limited()[0])

        ApiKey.objects.create(
            api_provider=self.provider, key="k2", enabled=True
        )
        self.provider.refresh_from_db()
        # Adding a key invalidates the provider-wide auth verdict immediately.
        self.assertEqual(self.provider.status, HealthStatus.UNKNOWN)
        self.assertFalse(self.provider.is_rate_limited()[0])
        result = RateLimitChecker.check(self.model)
        self.assertIsNotNone(result.selected_key)
        self.assertNotEqual(result.selected_key.pk, self.key.pk)


class DirectProbeTest(TestCase):
    """The UI "Test" action must be able to re-probe a blocked row."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.call_llm_direct = _load_call_llm_direct()

    def setUp(self):
        self.provider = ApiProvider.objects.create(name="p1")
        self.model = AiModel.objects.create(
            api_provider=self.provider, name="Alpha", provider_model_id="alpha"
        )

    def test_unknown_model_id_does_not_fall_back(self):
        self.assertIsNone(
            self.call_llm_direct._resolve_aimodel("Alpha", model_id=999_999)
        )

    def test_model_id_probe_clears_health_but_keeps_cooldown(self):
        auth_key = ApiKey.objects.create(
            api_provider=self.provider, key="auth", enabled=True
        )
        cooling_key = ApiKey.objects.create(
            api_provider=self.provider, key="cooling", enabled=True
        )
        self.model.record_health_error(
            HealthStatus.UNAVAILABLE, "404", sticky=True
        )
        self.provider.record_health_error(
            HealthStatus.AUTH_ERROR, "401", sticky=True
        )
        auth_key.record_health_error(HealthStatus.AUTH_ERROR, "401", sticky=True)
        cooling_key.record_provider_cooldown(300, reason="429")

        model = self.call_llm_direct._resolve_aimodel(None, model_id=self.model.pk)

        self.assertEqual(model.pk, self.model.pk)
        self.model.refresh_from_db()
        self.provider.refresh_from_db()
        auth_key.refresh_from_db()
        cooling_key.refresh_from_db()
        self.assertEqual(self.model.status, HealthStatus.UNKNOWN)
        self.assertEqual(self.provider.status, HealthStatus.UNKNOWN)
        self.assertEqual(auth_key.status, HealthStatus.UNKNOWN)
        # Rate-limit cooldown and its derived status survive the probe.
        self.assertEqual(cooling_key.status, HealthStatus.RATE_LIMITED)
        self.assertIsNotNone(cooling_key.rate_limit_until)


class _StubResponse:
    def __init__(self):
        self.pk = 1
        self.status = ResponseStatus.ACTIVE
        self.content = ""
        self.reasoning = ""
        self.tool_calls = []
        self.completion_tokens = 0
        self.prompt_tokens = 0
        self.cached_tokens = 0
        self.reasoning_tokens = 0
        self.finish_reason = ""
        self.time_to_first_token = 0
        self.token_generation_time = 0
        self.reasoning_time = 0
        self.total_time = 0
        self.error_type = ""
        self.error_message = ""

    def save(self):
        pass


class StreamingHealthTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.call_llm = _load_call_llm()

    def setUp(self):
        self.provider = ApiProvider.objects.create(name="p1")
        self.key = ApiKey.objects.create(
            api_provider=self.provider, key="k1", enabled=True
        )
        self.model = AiModel.objects.create(
            api_provider=self.provider, name="Alpha", provider_model_id="alpha"
        )
        self.query = SimpleNamespace(
            pk=1,
            apikey=self.key,
            status=QueryStatus.ACTIVE,
            session_version=SimpleNamespace(session=SimpleNamespace()),
            refresh_from_db=lambda: None,
        )

    def test_404_marks_model_unavailable_and_records_response_error(self):
        from litellm.exceptions import NotFoundError

        resp = _StubResponse()
        error = NotFoundError(
            message="The requested model 'alpha' does not exist.",
            model="alpha",
            llm_provider="openai",
        )
        with mock.patch(
            "server.models.queries.response.Response.objects.create",
            return_value=resp,
        ), mock.patch.object(self.call_llm.litellm, "completion", side_effect=error):
            with self.assertRaises(NotFoundError):
                self.call_llm.run_streaming_query(
                    session=_StubSession(aimodel=self.model),
                    tools=[],
                    messages=[],
                    query=self.query,
                )
        self.assertEqual(resp.status, ResponseStatus.FAILURE)
        self.assertEqual(resp.error_type, "model_not_found")
        self.assertIn("does not exist", resp.error_message)
        self.model.refresh_from_db()
        self.assertEqual(self.model.status, HealthStatus.UNAVAILABLE)
        self.assertTrue(self.model.health_blocks_calls())

    def test_success_clears_previous_failure(self):
        self.model.record_health_error(
            HealthStatus.DEGRADED, "timeout", retry_after_seconds=60
        )

        class _Event:
            def __init__(self, delta=None, finish=None):
                self._data = {
                    "choices": [{"delta": delta or {}, "finish_reason": finish}],
                }

            def model_dump(self):
                return self._data

        class _Stream:
            def __init__(self, events):
                self._events = events

            def __iter__(self):
                return iter(self._events)

        events = [
            _Event(delta={"content": "hello"}),
            _Event(finish="stop"),
        ]
        resp = _StubResponse()
        with mock.patch(
            "server.models.queries.response.Response.objects.create",
            return_value=resp,
        ), mock.patch.object(
            self.call_llm.litellm, "completion", return_value=_Stream(events)
        ):
            self.call_llm.run_streaming_query(
                session=_StubSession(aimodel=self.model),
                tools=[],
                messages=[],
                query=self.query,
            )
        self.model.refresh_from_db()
        self.assertEqual(self.model.status, HealthStatus.HEALTHY)


class FallbackDemotionTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.call_llm = _load_call_llm()

    def setUp(self):
        self.p1 = ApiProvider.objects.create(name="p1")
        self.p2 = ApiProvider.objects.create(name="p2")
        ApiKey.objects.create(api_provider=self.p1, key="k1", enabled=True)
        ApiKey.objects.create(api_provider=self.p2, key="k2", enabled=True)
        self.alpha_p1 = AiModel.objects.create(
            api_provider=self.p1, name="Alpha", provider_model_id="a1"
        )
        self.alpha_p2 = AiModel.objects.create(
            api_provider=self.p2, name="Alpha", provider_model_id="a2"
        )
        self.alpha_p1.record_health_error(
            HealthStatus.UNAVAILABLE, "404", sticky=True
        )

    def test_blocked_pinned_model_is_demoted_to_sibling(self):
        response = SimpleNamespace(status=ResponseStatus.SUCCESS)
        query = _StubQuery(
            pk=1,
            apikey=ApiKey.objects.get(api_provider=self.p1),
            status=QueryStatus.WAITING,
            refresh_from_db=lambda: None,
        )
        session = _StubSession(aimodel=self.alpha_p1)
        with mock.patch.object(self.call_llm, "RateLimitChecker") as checker, mock.patch.object(
            self.call_llm, "Query"
        ) as query_model, mock.patch.object(
            self.call_llm, "run_streaming_query", return_value=response
        ) as stream:
            checker.check.return_value = RateLimitResult(selected_key=None)
            query_model.objects.filter.return_value.update.return_value = 1
            result = self.call_llm._call_with_fallback(
                session=session, query=query, messages=[], tools=[]
            )
        self.assertIs(result, response)
        self.assertEqual(stream.call_args.kwargs["aimodel"], self.alpha_p2)
        self.assertEqual(session.aimodel, self.alpha_p2)
