import time
from openai import OpenAI
from celery import shared_task
import traceback
import json
import random
from django.db.models import Q

from agents.models.agent_instance import AgentInstance
from agents.models.conversation_message import ConversationMessage, ConversationMessagePart
from agents.models.debug_log_entry import DebugLogEntry
from agents.models.llm_query import LLMQuery
from agents.models.llm_response import LLMResponse
from systems.models.system import System
from tools.calls.models.tool_call import ToolCall
from collections import defaultdict


@shared_task
def execute_query(llmQuery_id, streaming=False):
    llmQuery = LLMQuery.objects.get(pk=llmQuery_id)
    if not llmQuery:
        return
    agentInstance = llmQuery.agentInstance
    agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.QUERY_ACTIVE)
    agent = llmQuery.agent
    
    llmQuery.apikey = random.choice([x for x in llmQuery.aimodel.apiProvider.apikeys.all()])
    llmQuery.status = LLMQuery.LLMQueryStatusChoices.ACTIVE
    llmQuery.save()
    try:
        messages = llmQuery.compile()
    except Exception as e:
        debugLogEntry = DebugLogEntry(agentInstance=agentInstance, event='exception', data={"exception": f'{e}\n{traceback.format_exc()}', "llmQuery_id": llmQuery.pk})
        debugLogEntry.save()
        llmQuery.status = LLMQuery.LLMQueryStatusChoices.FAILED
        llmQuery.save()
        agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.ERROR)
        return

    from events.event_dispatcher import EventDispatcher

    agentInstance.set_automated_step_count(agentInstance.automated_step_count + 1)


    debugLogEntry = DebugLogEntry(agentInstance=agentInstance, event='raw_query_messages', data={"messages": messages, "llmQuery_id": llmQuery.id})
    debugLogEntry.save()

    EventDispatcher.event_llmquery_pre_execute(agent, agentInstance, llmQuery)

    llmResponse = None
    conversationMessage = None
    try:
        tools = []
        [tools.extend(tool_def.to_llm_schema()) for tool_def in agent.available_tools.all()]
        api_params = {
            "model": llmQuery.aimodel.name,
            "messages": messages,

        }
        if tools:
            api_params.update({
                "tools": tools,
                "tool_choice": "auto"
            })

        client = OpenAI(api_key=llmQuery.apikey.key, base_url=llmQuery.aimodel.apiProvider.url)
        if streaming:
            llmResponse, conversationMessage = run_query_streaming(llmQuery, client, api_params)
        else:
            llmResponse, conversationMessage = run_query_non_streaming(llmQuery, client, api_params)
        
        llmQuery.status = LLMQuery.LLMQueryStatusChoices.SUCCESS
    except Exception as e:
        debugLogEntry = DebugLogEntry(agentInstance=agentInstance, event='exception', data={"exception": f"{e}\n{traceback.format_exc()}", "llmQuery_id": llmQuery.pk})
        debugLogEntry.save()
        llmQuery.status = LLMQuery.LLMQueryStatusChoices.FAILED
        agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.ERROR)
        return
    finally:
        llmQuery.save()
    
    EventDispatcher.event_llmquery_post_execute(agent, agentInstance, llmQuery)

    if llmResponse:
       handle_llmResponse(llmResponse, conversationMessage)

def run_query_non_streaming(llmQuery, client, api_params):
    response = client.chat.completions.create(**api_params)
    response = json.loads(response.model_dump_json())
    llmResponse = LLMResponse.objects.create(
        agent=llmQuery.agent,
        agentInstance=llmQuery.agentInstance,
        llmQuery=llmQuery,
        data=response,
        status=LLMResponse.LLMResponseStatusChoices.SUCCESS
    )
    conversationMessage = ConversationMessage(
        agent=llmResponse.agent,
        agentInstance=llmResponse.agentInstance,
        llmResponse=llmResponse,
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

    return llmResponse, conversationMessage

def run_query_streaming(llmQuery, client, api_params):
    api_params["stream_options"] = {"include_usage": True}
    not_saved = True
    with client.chat.completions.stream(**api_params) as stream:
        llmResponse = LLMResponse.objects.create(
            agent=llmQuery.agent,
            agentInstance=llmQuery.agentInstance,
            llmQuery=llmQuery,
            data={"stream": []},
            status=LLMResponse.LLMResponseStatusChoices.ACTIVE
        )
        conversationMessage = ConversationMessage(
            agent=llmResponse.agent,
            agentInstance=llmResponse.agentInstance,
            llmResponse=llmResponse,
            role='assistant'
        )
        firstConversationMessagePart = ConversationMessagePart(content="", index=0, tokens=0, conversationMessage=conversationMessage)

        buffered_content = ""
        last_save_time = time.time()
        SAVE_INTERVAL = 0.150  # 150ms

        for event in stream:
            event_data = event.model_dump()
            event_data.pop("snapshot", None)
            llmResponse.data["stream"].append(event_data)

            if event.type == "content.delta" and event.delta:
                buffered_content += event.delta
                current_time = time.time()
                if current_time - last_save_time > SAVE_INTERVAL:
                    if buffered_content:
                        if not_saved: 
                            conversationMessage.save()
                            not_saved = False
                        firstConversationMessagePart.content += buffered_content
                        firstConversationMessagePart.save()
                        buffered_content = ""
                    last_save_time = current_time

            if event.type == "chunk" and event.chunk.usage:
                llmResponse.data["usage"] = event.chunk.usage.model_dump()
            elif event.type == "content.done":
                response_string_full = event.content

        if buffered_content:
            if not_saved: 
                conversationMessage.save()
                not_saved = False
            firstConversationMessagePart.content += buffered_content
            firstConversationMessagePart.save()

        llmResponse.status = LLMResponse.LLMResponseStatusChoices.SUCCESS
        llmResponse.save()
    if not_saved: 
        conversationMessage.save()
    return llmResponse, conversationMessage

def handle_llmResponse(llmResponse, conversationMessage):
    from events.event_dispatcher import EventDispatcher

    llmResponse.agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.RESPONSE_PROCESS)
    api_tool_calls = []
    if llmResponse.data.get('stream'):
        tool_call_chunks = defaultdict(lambda: {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
        for event in llmResponse.data['stream']:
            if event.get('type') == 'tool_call.delta':
                delta = event.get('delta', {})
                if delta:
                    index = delta.get('index')
                    if index is not None:
                        chunk = tool_call_chunks[index]
                        if delta.get('id'): chunk['id'] = delta.get('id')
                        if delta.get('function'):
                            if delta['function'].get('name'): chunk['function']['name'] = delta['function']['name']
                            if delta['function'].get('arguments'): chunk['function']['arguments'] += delta['function']['arguments']
        if tool_call_chunks:
            api_tool_calls = [tool_call_chunks[i] for i in sorted(tool_call_chunks.keys())]

    elif llmResponse.data.get('choices'): # Non-streaming responses have the tool_calls array directly in the message
        api_tool_calls = llmResponse.data['choices'][0].get('message', {}).get('tool_calls', [])

    print("api_tool_calls", api_tool_calls)
    tool_calls = []
    firstConversationMessagePart = None
    if api_tool_calls:
        # If the LLM's response contained *only* tool calls and no text content, the initial text part we created will be empty. We should delete it.
        firstConversationMessagePart = conversationMessage.conversationMessageParts.first()
        if firstConversationMessagePart and not firstConversationMessagePart.content.strip():  
            firstConversationMessagePart.delete()
            firstConversationMessagePart = None


        for index, tool_call_data in enumerate(api_tool_calls):
            if not tool_call_data['id']: # fix missing tool call id
                tool_call_data['id'] = f'function-call-{time.time()}{random.random()}'
            
            toolCall = ToolCall.objects.create(
                tool_call_id=tool_call_data['id'],
                function_name=tool_call_data['function']['name'],
                arguments=json.loads(tool_call_data['function']['arguments']),
                conversationMessage=conversationMessage,
                agent=llmResponse.agent,
                agentInstance=llmResponse.agentInstance
            )
            tool_calls.append(toolCall)

    # If a text part was created and still exists (i.e., there was text content), ensure it's saved.
    if firstConversationMessagePart:
        firstConversationMessagePart.save()

    if tool_calls:
        if not llmResponse.agentInstance.system or (llmResponse.agentInstance.system and llmResponse.agentInstance.system.status == System.SystemStatusChoices.ONLINE):
            schedule_tool_calls(llmResponse)
        else:
            llmResponse.agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.SYSTEM_OFFLINE)
    else:
        if (current_task := llmResponse.agentInstance.get_active_task()) :  #current task may be finished
            print("CURRENT TASK MAYBE DONE", current_task, current_task.status)
            current_task.finish(status= "SUCCESS", result = "".join([x.content for x in conversationMessage.conversationMessageParts.all()]))
        

        decide_next_status(conversationMessage)


def schedule_tool_calls(llmResponse):
    llmResponse.agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.TOOLCALLS_PENDING)
    run_tool_calls(llmResponse)

def run_tool_calls(llmResponse):
    llmResponse.agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.TOOLCALLS_ACTIVE)
    conversationMessage =  llmResponse.conversationMessages.first()
    agent = conversationMessage.agent
    agentInstance = conversationMessage.agentInstance
    llmResponse = conversationMessage.llmResponse
    llmQuery = llmResponse.llmQuery
    for toolCall in conversationMessage.toolCalls.all():
        try:
            toolCall.run()
        except Exception as e:
            print(f"Error running tool call {toolCall.id}: {e} {traceback.format_exc()}")
    on_toolcalls_completed(conversationMessage)

def on_toolcalls_completed(conversationMessage):
    decide_next_status(conversationMessage) # later call async


def decide_next_status(conversationMessage):
    from events.event_dispatcher import EventDispatcher
    EventDispatcher.event_conversationMessage_added(conversationMessage.agent, conversationMessage.agentInstance, conversationMessage)
    
    agentInstance = conversationMessage.agentInstance
    agentInstance.refresh_from_db()
    if agentInstance.require_user_interaction:
        agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.AWAITING_USER_INPUT)
    elif agentInstance.effective_limit_max_automated_steps == 0: # automatic steps are  disabls, we need user input next
        agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.AWAITING_USER_INPUT)
    elif agentInstance.automated_step_count >= agentInstance.effective_limit_max_automated_steps:  # automated step LIMIT REACHED, require user confirmation
        agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.AWAITING_USER_INPUT)
    else: # limit not reached, automation enabled
        agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.IDLE)
        if agentInstance.tasks.first(): # is task agent
            if not agentInstance.get_active_task(): # no active task
                agentInstance.process_next_task()
        else: # chat agent, no tasks
            print("# chat agent, no tasks")
            from agents.tasks.create_query import celery_create_query
            celery_create_query.delay(agentInstance.instance_pk)
 
