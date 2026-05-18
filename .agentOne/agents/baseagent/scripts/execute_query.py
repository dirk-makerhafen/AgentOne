
import json
import time
import traceback
from registry.task_decorators import task
from runtime.agents.session import Session
from server.models.settings import AgentToolCallSyntax
from server.models.content import GenericContent
from server.models.queries.query import Query, QueryStatus
from server.models.queries.response import Response, ResponseStatus
from openai import OpenAI
from runtime.rate_limiter import RateLimitChecker, RateLimitError


'''
client = OpenAI(api_key=query.apikey.key, base_url=query.aimodel.api_provider.url)
api_response = client.chat.completions.create(**api_params)
session.count_turn()
session.count_unattended_turn()
response = json.loads(api_response.model_dump_json())
response = Response.objects.create(
    query = query,
    session_version = query.session_version,
    status = "SUCCESS",
    completion_tokens = api_response.get("usage", {}).get("completion_tokens", 0),
    prompt_tokens = api_response.get("usage", {}).get("prompt_tokens", 0),
    data = api_response,
)
query.status = QueryStatus.SUCCESS
query.save()
return response


def run_query_non_streaming(query, client, api_params):
    api_response = client.chat.completions.create(**api_params)
    api_response_data = json.loads(api_response.model_dump_json())
    response = Response.objects.create(
        agent=llmQuery.agent,
        agentInstance=llmQuery.agentInstance,
        llmQuery=llmQuery,
        data=api_response_data,
        status=Response.LLMResponseStatusChoices.SUCCESS
    )
    conversationMessage = Message(
        agent=response.agent,
        agentInstance=response.agentInstance,
        llmResponse=response,
        role='assistant',
    )
    response_string_full = (response['choices'][0].get('message', "") if len(response['choices']) > 0 else {}).get("content", "")
    if response_string_full is not None:
        print("response_string_full", response_string_full)
        conversationMessage.save()
        firstConversationMessagePart = conversationMessage.conversationMessageParts.create(content=response_string_full, index=0, tokens=0)
        firstConversationMessagePart.save()
    else:
        conversationMessage.save()

    return response, conversationMessage

'''



def run_streaming_query(url, api_key, model, tools, messages, extra_body, query):

    SAVE_INTERVAL = 0.150  # 150ms

    response = Response.objects.create(
        query = query,
        session_version = query.session_version,
        status = ResponseStatus.ACTIVE,
        tool_calls = [],
    )
    last_save_time = time.time()


    first_token_timestamp = None
    first_reasoning_token_timestamp = None
    last_reasoning_token_timestamp = None
    start_timestamp = time.time()

    client = OpenAI(base_url=url, api_key=api_key)
    stream = client.chat.completions.create(
        model = model, 
        messages = messages, 
        extra_body = extra_body, 
        stream_options = {"include_usage": True}, 
        stream = True,
        tools = tools, 
        tool_choice = "auto",
    )

    for event in stream:
        event_data = event.model_dump()
        #print(event_data )
        unknown_chunk = True

        if usage := event_data.get("usage", None):
            unknown_chunk = False
            response.completion_tokens = int(usage.get("completion_tokens", 0))
            response.prompt_tokens = int(usage.get("prompt_tokens", 0))
    
        choices = event_data.get("choices", [{}])
        if not choices:
            continue

        message_chunk = choices[0].get("delta", {})
        #print("message_chunk", message_chunk)

        if finish_reason := choices[0].get("finish_reason"):
            unknown_chunk = False
            response.finish_reason = finish_reason

        if chunk := message_chunk.get("reasoning", None) or  message_chunk.get("thinking", None):
            if not first_reasoning_token_timestamp:
                first_reasoning_token_timestamp = time.time()
            last_reasoning_token_timestamp = time.time()
            unknown_chunk = False
            response.reasoning += chunk

        if chunk := message_chunk.get("content", None):
            unknown_chunk = False
            response.content += chunk

        if tool_calls := message_chunk.get("tool_calls", None):
            unknown_chunk = False
            for tool_call in tool_calls:
                index = tool_call.get("index", 0)
                if not response.tool_calls:
                    response.tool_calls = []
                while len(response.tool_calls) <= index:
                    response.tool_calls.append( { "name": "", "arguments": "", "id": "", "index": len(response.tool_calls )})
                if tool_call_id := tool_call.get("id"):
                    response.tool_calls[index]["id"] +=  tool_call_id
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
            last_save_time =  time.time()

    end_timestamp = time.time()

    for tool_call in response.tool_calls:
        try:
            tool_call["arguments"] = json.loads(tool_call["arguments"])
        except json.JSONDecodeError:
            pass

    # log timeings
    response.time_to_first_token = 0
    response.token_generation_time = 0
    response.reasoning_time = 0
    response.total_time =  end_timestamp - start_timestamp
    if first_token_timestamp:
        response.time_to_first_token = first_token_timestamp  - start_timestamp 
        response.token_generation_time = end_timestamp - first_token_timestamp    
    if first_reasoning_token_timestamp and last_reasoning_token_timestamp:
        response.reasoning_time = last_reasoning_token_timestamp - first_reasoning_token_timestamp

    if first_token_timestamp and response.finish_reason:
        response.status = ResponseStatus.SUCCESS
    else:
        response.status = ResponseStatus.FAILURE
    response.save()
    return response
    


@task()
def execute_query(session: Session, query: Query) -> Response:

    # --- Rate limit check + key selection ---
    # This is the only place rate limits are enforced.
    # RateLimitError is caught separately in AgentTaskRun.apply() and sets
    # status=RATE_LIMITED rather than FAILURE — no retry budget consumed.

    ratelimit_result = RateLimitChecker.check(session.aimodel)
    query.apikey = ratelimit_result.selected_key
    query.status = QueryStatus.ACTIVE
    query.save()

    try:
        messages = query.compile()
        tool_call_syntax = session.tool_call_syntax
        api_tools = []

        if tool_call_syntax == AgentToolCallSyntax.DEFAULT:
            for allowedToolName in session.allowedToolNames:
                allowed_tool = session.agent.get_allowed_tool(allowedToolName)
                if not allowed_tool:
                    raise Exception(f"Tool '{allowedToolName}' not found")
                if not allowed_tool.task_definition:
                    raise Exception(f"No Taskdefinition for '{allowedToolName}' found")
                api_tools.append({
                    "type": "function",
                    "function": {
                        "name": allowed_tool.task_definition.name,
                        "description": allowed_tool.description,
                        "parameters": allowed_tool.function_schema,
                    }
                })

        response = run_streaming_query(
            url = session.aimodel.api_provider.url, 
            api_key = query.apikey.key, 
            model =  session.aimodel.name,
            messages = messages,
            tools = api_tools,
            query = query,
            extra_body = {
                "reasoning_effort":  session.reasoning_effort,
            },
        )
        return response
        
    except RateLimitError:
        query.status = QueryStatus.FAILURE
        query.save()
        # Don't touch query.status — the run will be re-dispatched by the
        # scheduler and _execute_query will be called again from scratch.
        raise  # re-raise so apply() can catch it by type

    except Exception:
        query.status = QueryStatus.FAILURE
        query.save()
        from server.models.debug_log_entry import DebugLogEntry
        DebugLogEntry.objects.create(
            session=session.model,
            event='exception',
            data={"exception": traceback.format_exc()},
        )
        raise

