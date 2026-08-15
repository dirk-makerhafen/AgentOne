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

# Drop unsupported params (e.g. reasoning_effort on models without thinking)
# instead of erroring, so the same request works across providers.
litellm.drop_params = True


PROVIDER_LITELLM_PREFIX = {
    "Google": "gemini/",
    "OpenRouter": "openrouter/",
    "Groq": "groq/",
    "DeepSeek": "deepseek/",
    "Together AI": "together_ai/",
    "Alibaba Cloud": "dashscope/",
    "Ollama": "ollama/",
}

# OpenAI-compatible providers LiteLLM has no native prefix for; they are
# routed through the openai provider using each provider URL as api_base.
PROVIDER_OPENAI_COMPATIBLE = {
    "Zhipu AI",
    "SiliconFlow",
    "OpenCode Zen",
    "Ollama Cloud",
}


def _get_litellm_model_name(provider_name: str, model_name: str) -> str:
    """Map provider name to a LiteLLM model name.

    LiteLLM uses the {provider}/{model} format for providers it knows
    natively.  OpenAI-compatible providers LiteLLM lacks a native prefix for
    are routed through the ``openai`` provider with an explicit ``api_base``.
    Unknown providers pass through unchanged (assumed OpenAI-compatible).
    """
    if provider_name in PROVIDER_LITELLM_PREFIX:
        return f"{PROVIDER_LITELLM_PREFIX[provider_name]}{model_name}"
    if provider_name in PROVIDER_OPENAI_COMPATIBLE:
        return f"openai/{model_name}"
    return model_name


def run_streaming_query(
    session: Session,
    tools: list[dict[Any, Any]],
    messages: list[dict[Any, Any]],
    query: Query,
) -> Response:
    SAVE_INTERVAL = 0.500
    last_save_time = time.time()
    first_token_timestamp: float | None = None
    first_reasoning_token_timestamp: float | None = None
    last_reasoning_token_timestamp: float | None = None
    start_timestamp = time.time()
    sv = query.session_version
    response = Response.objects.create(
        query=query,
        session=sv.session,
        session_version=sv,
        status=ResponseStatus.ACTIVE,
        tool_calls=[],
        aimodel=session.aimodel,
        model_name=session.aimodel.name if session.aimodel else "",
        provider_name=session.aimodel.api_provider.name if session.aimodel and session.aimodel.api_provider else "",
    )
    provider = session.aimodel.api_provider.name if session.aimodel and session.aimodel.api_provider else ""
    api_model_id = session.aimodel.provider_model_id or session.aimodel.name if session.aimodel else ""
    model_name = _get_litellm_model_name(provider, api_model_id)
    args = dict(
        model=model_name,
        messages=messages,
        stream=True,
        stream_options={"include_usage": True},
        api_key=query.apikey.key if query.apikey else (session.aimodel.api_provider.data or {}).get("default_api_key", ""),
    )
    if session.aimodel.supports_reasoning:
        args["reasoning_effort"] = session.reasoning_effort
    if provider in PROVIDER_OPENAI_COMPATIBLE:
        args["api_base"] = session.aimodel.api_provider.url
    if tools:
        args["tools"] = tools
        args["tool_choice"] = "auto"
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
        blocked, reason = battery_gate_blocked(_session.aimodel)
        if blocked:
            raise RateLimitError(reason)

        ratelimit_result = RateLimitChecker.check(_session.aimodel)
        if not ratelimit_result:
            raise Exception("Error in ratelimiter")
        apikey = ratelimit_result.selected_key
        updated = Query.objects.filter(pk=query.pk, status__in=[QueryStatus.WAITING, QueryStatus.FAILURE]).update(apikey=apikey, status=QueryStatus.ACTIVE)
        if not updated:
            raise Exception("Failed to update query to active state")
        query.apikey = apikey
        query.status = QueryStatus.ACTIVE # no need to call save, this was done by .update()

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

        response = run_streaming_query(
            session=_session,
            messages=messages,
            tools=api_tools,
            query=query,
        )
        Query.objects.filter(pk=query.pk).update(status=QueryStatus.SUCCESS if response.status == ResponseStatus.SUCCESS else QueryStatus.FAILURE)
        query.refresh_from_db()
        from runtime.events import publish_model_event
        publish_model_event(query, "update")
        return response

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
