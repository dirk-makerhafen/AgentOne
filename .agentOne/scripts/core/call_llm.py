"""
Streams the Query to the LLM API and records the Response.
Handles rate limiting, API key selection, and streaming ingestion.
"""

from __future__ import annotations

import json
import time
import traceback
from typing import Any

from runtime.session.session import Session
from server.models.settings import AgentToolCallSyntax
from server.models.queries.query import Query, QueryStatus
from server.models.queries.response import Response, ResponseStatus
from openai import OpenAI
from runtime.rate_limiter import RateLimitChecker, RateLimitError


def run_streaming_query(
    session: Session,
    tools: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    query: Query,
) -> Response:
    """
    Open a streaming chat completion and incrementally save the response.

    Accumulates content, reasoning/thinking tokens, and tool call deltas
    into the Response model. Saves every 150ms for progress visibility.

    Args:
        session:  The active agent session.
        tools:    OpenAI-format tool definitions.
        messages: OpenAI-API-compatible message list from the Query.
        query:    The Query model this response belongs to.

    Returns:
        A saved Response model with content, reasoning, tool_calls,
        token usage, and timing metrics.
    """
    SAVE_INTERVAL = 0.150  # persist progress every 150ms

    last_save_time = time.time()
    first_token_timestamp: float | None = None
    first_reasoning_token_timestamp: float | None = None
    last_reasoning_token_timestamp: float | None = None
    start_timestamp = time.time()

    response = Response.objects.create(
        query=query,
        session_version=query.session_version,
        status=ResponseStatus.ACTIVE,
        tool_calls=[],
    )

    client = OpenAI(
        base_url=session.aimodel.api_provider.url,
        api_key=query.apikey.key if query.apikey else None,
    )

    from server.models.debug_log_entry import DebugLogEntry


    args = dict(
        model=session.aimodel.name,
        messages=messages,
        extra_body={
            "reasoning_effort": session.reasoning_effort,
        },
        stream_options={"include_usage": True},
        stream=True,
    )
    if tools:
        args["tools"] = tools
        args["tool_choice"] = "auto"
    
    DebugLogEntry.objects.create(
        session=session.model,
        event="query",
        data={"query_args": args}
    )

    stream = client.chat.completions.create(**args)

    for event in stream:
        event_data = event.model_dump()
        unknown_chunk = True

        if usage := event_data.get("usage", None):
            unknown_chunk = False
            response.completion_tokens = int(usage.get("completion_tokens", 0))
            response.prompt_tokens = int(usage.get("prompt_tokens", 0))

        choices = event_data.get("choices", [{}])
        if not choices:
            continue

        message_chunk = choices[0].get("delta", {})

        if finish_reason := choices[0].get("finish_reason"):
            unknown_chunk = False
            response.finish_reason = finish_reason

        reasoning_chunk = message_chunk.get("reasoning", None) or message_chunk.get(
            "thinking", None
        )
        if reasoning_chunk:
            if not first_reasoning_token_timestamp:
                first_reasoning_token_timestamp = time.time()
            last_reasoning_token_timestamp = time.time()
            unknown_chunk = False
            response.reasoning += reasoning_chunk

        if content_chunk := message_chunk.get("content", None):
            unknown_chunk = False
            response.content += content_chunk

        if tool_calls_chunk := message_chunk.get("tool_calls", None):
            unknown_chunk = False
            for tool_call in tool_calls_chunk:
                index = tool_call.get("index", 0)
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

    # Parse tool call arguments from JSON string to dict
    for tool_call in response.tool_calls:
        try:
            tool_call["arguments"] = json.loads(tool_call["arguments"])
        except json.JSONDecodeError:
            pass

    # Record timing metrics
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

    if first_token_timestamp and response.finish_reason:
        response.status = ResponseStatus.SUCCESS
    else:
        response.status = ResponseStatus.FAILURE
    response.save()
    return response


def call_llm(session: Session, query: Query) -> Response:
    """
    Send the Query to the LLM and stream the response.

    Handles rate-limit checking and API key selection before calling
    the provider. RateLimitError is caught by AgentTaskRun.apply()
    and transitions to RATE_LIMITED status (no retry budget consumed).

    Args:
        session: The active agent session.
        query:   The Query (built by build_llm_context) to send.

    Returns:
        A Response model containing the streamed LLM output.
    """
    try:
        if not session.aimodel:
            raise Exception("No llm model specified")

        ratelimit_result = RateLimitChecker.check(session.aimodel)
        if not ratelimit_result:
            raise Exception("Error in ratelimiter")
        apikey = ratelimit_result.selected_key
        if not apikey:
            raise Exception("Error in ratelimiter, not api key selected")
        updated = Query.objects.filter(pk=query.pk, status=QueryStatus.WAITING).update(apikey=apikey, status=QueryStatus.ACTIVE)
        if not updated:
            raise Exception("Failed to update query to active state")
        query.apikey = apikey
        query.status = QueryStatus.ACTIVE # no need to call save, this was done by .update()

        messages = query.to_openai_message()
        api_tools: list[dict[str, Any]] = []
        if session.tool_call_syntax == AgentToolCallSyntax.DEFAULT:
            for tool in session.allowedTools:
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
            session=session,
            messages=messages,
            tools=api_tools,
            query=query,
        )
        Query.objects.filter(pk=query.pk).update(status=QueryStatus.SUCCESS if response.status == ResponseStatus.SUCCESS else QueryStatus.FAILURE)
        return response

    except RateLimitError:
        Query.objects.filter(pk=query.pk).update(status=QueryStatus.FAILURE)
        raise

    except Exception:
        Query.objects.filter(pk=query.pk).update(status=QueryStatus.FAILURE)
        from server.models.debug_log_entry import DebugLogEntry

        DebugLogEntry.objects.create(
            session=session.model,
            event="exception",
            data={"exception": traceback.format_exc()},
        )
        raise
