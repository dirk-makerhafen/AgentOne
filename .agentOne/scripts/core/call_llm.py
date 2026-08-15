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

from runtime.session.session import Session
from runtime.tool_argument_utils import normalize_tool_arguments
from server.models.settings import AgentToolCallSyntax
from server.models.queries.query import Query, QueryStatus
from server.models.queries.response import Response, ResponseStatus
import litellm
from runtime.rate_limiter import RateLimitChecker, RateLimitError
from runtime.power import battery_gate_blocked
import re
import logging
# Drop unsupported params (e.g. reasoning_effort on models without thinking)
# instead of erroring, so the same request works across providers.
litellm.drop_params = True
litellm_logger = logging.getLogger("LiteLLM")
litellm_logger.setLevel(logging.ERROR)
litellm_logger.propagate = False  # Ve
litellm.logging = False
litellm.suppress_debug_info = True

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


def run_streaming_query(
    session: Session,
    tools: list[dict[Any, Any]],
    messages: list[dict[Any, Any]],
    query: Query,
    aimodel: Any | None = None,
) -> Response:
    SAVE_INTERVAL = 0.500
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
        api_key=query.apikey.key if query.apikey else (api_provider.data or {}).get("default_api_key", "") if api_provider else "",
    )
    if aimodel and aimodel.supports_reasoning:
        args["reasoning_effort"] = session.reasoning_effort
    if api_provider is not None and not (api_provider.litellm_prefix or "").strip():
        args["api_base"] = api_provider.url
    if tools:
        args["tools"] = tools
        args["tool_choice"] = "auto"
    try:
        stream = litellm.completion(**args)
        repeat_count = 0
        for event in stream:
            if repeat_count >= 5:
                response.finish_reason = "Looping detected"
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
                if not first_reasoning_token_timestamp:
                    first_reasoning_token_timestamp = time.time()
                last_reasoning_token_timestamp = time.time()
                unknown_chunk = False
                response.reasoning += reasoning_chunk
                r = response.reasoning
                if r and r.count(r[-255:]) > 1:
                    repeat_count += 1
            if content_chunk := message_chunk.get("content", None):
                unknown_chunk = False
                response.content += content_chunk
                r = response.content
                if r and r.count(r[-255:]) > 1:
                    repeat_count += 1
            if tool_calls_chunk := message_chunk.get("tool_calls", None):
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
                response.save()
                last_save_time = time.time()
    except Exception as exc:
        # Provider hard-failure (connection, 5xx, auth, etc.).  Record how far
        # the response got so the caller can avoid duplicating a partial stream,
        # then mark the orphaned response FAILURE instead of leaving it ACTIVE.
        exc.streamed_content = response.content or response.reasoning
        response.status = ResponseStatus.FAILURE
        response.save()
        raise
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
    else:
        response.status = ResponseStatus.FAILURE
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
    candidates = [pinned] + sibling_aimodels(pinned)
    last_error: Exception | None = None
    first = True
    for aimodel in candidates:
        try:
            ratelimit_result = RateLimitChecker.check(aimodel)
            if not ratelimit_result:
                raise Exception("Error in ratelimiter")
            apikey = ratelimit_result.selected_key
            if first:
                updated = Query.objects.filter(pk=query.pk, status__in=[QueryStatus.WAITING, QueryStatus.FAILURE]).update(
                    apikey=apikey, status=QueryStatus.ACTIVE
                )
                if not updated:
                    raise Exception("Failed to update query to active state")
            else:
                Query.objects.filter(pk=query.pk).update(apikey=apikey, status=QueryStatus.ACTIVE)
            query.apikey = apikey
            query.status = QueryStatus.ACTIVE  # DB row was set by the filter update above

            response = run_streaming_query(
                session=session,
                messages=messages,
                tools=tools,
                query=query,
                aimodel=aimodel,
            )
            if not first:
                session.set_aimodel(aimodel)
            Query.objects.filter(pk=query.pk).update(
                status=QueryStatus.SUCCESS if response.status == ResponseStatus.SUCCESS else QueryStatus.FAILURE
            )
            query.refresh_from_db()
            return response
        except RateLimitError as exc:
            last_error = exc
        except Exception as exc:
            last_error = exc
            if getattr(exc, "streamed_content", ""):
                raise
        finally:
            first = False
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

    except RateLimitError:
        Query.objects.filter(pk=query.pk).update(status=QueryStatus.FAILURE)
        query.refresh_from_db()
        from runtime.events import publish_model_event
        publish_model_event(query, "update")
        raise

    except Exception:
        Query.objects.filter(pk=query.pk).update(status=QueryStatus.FAILURE)
        query.refresh_from_db()
        from runtime.events import publish_model_event
        publish_model_event(query, "update")
        from server.models.debug_log_entry import DebugLogEntry

        DebugLogEntry.objects.create(
            session=_session.model,
            event="exception",
            data={"exception": traceback.format_exc()},
        )
        raise
