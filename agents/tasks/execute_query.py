import time
from openai import OpenAI
from celery import shared_task
import traceback
import json
import random

from agents.models.agent_instance import AgentInstance
from agents.models.conversation_message import ConversationMessage
from agents.models.debug_log_entry import DebugLogEntry
from agents.models.llm_query import LLMQuery
from agents.models.llm_response import LLMResponse
from systems.models.system import System
from tools.calls.models.tool_call import ToolCall
from tools.calls.tool_parser import parse_responsestring


@shared_task
def execute_query(llmQuery_id, streaming=True  ):
    llmQuery = LLMQuery.objects.get(pk=llmQuery_id)
    print("execute_query %s" % llmQuery)
    if not llmQuery:
        return 

    llmQuery.apikey = random.choice([x for x in llmQuery.aimodel.apiProvider.apikeys.all()])
    llmQuery.status = LLMQuery.LLMQueryStatusChoices.ACTIVE
    llmQuery.save()

    try:
        messages = llmQuery.compile()
    except Exception as e:
        debugLogEntry = DebugLogEntry(agentInstance = llmQuery.agentInstance, event = 'exception', data = {"exception": f'{e}\n{traceback.format_exc()}', "llmQuery_id": llmQuery.pk })
        debugLogEntry.save()
        llmQuery.status = LLMQuery.LLMQueryStatusChoices.FAILED
        llmQuery.save()
        llmQuery.agentInstance.status = AgentInstance.AgentInstanceStatusChoices.ERROR
        llmQuery.agentInstance.save()
        return

    log_raw_query = True
    if log_raw_query:
        debugLogEntry = DebugLogEntry(agentInstance = llmQuery.agentInstance, event = 'raw_query_messages', data = {"messages": messages, "llmQuery_id": llmQuery.id})
        debugLogEntry.save()

    client = OpenAI(api_key=llmQuery.apikey.key, base_url=llmQuery.aimodel.apiProvider.url)
    toolCalls = []
    response_string_full = ""
    try:
        if not streaming:
            response = client.chat.completions.create(model=llmQuery.aimodel.name, messages=messages)
            response = json.loads(response.model_dump_json())   
            llmResponse = LLMResponse()
            llmResponse.agent = llmQuery.agent
            llmResponse.agentInstance = llmQuery.agentInstance
            llmResponse.llmQuery = llmQuery
            llmResponse.data = response
            llmResponse.status = LLMResponse.LLMResponseStatusChoices.SUCCESS
            llmResponse.save()
            conversationMessage = ConversationMessage()
            conversationMessage.agent = llmResponse.agent
            conversationMessage.agentInstance = llmResponse.agentInstance
            conversationMessage.llmResponse = llmResponse
            conversationMessage.role = 'assistant'
            conversationMessage.save(send_to_client=False)
            response_string_full = (response['choices'][0].get('message', "") if len(response['choices']) > 0 else {}).get("content", "")
        else:
            with client.chat.completions.stream(model=llmQuery.aimodel.name, messages=messages, stream_options= {"include_usage": True}) as stream:
                llmResponse = LLMResponse()
                llmResponse.agent = llmQuery.agent
                llmResponse.agentInstance = llmQuery.agentInstance
                llmResponse.llmQuery = llmQuery
                llmResponse.data = {"stream":[]}
                llmResponse.status =  LLMResponse.LLMResponseStatusChoices.ACTIVE
                llmResponse.save()

                conversationMessage = ConversationMessage()
                conversationMessage.agent = llmResponse.agent
                conversationMessage.agentInstance = llmResponse.agentInstance
                conversationMessage.llmResponse = llmResponse
                conversationMessage.role = 'assistant'
                conversationMessage.data = {"parts":[{"content":""}]}
                conversationMessage.save()

                buffered_content = ""
                last_save_time = time.time()
                SAVE_INTERVAL = 0.1  # 100ms

                for event in stream:
                    event_data = event.model_dump()
                    event_data.pop("snapshot", None)  # remove snapshot if present
                    llmResponse.data["stream"].append(event_data)
                    
                    if event.type == "content.delta" and event.delta:
                        buffered_content += event.delta
                        current_time = time.time()
                        if current_time - last_save_time > SAVE_INTERVAL:
                            if buffered_content:
                                conversationMessage.data["parts"][0]["content"] += buffered_content
                                conversationMessage.save()
                                buffered_content = ""
                            last_save_time = current_time
                    
                    if event.type == "chunk" and event.chunk.usage:
                        llmResponse.data["usage"] = event.chunk.usage.model_dump()
                    elif event.type == "content.done":
                        response_string_full = event.content

                # Save any remaining buffered content
                if buffered_content:
                    conversationMessage.data["parts"][0]["content"] += buffered_content
                    conversationMessage.save()

                llmResponse.status =  LLMResponse.LLMResponseStatusChoices.SUCCESS
                llmResponse.save()

        parts = parse_responsestring(response_string_full)

        for part in parts:
            if "tool" in part:
                toolCall = ToolCall()
                toolCall.function_name = part["tool"]
                toolCall.arguments = part["arguments"]
                toolCall.conversationMessage = conversationMessage
                toolCall.agent = llmResponse.agent
                toolCall.agentInstance = llmQuery.agentInstance
                toolCall.save()
                part["tcId"] = toolCall.id
                toolCalls.append(toolCall)

        conversationMessage.data["parts"] = parts
        conversationMessage.save()
        llmQuery.status = LLMQuery.LLMQueryStatusChoices.SUCCESS
        llmQuery.save()

    except Exception as e:
        debugLogEntry = DebugLogEntry(agentInstance = llmQuery.agentInstance, event = 'exception', data = {"exception": f"{e}\n{traceback.format_exc()}", "llmQuery_id": llmQuery.pk })
        debugLogEntry.save()
        llmQuery.status = LLMQuery.LLMQueryStatusChoices.FAILED
        llmQuery.save()
        llmQuery.agentInstance.status = AgentInstance.AgentInstanceStatusChoices.ERROR
        llmQuery.agentInstance.save()
        return # Stop execution

    instance = llmQuery.agentInstance
    if not toolCalls:
        decide_next_step(instance)
        return
    
    if not instance.system  or (instance.system and instance.system.status == System.SystemStatusChoices.ONLINE):
        # Set status to EXECUTING_TOOLS before running them
        instance.status = AgentInstance.AgentInstanceStatusChoices.EXECUTING_TOOLS
        instance.save()
        for toolCall in toolCalls:
            try:
                toolCall.run()
            except Exception as e:
                print(f"Error running tool call {toolCall.id}: {e}")
        decide_next_step(instance)
        return 
    
    print(f"Cannot execute tool calls for instance {instance.pk}. Its assigned system is offline or not set.")
    instance.status = AgentInstance.AgentInstanceStatusChoices.SYSTEM_OFFLINE
    instance.save()


def decide_next_step(agent_instance):
    """
    The core of the new state machine. Determines the agent's next status after a cycle.
    A cycle is defined as one LLM query and the execution of any resulting tool calls.
    """
    # The `await_user_input` tool sets this flag. If it's true, we must wait.
    if agent_instance.require_user_interaction:
        agent_instance.status = AgentInstance.AgentInstanceStatusChoices.AWAITING_USER_INPUT
        agent_instance.automated_step_count = 0
        agent_instance.save()
        return  # Stop the loop and wait.

    # If we are not waiting for a user, check if we can and should continue automatically.
    if agent_instance.limit_max_automated_steps > 0:
        if agent_instance.automated_step_count < agent_instance.limit_max_automated_steps:
            agent_instance.status = AgentInstance.AgentInstanceStatusChoices.IDLE_AUTOMATED
            agent_instance.automated_step_count += 1
            agent_instance.save()
            agent_instance.start_or_continue()  # Trigger the next automated cycle.
            return 
        # has reached its limit, or the task is complete.
        # For now, we default to IDLE. A future tool could set a 'FINISHED' state.
        agent_instance.status = AgentInstance.AgentInstanceStatusChoices.AWAITING_USER_INPUT
        agent_instance.automated_step_count = 0  # Reset counter
        agent_instance.save()
        return 
    
    # If automation is disabled, 
    agent_instance.status = AgentInstance.AgentInstanceStatusChoices.IDLE
    agent_instance.automated_step_count = 0  # Reset counter, just in case
    agent_instance.save()


