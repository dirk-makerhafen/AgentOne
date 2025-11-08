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
from tools.calls.tool_parser import parse_responsestring


@shared_task
def execute_query(llmQuery_id, streaming=True):
    llmQuery = LLMQuery.objects.get(pk=llmQuery_id)
    if not llmQuery:
        return

    llmQuery.apikey = random.choice([x for x in llmQuery.aimodel.apiProvider.apikeys.all()])
    llmQuery.status = LLMQuery.LLMQueryStatusChoices.ACTIVE
    llmQuery.save()
    agentInstance = llmQuery.agentInstance
    try:
        messages = llmQuery.compile()
    except Exception as e:
        debugLogEntry = DebugLogEntry(agentInstance=agentInstance, event='exception',
                                      data={"exception": f'{e}\n{traceback.format_exc()}', "llmQuery_id": llmQuery.pk})
        debugLogEntry.save()
        llmQuery.status = LLMQuery.LLMQueryStatusChoices.FAILED
        llmQuery.save()
        agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.ERROR)
        return

    log_raw_query = True
    if log_raw_query:
        debugLogEntry = DebugLogEntry(agentInstance=agentInstance, event='raw_query_messages', data={"messages": messages, "llmQuery_id": llmQuery.id})
        debugLogEntry.save()

    client = OpenAI(api_key=llmQuery.apikey.key, base_url=llmQuery.aimodel.apiProvider.url)
    toolCalls = []
    llmResponse = None
    response_string_full = ""
    conversationMessage = None
    firstConversationMessagePart = None
    from agents.models.agentevents import EventDispatcher

    try:
        EventDispatcher.event_llmquery_pre_execute( llmQuery.agent, agentInstance, llmQuery)

        if not streaming:
            response = client.chat.completions.create(model=llmQuery.aimodel.name, messages=messages)
            response = json.loads(response.model_dump_json())
            llmResponse = LLMResponse.objects.create(
                agent=llmQuery.agent,
                agentInstance=agentInstance,
                llmQuery=llmQuery,
                data=response,
                status=LLMResponse.LLMResponseStatusChoices.SUCCESS
            )
            conversationMessage = ConversationMessage.objects.create(
                agent=llmResponse.agent,
                agentInstance=llmResponse.agentInstance,
                llmResponse=llmResponse,
                role='assistant',
            )
            response_string_full = (response['choices'][0].get('message', "") if len(response['choices']) > 0 else {}).get("content", "")
        else:
            with client.chat.completions.stream(model=llmQuery.aimodel.name, messages=messages,
                                               stream_options={"include_usage": True}) as stream:
                llmResponse = LLMResponse.objects.create(
                    agent=llmQuery.agent,
                    agentInstance=agentInstance,
                    llmQuery=llmQuery,
                    data={"stream": []},
                    status=LLMResponse.LLMResponseStatusChoices.ACTIVE
                )

                conversationMessage = ConversationMessage.objects.create(
                    agent=llmResponse.agent,
                    agentInstance=llmResponse.agentInstance,
                    llmResponse=llmResponse,
                    role='assistant'
                )

                # Create the initial part for streaming via the manager
                firstConversationMessagePart = conversationMessage.conversationMessageParts.create(content="", index=0, tokens=0)

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
                                firstConversationMessagePart.content += buffered_content
                                firstConversationMessagePart.save()
                                buffered_content = ""
                            last_save_time = current_time

                    if event.type == "chunk" and event.chunk.usage:
                        llmResponse.data["usage"] = event.chunk.usage.model_dump()
                    elif event.type == "content.done":
                        response_string_full = event.content

                if buffered_content:
                    firstConversationMessagePart.content += buffered_content
                    firstConversationMessagePart.save()

                llmResponse.status = LLMResponse.LLMResponseStatusChoices.SUCCESS
                llmResponse.save()

        EventDispatcher.event_llmresponse_pre_parse(llmQuery.agent, agentInstance, llmQuery, llmResponse, conversationMessage)
        parts = parse_responsestring(response_string_full)

        for index, part in enumerate(parts):
            conversationMessagePart = firstConversationMessagePart if firstConversationMessagePart and index==0 else ConversationMessagePart()
            conversationMessagePart.content = part["content"]
            conversationMessagePart.tokens = len(part["content"]) // 3.8
            conversationMessagePart.index = index
            conversationMessagePart.conversationMessage = conversationMessage
            if "tool" in part:
                # Save part to get an ID before creating the related tool call                
                conversationMessagePart.save(send_to_client=False)
                toolCall = ToolCall.objects.create(
                    function_name=part["tool"],
                    arguments=part["arguments"],
                    conversationMessage=conversationMessage,
                    conversationMessagePart=conversationMessagePart,
                    agent=llmResponse.agent,
                    agentInstance=agentInstance
                )
                toolCalls.append(toolCall)
            conversationMessagePart.save()
        EventDispatcher.event_llmresponse_post_parse(llmQuery.agent, agentInstance, llmQuery, llmResponse, conversationMessage)
        
        EventDispatcher.event_conversationMessage_added(llmQuery.agent, agentInstance, conversationMessage)
        llmQuery.status = LLMQuery.LLMQueryStatusChoices.SUCCESS
        llmQuery.save()
        EventDispatcher.event_llmquery_successfull(llmQuery.agent, agentInstance, llmQuery, llmResponse, conversationMessage)

    except Exception as e:
        debugLogEntry = DebugLogEntry(agentInstance=agentInstance, event='exception', data={"exception": f"{e}\n{traceback.format_exc()}", "llmQuery_id": llmQuery.pk})
        debugLogEntry.save()
        llmQuery.status = LLMQuery.LLMQueryStatusChoices.FAILED
        llmQuery.save()
        agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.ERROR)
        EventDispatcher.event_llmquery_failed(llmQuery.agent, agentInstance, llmQuery, llmResponse, conversationMessage)
        return

    try:
        decide_next = True
        if not toolCalls:
            pass
        elif not agentInstance.system or (agentInstance.system and agentInstance.system.status == System.SystemStatusChoices.ONLINE):
            agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.EXECUTING_TOOLS)
            EventDispatcher.event_llmresponse_pre_tool_calls(llmQuery.agent, agentInstance, llmQuery, llmResponse, conversationMessage)
            for toolCall in toolCalls:
                EventDispatcher.event_llmresponse_pre_tool_call(llmQuery.agent, agentInstance, llmQuery, llmResponse, conversationMessage, toolCall)
                try:
                    toolCall.run()
                except Exception as e:
                    print(f"Error running tool call {toolCall.id}: {e} {traceback.format_exc()}")
                EventDispatcher.event_llmresponse_post_tool_call(llmQuery.agent, agentInstance, llmQuery, llmResponse, conversationMessage, toolCall)
            EventDispatcher.event_llmresponse_post_tool_calls(llmQuery.agent, agentInstance, llmQuery, llmResponse, conversationMessage)
        else:
            decide_next = False
            agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.SYSTEM_OFFLINE)
        
        if decide_next:
            agentInstance.refresh_from_db()
            if agentInstance.require_user_interaction:
                agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.AWAITING_USER_INPUT)
                agentInstance.set_automated_step_count(0)
            elif agentInstance.effective_limit_max_automated_steps > 0:
                if agentInstance.automated_step_count < agentInstance.effective_limit_max_automated_steps:
                    agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.IDLE_AUTOMATED)
                    agentInstance.set_automated_step_count(agentInstance.automated_step_count + 1)
                else:
                    agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.AWAITING_AUTOMATION_CONFIRMATION)
                    agentInstance.set_automated_step_count(0)
            else:
                agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.IDLE)
                agentInstance.set_automated_step_count(0)

        EventDispatcher.event_llmresponse_finished(llmQuery.agent, agentInstance, llmQuery, llmResponse, conversationMessage)
        if agentInstance.status == AgentInstance.AgentInstanceStatusChoices.IDLE_AUTOMATED:
            agentInstance.start_or_continue()

    except Exception as e:
        debugLogEntry = DebugLogEntry(agentInstance=agentInstance, event='exception', data={"exception": f"{e}\n{traceback.format_exc()}", "llmQuery_id": llmQuery.pk})
        debugLogEntry.save()


