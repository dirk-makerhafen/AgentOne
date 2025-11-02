import time
from openai import OpenAI
from celery import shared_task
import traceback
import json
import random

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

    try:
        messages = llmQuery.compile()
    except Exception as e:
        debugLogEntry = DebugLogEntry(agentInstance=llmQuery.agentInstance, event='exception',
                                      data={"exception": f'{e}\n{traceback.format_exc()}', "llmQuery_id": llmQuery.pk})
        debugLogEntry.save()
        llmQuery.status = LLMQuery.LLMQueryStatusChoices.FAILED
        llmQuery.save()
        llmQuery.agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.ERROR)
        return

    log_raw_query = True
    if log_raw_query:
        debugLogEntry = DebugLogEntry(agentInstance=llmQuery.agentInstance, event='raw_query_messages', data={"messages": messages, "llmQuery_id": llmQuery.id})
        debugLogEntry.save()

    client = OpenAI(api_key=llmQuery.apikey.key, base_url=llmQuery.aimodel.apiProvider.url)
    toolCalls = []
    response_string_full = ""
    firstConversationMessagePart = None

    try:
        if not streaming:
            response = client.chat.completions.create(model=llmQuery.aimodel.name, messages=messages)
            response = json.loads(response.model_dump_json())
            llmResponse = LLMResponse.objects.create(
                agent=llmQuery.agent,
                agentInstance=llmQuery.agentInstance,
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
                    agentInstance=llmQuery.agentInstance,
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

        parts = parse_responsestring(response_string_full)

        for index, part in enumerate(parts):
            if index == 0:
                # If a streaming part exists, update it. Otherwise, create it.
                conversationMessagePart = firstConversationMessagePart
                if not conversationMessagePart:
                     conversationMessagePart = conversationMessage.conversationMessageParts.create(content="", index=0)
                
                conversationMessagePart.content = part["content"]
                conversationMessagePart.tokens = len(part["content"]) // 3.8
                conversationMessagePart.index = index
            else:
                # Create subsequent parts via the manager
                conversationMessagePart = conversationMessage.conversationMessageParts.create(
                    content=part["content"],
                    tokens=len(part["content"]) // 3.8,
                    index=index
                )

            if "tool" in part:
                # Save part to get an ID before creating the related tool call
                conversationMessagePart.save(send_to_client=False)
                
                toolCall = ToolCall.objects.create(
                    function_name=part["tool"],
                    arguments=part["arguments"],
                    conversationMessage=conversationMessage,
                    conversationMessagePart=conversationMessagePart,
                    agent=llmResponse.agent,
                    agentInstance=llmQuery.agentInstance
                )
                toolCalls.append(toolCall)
            
            # Save the final state of the part (with tool call relation if any)
            # This will trigger the broadcast with the correct context.
            conversationMessagePart.save()

        llmQuery.status = LLMQuery.LLMQueryStatusChoices.SUCCESS
        llmQuery.save()

    except Exception as e:
        debugLogEntry = DebugLogEntry(agentInstance=llmQuery.agentInstance, event='exception',
                                      data={"exception": f"{e}\n{traceback.format_exc()}", "llmQuery_id": llmQuery.pk})
        debugLogEntry.save()
        llmQuery.status = LLMQuery.LLMQueryStatusChoices.FAILED
        llmQuery.save()
        llmQuery.agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.ERROR)
        return

    instance = llmQuery.agentInstance
    if not toolCalls:
        decide_next_step(instance)
        return

    if not instance.system or (instance.system and instance.system.status == System.SystemStatusChoices.ONLINE):
        instance.set_status(AgentInstance.AgentInstanceStatusChoices.EXECUTING_TOOLS)
        for toolCall in toolCalls:
            try:
                toolCall.run()
            except Exception as e:
                print(f"Error running tool call {toolCall.id}: {e} {traceback.format_exc()}")
        decide_next_step(instance)
        return

    print(f"Cannot execute tool calls for instance {instance.pk}. Its assigned system is offline or not set.")
    instance.set_status(AgentInstance.AgentInstanceStatusChoices.SYSTEM_OFFLINE)


def decide_next_step(agent_instance):
    agent_instance.refresh_from_db()
    if agent_instance.require_user_interaction:
        agent_instance.set_status(AgentInstance.AgentInstanceStatusChoices.AWAITING_USER_INPUT)
        agent_instance.set_automated_step_count(0)
        return

    if agent_instance.effective_limit_max_automated_steps > 0:
        if agent_instance.automated_step_count < agent_instance.effective_limit_max_automated_steps:
            agent_instance.set_status(AgentInstance.AgentInstanceStatusChoices.IDLE_AUTOMATED)
            agent_instance.set_automated_step_count(agent_instance.automated_step_count + 1)
            agent_instance.start_or_continue()
            return

        agent_instance.set_status(AgentInstance.AgentInstanceStatusChoices.AWAITING_AUTOMATION_CONFIRMATION)
        agent_instance.set_automated_step_count(0)
        return

    agent_instance.set_status(AgentInstance.AgentInstanceStatusChoices.IDLE)
    agent_instance.set_automated_step_count(0)
    agent_instance.save()
