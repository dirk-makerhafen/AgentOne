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


class ApiKeyCooldownTest(TestCase):
    """Provider-provided cooldown on the API key gates key selection."""

    def setUp(self):
        self.p1 = ApiProvider.objects.create(name="p1")
        self.key = ApiKey.objects.create(api_provider=self.p1, key="k1", enabled=True)

    def test_is_rate_limited_until_cooldown_passes(self):
        from django.utils import timezone
        from datetime import timedelta

        self.key.record_provider_cooldown(120)
        self.key.refresh_from_db()
        limited, reason = self.key.is_rate_limited()
        self.assertTrue(limited)
        self.assertIn("cooldown_until", reason)
        # Cooldown window covers the asked delay.
        self.assertGreater(self.key.rate_limit_until, timezone.now() - timedelta(seconds=100))

    def test_cooldown_expires(self):
        from django.utils import timezone
        from datetime import timedelta

        ApiKey.objects.filter(pk=self.key.pk).update(
            rate_limit_until=timezone.now() - timedelta(seconds=1)
        )
        self.key.refresh_from_db()
        self.assertFalse(self.key.is_rate_limited()[0])

    def test_clear_provider_cooldown(self):
        self.key.record_provider_cooldown(120)
        self.key.clear_provider_cooldown()
        self.key.refresh_from_db()
        self.assertIsNone(self.key.rate_limit_until)
        self.assertFalse(self.key.is_rate_limited()[0])

    def test_select_key_skips_cooling_down_key(self):
        from runtime.rate_limiter import RateLimitChecker, RateLimitResult

        from server.models.providers.ai_model import AiModel

        AiModel.objects.create(api_provider=self.p1, name="Alpha", provider_model_id="sql-alpha")
        model = AiModel.objects.get(api_provider=self.p1)
        self.key.record_provider_cooldown(120)
        with self.assertRaises(RateLimitError):
            RateLimitChecker.check(model)

    def test_select_key_uses_available_sibling_when_one_cools_down(self):
        from runtime.rate_limiter import RateLimitChecker, RateLimitError

        from server.models.providers.ai_model import AiModel

        AiModel.objects.create(api_provider=self.p1, name="Alpha", provider_model_id="sql-alpha")
        model = AiModel.objects.get(api_provider=self.p1)
        other = ApiKey.objects.create(api_provider=self.p1, key="k2", enabled=True)
        self.key.record_provider_cooldown(120)
        result = RateLimitChecker.check(model)
        self.assertIsNotNone(result.selected_key)
        self.assertEqual(result.selected_key.pk, other.pk)


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

    def _stub_query(self, apikey=None):
        return SimpleNamespace(
            pk=1,
            apikey=apikey,
            status=QueryStatus.WAITING,
            session_version=None,
            refresh_from_db=lambda: None,
        )

    def _ok(self):
        return SimpleNamespace(status=ResponseStatus.SUCCESS)

    def test_rate_limit_detection_matches_litellm_errors(self):
        from litellm.exceptions import RateLimitError as LiteLLMRateLimitError
        from litellm.exceptions import MidStreamFallbackError, ServiceUnavailableError

        module = self.call_llm
        err = LiteLLMRateLimitError("rate limited", "openai", "gpt-4")
        self.assertTrue(module._is_provider_rate_limit(err))

        class _Stub429:
            status_code = 429
            message = "quota exceeded"

        self.assertTrue(module._is_provider_rate_limit(_Stub429()))

        class _Stub500:
            status_code = 500
            message = "server error"

        self.assertFalse(module._is_provider_rate_limit(_Stub500()))

        # Google's "high demand, try again later" 503 arrives as a
        # MidStreamFallbackError (subclass of ServiceUnavailableError).
        class _Stub503:
            status_code = 503
            message = "This model is currently experiencing high demand"

        self.assertTrue(module._is_provider_rate_limit(_Stub503()))

        real_503 = ServiceUnavailableError(
            "high demand", "vertex_ai", "gemini-3.6-flash"
        )
        self.assertTrue(module._is_provider_rate_limit(real_503))
        mid = MidStreamFallbackError(
            message="fallback after 503",
            llm_provider="vertex_ai",
            model="gemini-3.6-flash",
            original_exception=real_503,
        )
        self.assertTrue(module._is_provider_rate_limit(mid))

    def test_vertex_ai_badrequest_wrapping_429(self):
        """Vertex AI wraps 429 quota errors as BadRequestError with status 400;
        the real 429 lives in the JSON body.  Verify we still catch it."""
        from litellm.exceptions import BadRequestError

        module = self.call_llm
        vertex_err = BadRequestError(
            message=(
                'litellm.BadRequestError: Vertex_ai_betaException BadRequestError - b\'{\\n '
                '\\"error\\": {\\n \\"code\\": 429,\\n \\"message\\": \\"You exceeded your current '
                'quota, please check your plan and billing details.\\",\\n \\"status\\": '
                '\\"RESOURCE_EXHAUSTED\\"\\n }\\n}\''
            ),
            model="gemini-3.6-flash",
            llm_provider="vertex_ai",
        )
        self.assertTrue(module._is_provider_rate_limit(vertex_err))
        self.assertAlmostEqual(
            module._extract_retry_after_seconds(vertex_err), 4.94, places=1
        )

    def test_retry_after_extraction(self):
        module = self.call_llm

        class _GoogleLike:
            status_code = 429
            message = (
                "Quota exceeded for metric: generate_content_free_tier_requests. "
                "Please retry in 58.184175815s."
            )

        self.assertAlmostEqual(module._extract_retry_after_seconds(_GoogleLike()), 58.184175815)

        class _RetryDelayJson:
            status_code = 429
            message = '{"details": [{"retryDelay": "58s"}]}'

        self.assertAlmostEqual(module._extract_retry_after_seconds(_RetryDelayJson()), 58.0)

        class _Header:
            status_code = 429
            response = SimpleNamespace(headers={"retry-after": "120"})

        self.assertEqual(module._extract_retry_after_seconds(_Header()), 120.0)

        class _NoDelay:
            status_code = 429
            message = "Rate limit exceeded. Please try again later."

        # No explicit retry delay → None, so the key's cooldown default decides.
        self.assertIsNone(module._extract_retry_after_seconds(_NoDelay()))

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

    def test_provider_429_parks_when_every_candidate_rate_limited(self):
        """A litellm 429 from run_streaming_query must be re-raised as the
        runtime RateLimitError so AgentTaskRun parks the call instead of
        hard-failing it (which would consume the retry budget)."""
        from litellm.exceptions import RateLimitError as LiteLLMRateLimitError

        provider_429 = LiteLLMRateLimitError("quota exceeded retry in 20s", "console", "SomeModel")
        with mock.patch.object(self.call_llm, "RateLimitChecker") as checker, mock.patch.object(
            self.call_llm, "Query"
        ):
            checker.check.return_value = RateLimitResult(selected_key=None)
            with mock.patch.object(self.call_llm, "run_streaming_query", side_effect=provider_429) as stream:
                session = _StubSession(aimodel=self.alpha_p1)
                with self.assertRaises(RateLimitError):
                    self.call_llm._call_with_fallback(
                        session=session, query=self._stub_query(), messages=[], tools=[]
                    )
        self.assertEqual(stream.call_count, 2)

    def test_provider_429_falls_back_to_working_sibling(self):
        """When the pinned candidate 429s but a sibling works, the call must
        succeed on the sibling, not park."""
        from litellm.exceptions import RateLimitError as LiteLLMRateLimitError

        provider_429 = LiteLLMRateLimitError("rate limit reached", "console", "SomeModel")
        response = self._ok()
        with mock.patch.object(self.call_llm, "RateLimitChecker") as checker, mock.patch.object(
            self.call_llm, "Query"
        ):
            checker.check.return_value = RateLimitResult(selected_key=None)
            with mock.patch.object(self.call_llm, "run_streaming_query", side_effect=[provider_429, response]) as stream:
                session = _StubSession(aimodel=self.alpha_p1)
                result = self.call_llm._call_with_fallback(
                    session=session, query=self._stub_query(), messages=[], tools=[]
                )
        self.assertIs(result, response)
        self.assertEqual(stream.call_count, 2)
        self.assertEqual(session.aimodel, self.alpha_p2)

    def test_provider_503_parks_when_every_candidate_unavailable(self):
        """A Google 503 "high demand" mid-stream error must be re-raised as
        the runtime RateLimitError so AgentTaskRun parks the call, instead of
        hard-failing and consuming the retry budget."""
        from litellm.exceptions import ServiceUnavailableError

        provider_503 = ServiceUnavailableError(
            "This model is currently experiencing high demand",
            "vertex_ai",
            "gemini-3.6-flash",
        )
        with mock.patch.object(self.call_llm, "RateLimitChecker") as checker, mock.patch.object(
            self.call_llm, "Query"
        ):
            checker.check.return_value = RateLimitResult(selected_key=None)
            with mock.patch.object(self.call_llm, "run_streaming_query", side_effect=provider_503) as stream:
                session = _StubSession(aimodel=self.alpha_p1)
                with self.assertRaises(RateLimitError):
                    self.call_llm._call_with_fallback(
                        session=session, query=self._stub_query(), messages=[], tools=[]
                    )
        self.assertEqual(stream.call_count, 2)
        self.assertEqual(session.repinned, [])

    def test_provider_503_falls_back_to_working_sibling(self):
        from litellm.exceptions import ServiceUnavailableError

        provider_503 = ServiceUnavailableError(
            "high demand, try again later", "vertex_ai", "gemini-3.6-flash"
        )
        response = self._ok()
        with mock.patch.object(self.call_llm, "RateLimitChecker") as checker, mock.patch.object(
            self.call_llm, "Query"
        ):
            checker.check.return_value = RateLimitResult(selected_key=None)
            with mock.patch.object(self.call_llm, "run_streaming_query", side_effect=[provider_503, response]) as stream:
                session = _StubSession(aimodel=self.alpha_p1)
                result = self.call_llm._call_with_fallback(
                    session=session, query=self._stub_query(), messages=[], tools=[]
                )
        self.assertIs(result, response)
        self.assertEqual(stream.call_count, 2)
        self.assertEqual(session.aimodel, self.alpha_p2)

    def test_run_streaming_query_records_provider_cooldown_on_key(self):
        """A 429 in run_streaming_query must store the provider's retry delay
        on the ApiKey so the rate limiter skips it until the cooldown passes."""
        from litellm.exceptions import RateLimitError as LiteLLMRateLimitError

        from django.utils import timezone

        apikey = ApiKey.objects.create(api_provider=self.p1, key="k-cooldown", enabled=True)
        sv = SimpleNamespace(session=SimpleNamespace())
        query = SimpleNamespace(
            pk=2,
            apikey=apikey,
            status=QueryStatus.ACTIVE,
            session_version=sv,
            refresh_from_db=lambda: None,
        )
        provider_429 = LiteLLMRateLimitError(
            "quota exceeded Please retry in 20s", "gemini", "gemini-3.6-flash"
        )
        saved_statuses = []

        class _Resp:
            status = ResponseStatus.ACTIVE
            content = ""
            reasoning = ""
            save = lambda self: saved_statuses.append(self.status)

        with mock.patch(
            "server.models.queries.response.Response.objects.create",
            return_value=_Resp(),
        ), mock.patch.object(self.call_llm.litellm, "completion", side_effect=provider_429):
            with self.assertRaises(LiteLLMRateLimitError):
                self.call_llm.run_streaming_query(
                    session=_StubSession(aimodel=self.alpha_p1),
                    tools=[],
                    messages=[],
                    query=query,
                )
        apikey.refresh_from_db()
        self.assertIsNotNone(apikey.rate_limit_until)

    def test_run_streaming_query_records_cooldown_on_503(self):
        """A 503 "high demand" must also park the key — a transient capacity
        error is the same retry-later signal as a 429."""
        from litellm.exceptions import ServiceUnavailableError

        from django.utils import timezone

        apikey = ApiKey.objects.create(
            api_provider=self.p1, key="k-503", enabled=True
        )
        sv = SimpleNamespace(session=SimpleNamespace())
        query = SimpleNamespace(
            pk=3,
            apikey=apikey,
            status=QueryStatus.ACTIVE,
            session_version=sv,
            refresh_from_db=lambda: None,
        )
        provider_503 = ServiceUnavailableError(
            "This model is currently experiencing high demand", "vertex_ai", "gemini-3.6"
        )
        saved_statuses = []

        class _Resp:
            status = ResponseStatus.ACTIVE
            content = ""
            reasoning = ""
            save = lambda self: saved_statuses.append(self.status)

        with mock.patch(
            "server.models.queries.response.Response.objects.create",
            return_value=_Resp(),
        ), mock.patch.object(self.call_llm.litellm, "completion", side_effect=provider_503):
            with self.assertRaises(ServiceUnavailableError):
                self.call_llm.run_streaming_query(
                    session=_StubSession(aimodel=self.alpha_p1),
                    tools=[],
                    messages=[],
                    query=query,
                )
        apikey.refresh_from_db()
        self.assertIsNotNone(apikey.rate_limit_until)


def _stream_event(delta=None, finish=None, usage=None):
    data = {"choices": [{"delta": delta or {}, "finish_reason": finish}]}
    if usage is not None:
        data["usage"] = usage
    return SimpleNamespace(model_dump=lambda data=data: dict(data))


class _FakeStream:
    """Sync stand-in for litellm's CustomStreamWrapper."""

    def __init__(self, events):
        self._events = events
        self.completion_stream = mock.Mock()

    def __iter__(self):
        return iter(self._events)


class _StubResponse:
    def __init__(self):
        self.pk = 99
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

    def save(self):
        pass


class StreamCloseTest(TestCase):
    """Abandoned streams must be closed; looping is detected early and its
    partial reasoning is accepted as a valid response."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.call_llm = _load_call_llm()

    def setUp(self):
        self.p1 = ApiProvider.objects.create(name="p1")
        ApiKey.objects.create(api_provider=self.p1, key="k1", enabled=True)
        self.model = AiModel.objects.create(api_provider=self.p1, name="Alpha", provider_model_id="alpha")

    def _stub_query(self):
        sv = SimpleNamespace(session=SimpleNamespace())
        return SimpleNamespace(
            pk=7,
            apikey=ApiKey.objects.filter(api_provider=self.p1).first(),
            status=QueryStatus.ACTIVE,
            session_version=sv,
            refresh_from_db=lambda: None,
        )

    def test_looping_stream_closed_and_accepted(self):
        """Repetitive output: detected early, partial reasoning kept, SUCCESS."""
        events = [_stream_event(delta={"reasoning_content": "L" * 300}) for _ in range(8)]
        stream = _FakeStream(events)
        inner = stream.completion_stream
        resp = _StubResponse()
        with mock.patch(
            "server.models.queries.response.Response.objects.create",
            return_value=resp,
        ), mock.patch.object(self.call_llm.litellm, "completion", return_value=stream):
            returned = self.call_llm.run_streaming_query(
                session=_StubSession(aimodel=self.model),
                tools=[],
                messages=[],
                query=self._stub_query(),
            )
        self.assertIs(returned, resp)
        # Looping is flagged for inspection but counted as valid since it is
        # detected early (see call_llm.py).  If it ever feeds the chain with
        # garbage we can flip this back to FAILURE + raise.
        self.assertEqual(resp.finish_reason, "Looping detected")
        self.assertEqual(resp.status, ResponseStatus.SUCCESS)
        self.assertTrue(resp.reasoning)
        # Server-side generation is cancelled via the underlying stream.
        inner.close.assert_called_once_with()
        self.assertIsNone(stream.completion_stream)

    def test_successful_stream_closed(self):
        """The happy path must also release the server-side stream."""
        events = [
            _stream_event(delta={"content": "hello"}),
            _stream_event(finish="stop", usage={"completion_tokens": 5, "prompt_tokens": 10}),
        ]
        stream = _FakeStream(events)
        inner = stream.completion_stream
        resp = _StubResponse()
        with mock.patch(
            "server.models.queries.response.Response.objects.create",
            return_value=resp,
        ), mock.patch.object(self.call_llm.litellm, "completion", return_value=stream):
            result = self.call_llm.run_streaming_query(
                session=_StubSession(aimodel=self.model),
                tools=[],
                messages=[],
                query=self._stub_query(),
            )
        self.assertEqual(result.status, ResponseStatus.SUCCESS)
        self.assertEqual(result.content, "hello")
        inner.close.assert_called_once_with()
        self.assertIsNone(stream.completion_stream)

    def test_exception_stream_closed(self):
        """A mid-stream hard failure must still close the stream."""
        from litellm.exceptions import APIConnectionError

        events = [_stream_event(delta={"content": "part"})]

        class _ExplodingStream(_FakeStream):
            def __iter__(self):
                yield from self._events
                raise APIConnectionError("conn reset", llm_provider="openai", model="alpha")

        stream = _ExplodingStream(events)
        inner = stream.completion_stream
        resp = _StubResponse()
        with mock.patch(
            "server.models.queries.response.Response.objects.create",
            return_value=resp,
        ), mock.patch.object(self.call_llm.litellm, "completion", return_value=stream):
            with self.assertRaises(APIConnectionError):
                self.call_llm.run_streaming_query(
                    session=_StubSession(aimodel=self.model),
                    tools=[],
                    messages=[],
                    query=self._stub_query(),
                )
        self.assertEqual(resp.status, ResponseStatus.FAILURE)
        inner.close.assert_called_once_with()
        self.assertIsNone(stream.completion_stream)