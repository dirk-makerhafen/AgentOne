"""
Streams the Query to the LLM API and records the Response.
Handles rate limiting, API key selection, and streaming ingestion.
Uses LiteLLM for unified API across providers.
"""
from __future__ import annotations

import json
import time
import traceback
from typing import Any

from django.utils import timezone
from runtime.session.session import Session
from runtime.tool_argument_utils import normalize_tool_arguments
from server.models.settings import AgentToolCallSyntax
from server.models.queries.query import Query, QueryStatus
from server.models.queries.response import Response, ResponseStatus
import litellm
from runtime.rate_limiter import RateLimitChecker, RateLimitError
from runtime.llm_errors import (
    ModelUnavailableError,
    classify_llm_error,
    extract_retry_after_seconds,
)
from runtime.power import battery_gate_blocked
from runtime.query_failures import record_query_failure
import re
import logging
# Drop unsupported params (e.g. reasoning_effort on models without thinking)
# instead of erroring, so the same request works across providers.
litellm.drop_params = True
logger = logging.getLogger(__name__)
litellm_logger = logging.getLogger("LiteLLM")
litellm_logger.setLevel(logging.ERROR)
litellm_logger.propagate = False  # Ve
litellm.logging = False
litellm.suppress_debug_info = True


def _is_provider_rate_limit(exc) -> bool:
    """True when *exc* is a provider-side rate limit or transient unavailability.

    Compatibility wrapper around :func:`runtime.llm_errors.classify_llm_error`.
    See that module for the full taxonomy (429/503/timeout are transient;
    404/401/403/400 are classified separately by the caller).
    """
    return classify_llm_error(exc).kind == "rate_limit"


def _extract_retry_after_seconds(exc) -> float | None:
    """Return the cooldown the provider asked for, in seconds.

    Compatibility wrapper around
    :func:`runtime.llm_errors.extract_retry_after_seconds`.
    """
    return extract_retry_after_seconds(exc)


def _get_litellm_model_name(provider: Any, api_model_id: str) -> str:
    """Map an :class:`ApiProvider` to the LiteLLM model string.

    Providers with a ``litellm_prefix`` (e.g. ``groq``, ``gemini``,
    ``openrouter``) are routed through LiteLLM's native provider:
    ``{prefix}/{model}``.  Everyone else is OpenAI-compatible and is routed
    through ``openai/`` with the provider's ``url`` as the ``api_base``.
    """
    prefix = (getattr(provider, "litellm_prefix", "") or "").strip()
    if prefix:
        return f"{prefix}/{api_model_id}"
    return f"openai/{api_model_id}"


def _close_stream(stream: Any | None) -> None:
    """Close an abandoned LiteLLM stream so the server drops its generation.

    ``CustomStreamWrapper`` only exposes async ``aclose``; the sync path
    holds a sync httpx ``completion_stream`` underneath.  Closing it releases
    the server-side generation (e.g. the OMLX parallel slot) — without this,
    breaking out of ``for event in stream`` leaves a ghost generation
    running server-side while our Query has long moved on.
    """
    if stream is None:
        return
    inner = getattr(stream, "completion_stream", None)
    if inner is not None:
        try:
            stream.completion_stream = None
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        close = getattr(inner, "close", None)
        if callable(close):
            try:
                close()
                return
            except Exception:  # pylint: disable=broad-exception-caught
                pass
    close = getattr(stream, "close", None)
    if callable(close):
        try:
            close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

# Thinking control for local OpenAI-compatible servers (OMLX, Ollama,
# vLLM, SGLang) serving Qwen3-style checkpoints.
#
# Researched against the actually-served checkpoint: this model's
# chat_template.jinja honours ONLY the ``enable_thinking`` bool
# (off → empty think block, anything else → open <think>) plus
# ``preserve_thinking``.  It reads NO ``reasoning_effort`` variable, so
# graded effort strings are a confirmed no-op here and are deliberately
# NOT mapped onto thinking_budget caps (a budget is a ceiling, not
# effort influence — silently substituting it would fake a feature the
# model doesn't have).  The single honest bridge is ``none`` → thinking
# off, which is exactly what that tier advertises.
def _local_thinking_extra_body(effort: Any) -> dict:
    """Map an AgentOne reasoning effort onto OMLX-style body params.

    Returns an ``extra_body`` fragment: ``{"enable_thinking": False}``
    for ``none``, empty for every other tier (the checkpoint has no
    graded effort mechanism; LiteLLM drops the top-level
    ``reasoning_effort`` for these providers with ``drop_params=True``).
    """
    if str(effort or "none").lower() == "none":
        return {"enable_thinking": False}
    return {}

def detect_repeat(content):
    for blocksize in [128, 256, 512, 1024]:
        windowsize = blocksize * 6
        if len(content) < windowsize:
            break
        window = content[-windowsize:]
        if window and window.count(content[-blocksize:]) >= 3:
            return True
    return False

def _backoff_seconds(failures: int) -> float:
    """Escalating retry delay for transient model failures (1 min → 1 h)."""
    return min(60.0 * (2 ** min(max(failures - 1, 0), 5)), 3600.0)


def _error_detail(info, exc) -> dict:
    """JSON-safe detail stored alongside the health status."""
    return {
        "error_type": info.kind,
        "status_code": info.status_code,
        "message": (info.message or "")[:2000],
        "exception_class": type(exc).__name__,
    }


def _record_health_failure(aimodel: Any, apikey: Any, info, exc) -> None:
    """Apply a classified provider failure to the affected row(s).

    ``rate_limit`` is handled by ``ApiKey.record_provider_cooldown`` (called
    by the caller); everything else lands here.  Request-scoped errors (a
    context-length 400) intentionally do **not** change model health.
    """
    if aimodel is None or not info.health_status:
        return
    if info.kind == "rate_limit":
        # The key cooldown (and its status) is recorded by the caller.
        return
    detail = _error_detail(info, exc)

    if info.kind == "auth":
        if apikey is not None:
            apikey.record_health_error(
                info.health_status,
                info.message,
                detail=detail,
                sticky=True,
            )
        provider = aimodel.api_provider
        if provider is not None and provider.all_enabled_keys_auth_failed():
            provider.record_health_error(
                info.health_status,
                info.message,
                detail=detail,
                sticky=True,
            )
        return

    if info.kind in ("timeout", "server", "connection"):
        failures = (aimodel.consecutive_failures or 0) + 1
        retry_after = _backoff_seconds(failures)
        aimodel.record_health_error(
            info.health_status,
            info.message,
            detail=detail,
            retry_after_seconds=retry_after,
        )
        provider = aimodel.api_provider
        if provider is not None:
            provider.record_health_error(
                info.health_status,
                info.message,
                detail=detail,
                retry_after_seconds=retry_after,
            )
        return

    # model_not_found / config_like bad_request — sticky or long-retry.
    aimodel.record_health_error(
        info.health_status,
        info.message,
        detail=detail,
        retry_after_seconds=None if info.sticky else 3600.0,
        sticky=info.sticky,
    )


def _record_health_success(aimodel: Any, apikey: Any) -> None:
    """Clear observed failures after a successful provider call."""
    if apikey is not None:
        apikey.record_health_success()
    if aimodel is not None:
        aimodel.record_health_success()
        provider = aimodel.api_provider
        if provider is not None:
            provider.record_health_success()


def run_streaming_query(
    session: Session,
    tools: list[dict[Any, Any]],
    messages: list[dict[Any, Any]],
    query: Query,
    aimodel: Any | None = None,
) -> Response:
    SAVE_INTERVAL = 1.000
    last_save_time = time.time()
    first_token_timestamp: float | None = None
    first_reasoning_token_timestamp: float | None = None
    last_reasoning_token_timestamp: float | None = None
    start_timestamp = time.time()
    sv = query.session_version
    aimodel = aimodel or session.aimodel
    response = Response.objects.create(
        query=query,
        session=sv.session,
        session_version=sv,
        status=ResponseStatus.ACTIVE,
        tool_calls=[],
        aimodel=aimodel,
        model_name=aimodel.name if aimodel else "",
        provider_name=aimodel.api_provider.name if aimodel and aimodel.api_provider else "",
    )
    api_provider = aimodel.api_provider if aimodel and aimodel.api_provider else None
    api_model_id = aimodel.provider_model_id or aimodel.name if aimodel else ""
    model_name = _get_litellm_model_name(api_provider, api_model_id)
    args = dict(
        model=model_name,
        messages=messages,
        stream=True,
        stream_options={"include_usage": True},
        api_key=query.apikey.key if query.apikey else (api_provider.default_api_key if api_provider else ""),
    )
    if aimodel and aimodel.supports_reasoning:
        args["reasoning_effort"] = session.reasoning_effort
    if api_provider is not None and not (api_provider.litellm_prefix or "").strip():
        args["api_base"] = api_provider.url
        # Local OpenAI-compatible servers never see the top-level
        # reasoning_effort (LiteLLM drops it as unsupported).  The only
        # bridge is the thinking off-switch for effort "none"; graded
        # tiers are intentionally left alone (no budget substitution).
        # extra_body is merged into the request body by the handler.
        if aimodel and aimodel.supports_reasoning:
            extra = _local_thinking_extra_body(session.reasoning_effort)
            if extra:
                args["extra_body"] = {**(args.get("extra_body") or {}), **extra}
    if tools:
        args["tools"] = tools
        args["tool_choice"] = "auto"
    stream = None
    loop_detected = False
    output_type = None
    try:
        stream = litellm.completion(**args, timeout=1800)
        repeat_count = 0
        new_chars_count = 0
        for event in stream:
            if repeat_count >= 6:
                loop_detected = True
                break
            event_data = event.model_dump()
            unknown_chunk = True
            if usage := event_data.get("usage", None):
                unknown_chunk = False
                response.completion_tokens = int(usage.get("completion_tokens", 0) or 0)
                response.prompt_tokens = int(usage.get("prompt_tokens", 0))
                prompt_details = usage.get("prompt_tokens_details", {}) or {}
                response.cached_tokens = int(prompt_details.get("cached_tokens", 0) or 0)
                completion_details = usage.get("completion_tokens_details", {}) or {}
                response.reasoning_tokens = int(completion_details.get("reasoning_tokens", 0) or 0)
            choices = event_data.get("choices", [{}])
            if not choices:
                continue
            message_chunk = choices[0].get("delta", {})
            if finish_reason := choices[0].get("finish_reason"):
                unknown_chunk = False
                response.finish_reason = finish_reason
            reasoning_chunk = message_chunk.get("reasoning", None) or message_chunk.get("thinking", None) or message_chunk.get("reasoning_content", None)

            if reasoning_chunk:
                if output_type != "reasoning":
                    repeat_count = 0
                    output_type = "reasoning"
                if not first_reasoning_token_timestamp:
                    first_reasoning_token_timestamp = time.time()
                last_reasoning_token_timestamp = time.time()
                unknown_chunk = False
                response.reasoning += reasoning_chunk
                new_chars_count += len(reasoning_chunk)
                if new_chars_count >= 128:
                    new_chars_count = 0
                    repeat_count += 1 if detect_repeat(response.reasoning) else -0.2 if repeat_count > 0.2 else 0

            if content_chunk := message_chunk.get("content", None):
                if output_type != "content":
                    repeat_count = 0
                    output_type = "content"
                unknown_chunk = False
                response.content += content_chunk
                new_chars_count += len(content_chunk)
                if new_chars_count >= 128:
                    new_chars_count = 0
                    repeat_count += 1 if detect_repeat(response.content) else -0.2 if repeat_count > 0.2 else 0
               
            if tool_calls_chunk := message_chunk.get("tool_calls", None):
                output_type = "toolcall"
                unknown_chunk = False
                for tool_call in tool_calls_chunk:
                    index = tool_call.get("index", 0) or 0
                    if not response.tool_calls:
                        response.tool_calls = []
                    while len(response.tool_calls) <= index:
                        response.tool_calls.append(
                            {
                                "name": "",
                                "arguments": "",
                                "id": "",
                                "index": len(response.tool_calls),
                            }
                        )
                    if tool_call_id := tool_call.get("id"):
                        response.tool_calls[index]["id"] += tool_call_id
                    if func := tool_call.get("function"):
                        if fname := func.get("name"):
                            response.tool_calls[index]["name"] += fname
                        if arguments := func.get("arguments"):
                            response.tool_calls[index]["arguments"] += arguments
            if unknown_chunk:
                print("Unknown Chunk: ", event_data)
            else:
                if not first_token_timestamp:
                    first_token_timestamp = time.time()
            if time.time() - last_save_time > SAVE_INTERVAL:
                # Periodic streaming saves update the response row itself but
                # must not republish the session-level keys: those would redraw
                # the whole thread for every 1 Hz token flush.  Publish only the
                # row key so the response component still tracks the tokens.
                response.save(publish=False)
                from runtime.observable_keys import partial_row_keys
                from server.models.observables import publish_model_event
                publish_model_event(partial_row_keys(response), response, "update")
                last_save_time = time.time()
    except Exception as exc:
        # Provider hard-failure (connection, 5xx, auth, 404, ...).  Classify
        # once, record the audit trail on the Response, then apply the failure
        # to the affected model/key/provider row(s).  Record how far the
        # stream got first so the caller can avoid duplicating partial output.
        retry_after = _extract_retry_after_seconds(exc)
        info = classify_llm_error(exc, retry_after)
        if info.kind == "rate_limit":
            apikey = query.apikey
            if apikey is not None:
                # 429/503 with a retry delay — park the key the provider
                # throttled so the rate limiter skips it until the cooldown.
                apikey.record_provider_cooldown(retry_after, reason=info.message)
        try:
            _record_health_failure(aimodel, query.apikey, info, exc)
        except Exception:  # pylint: disable=broad-exception-caught
            # Health bookkeeping must never mask the provider error itself.
            logger.exception("failed to record model health failure")
        response.error_type = info.kind
        response.error_message = (info.message or str(exc))[:50000]
        response.status = ResponseStatus.FAILURE
        response.save()
        raise
    finally:
        _close_stream(stream)
    if loop_detected:
        # Repetitive output is detected early, so the partial reasoning is
        # counted as a valid response (finish_reason flags it for inspection).
        # If the garbage ever feeds the chain, flip this back to FAILURE and
        # raise with streamed_content set so _call_with_fallback re-raises
        # immediately (no sibling retry) and the task retry budget bounds
        # re-attempts.
        response.finish_reason = "Looping detected"
        response.status = ResponseStatus.SUCCESS
        response.save()
        #err = RuntimeError("Looping detected; partial output kept in FAILURE response")
        #err.streamed_content = response.content or response.reasoning
        #raise err
    end_timestamp = time.time()
    for tool_call in response.tool_calls:
        try:
            tool_call["arguments"] = json.loads(tool_call["arguments"])
        except json.JSONDecodeError:
            pass
        tool_call["arguments"] = normalize_tool_arguments(tool_call["arguments"])
    response.time_to_first_token = 0
    response.token_generation_time = 0
    response.reasoning_time = 0
    response.total_time = end_timestamp - start_timestamp
    if first_token_timestamp:
        response.time_to_first_token = first_token_timestamp - start_timestamp
        response.token_generation_time = end_timestamp - first_token_timestamp
    if first_reasoning_token_timestamp and last_reasoning_token_timestamp:
        response.reasoning_time = (
            last_reasoning_token_timestamp - first_reasoning_token_timestamp
        )
    response.content = re.sub(r'\s*</parameter>\s?</function>\s?</tool_call>\s*$','',str(response.content))

    if first_token_timestamp and response.finish_reason:
        response.status = ResponseStatus.SUCCESS
        response.error_type = ""
        response.error_message = ""
        # Update last_usage on provider and model
        if aimodel and aimodel.api_provider:
            aimodel.api_provider.last_usage = timezone.now()
            aimodel.api_provider.save(update_fields=["last_usage"])
        if aimodel:
            aimodel.last_usage = timezone.now()
            aimodel.save(update_fields=["last_usage"])
        try:
            _record_health_success(aimodel, query.apikey)
        except Exception:  # pylint: disable=broad-exception-caught
            # A bookkeeping failure must not discard a successful response.
            logger.exception("failed to record model health success")
    else:
        response.status = ResponseStatus.FAILURE
        response.error_type = response.error_type or "empty_response"
        response.error_message = response.error_message or "Provider returned no content."
    response.save()
    return response


def _call_with_fallback(
    session: Session,
    query: Query,
    messages: list[dict[Any, Any]],
    tools: list[dict[Any, Any]],
) -> Response:
    """Run the request on the pinned provider, falling back to sibling
    providers that serve the same canonical model name when it hard-fails.

    - ``RateLimitError`` never retries across the whole chain blindly: a
      rate-limited candidate is skipped, but if every candidate is parked the
      last ``RateLimitError`` is re-raised so the scheduler can hold the call.
    - A hard failure that streamed nothing is safe to re-attempt on the next
      sibling.  A mid-stream failure has already delivered partial output and
      is propagated so it is never duplicated.
    - When a sibling succeeds, the session is re-pinned to that provider so
      subsequent calls reuse it (KV-cache friendly).
    """
    from runtime.session.aimodel_picker import sibling_aimodels

    pinned = session.aimodel
    if pinned is None:
        candidates = []
    elif pinned.health_blocks_calls():
        # The session is pinned to a row that is known-bad (404, revoked key,
        # ...).  Prefer a healthy sibling; only fall back to the pinned row
        # when nothing else serves the name, so the failure is still visible.
        alternatives = sibling_aimodels(pinned)
        candidates = alternatives or [pinned]
    else:
        candidates = [pinned] + sibling_aimodels(pinned)
    last_error: Exception | None = None
    claimed = False
    for aimodel in candidates:
        try:
            ratelimit_result = RateLimitChecker.check(aimodel, session=session)
            if not ratelimit_result:
                raise Exception("Error in ratelimiter")
            apikey = ratelimit_result.selected_key
            if not claimed:
                # Claim the query exactly once per attempt: only an unowned
                # (WAITING), retry-reusable (FAILURE), or capacity-parked
                # (RATE_LIMITED) row may flip to ACTIVE.  RATE_LIMITED is
                # *not* terminal for the owning call: the scheduler releases
                # WAITING_RATELIMIT -> WAITING_QUEUE and re-dispatches this
                # same query when capacity returns, so the claim must accept
                # it (otherwise every released call hard-fails here and burns
                # a retry).  Never resurrect a terminal (SUCCESS) query or
                # hijack a foreign ACTIVE one — a retry of an ancient call
                # must fail here, not open a ghost stream on a sibling.
                updated = Query.atomic_update_by_pk(
                    query.pk,
                    expect={
                        "status__in": [
                            QueryStatus.WAITING,
                            QueryStatus.FAILURE,
                            QueryStatus.RATE_LIMITED,
                        ],
                    },
                    apikey=apikey,
                    status=QueryStatus.ACTIVE,
                )
                if not updated:
                    raise Exception("Failed to update query to active state")
                claimed = True
            else:
                # Our own in-flight ACTIVE row — just refresh the key.
                query.atomic_update(apikey=apikey)
            query.apikey = apikey
            query.status = QueryStatus.ACTIVE  # DB row was set by the filter update above

            response = run_streaming_query(
                session=session,
                messages=messages,
                tools=tools,
                query=query,
                aimodel=aimodel,
            )
            if query.apikey is not None:
                query.apikey.clear_provider_cooldown()
            if pinned is None or aimodel.pk != pinned.pk:
                session.set_aimodel(aimodel)
            if response.status == ResponseStatus.SUCCESS:
                query.atomic_update(status=QueryStatus.SUCCESS)
            else:
                # Persist the reason on the Response before the query becomes
                # terminal — the failed query card is immutable in the UI.
                record_query_failure(query, response.error_type, response.error_message)
            query.refresh_from_db()
            return response
        except RateLimitError as exc:
            if "auth_error" in (exc.reason or ""):
                # A revoked/forbidden key will not recover by waiting.
                last_error = ModelUnavailableError(str(exc))
            else:
                last_error = exc
        except ModelUnavailableError as exc:
            # Known-bad model/provider row — try the next candidate.
            last_error = exc
            continue
        except Exception as exc:
            if _is_provider_rate_limit(exc):
                # Provider 429 — the candidate's key is now on cooldown (set
                # inside run_streaming_query).  Convert to our own rate-limit
                # error so the whole task parks (WAITING_RATELIMIT) and the
                # scheduler re-runs it once capacity/cooldown returns, instead
                # of hard-failing and consuming the retry budget.
                last_error = RateLimitError("provider_rate_limit")
                continue
            last_error = exc
            if getattr(exc, "streamed_content", ""):
                raise
    if last_error is not None:
        raise last_error
    raise Exception("No provider could handle the request")


def call_llm(_session: Session, query: Query) -> Response:
    """
    Send the Query to the LLM and stream the response.

    Handles rate-limit checking and API key selection before calling
    the provider. RateLimitError is caught by AgentTaskRun.apply()
    and transitions to RATE_LIMITED status (no retry budget consumed).

    Args:
        _session: The active agent session.
        query:   The Query (built by build_llm_context) to send.

    Returns:
        A Response model containing the streamed LLM output.
    """
    try:
        if not _session.aimodel:
            raise Exception("No llm model specified")

        # Low-battery pause for local models — parks the call via the
        # existing RateLimitError mechanism (WAITING_RATELIMIT + auto-resume).
        # A hard gate on the pinned model: we do NOT fall back to a cloud
        # provider to bypass a battery warning.
        blocked, reason = battery_gate_blocked(_session.aimodel)
        if blocked:
            raise RateLimitError(reason)

        messages = query.to_openai_message()
        api_tools: list[dict[Any, Any]] = []
        if _session.tool_call_syntax == AgentToolCallSyntax.DEFAULT:
            for tool in _session.allowedTools:
                if not tool.task_definition:
                    raise Exception("Missing task_definition")
                api_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.task_definition.name,
                            "description": tool.description,
                            "parameters": tool.function_schema,
                        },
                    }
                )

        return _call_with_fallback(
            session=_session,
            query=query,
            messages=messages,
            tools=api_tools,
        )

    except RateLimitError as exc:
        info = classify_llm_error(exc)
        record_query_failure(
            query,
            info.kind,
            info.message or str(exc) or "Provider rate limit",
            status=QueryStatus.RATE_LIMITED,
        )
        raise

    except Exception as exc:
        info = classify_llm_error(exc)
        # The Response may already carry a more specific provider error from a
        # failed stream; record_query_failure keeps it instead of overwriting.
        record_query_failure(query, info.kind, info.message or str(exc))
        from server.models.debug_log_entry import DebugLogEntry

        DebugLogEntry.objects.create(
            session=_session.model,
            event="exception",
            data={"exception": traceback.format_exc()},
        )
        raise
