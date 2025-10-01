from datetime import datetime
import time
from openai import OpenAI
from celery import shared_task
import traceback
import json
import random
from agent.models.llm import LLMQuery, LLMResponse
from agent.models.conversation import ConversationMessage
from agent.models.agent import  AgentInstance
from agent.models.debug import DebugLogEntry
from common.models import PromptString
from tools_common.models import ToolCall
from dashboard.tasks import send_object_to_clients
from tools_common.tool_parser import extract_tool_call_parts
from tools_filesystem.fsutils import get_relative_path
from tools_filesystem.models import FsLogEntry
from agent.history_limiter import HistoryLimiter
from tools_subscriptions.models import ToolSubscription

@shared_task
def celery_create_query(agentinstance_id):
    agentInstance = AgentInstance.objects.get(instance_pk=agentinstance_id)
    agentInstance.status = 'THINKING'
    agentInstance.save()

    try:
        messages = []
        systemPrompt = PromptString.get_template(agentInstance=agentInstance, source="Agent", key="System")
        toolInstructions = PromptString.get_template(agentInstance=agentInstance, source="Tools.Common", key="Instructions")
        outputFormat = PromptString.get_template(agentInstance=agentInstance, source="Agent", key="OutputFormat")
        outputFormatReminder = PromptString.get_template(agentInstance=agentInstance, source="Agent", key="OutputFormatReminder")
        agentDescription = PromptString.get_template(agentInstance=agentInstance, source="Agent", key="Description")
        
        messages.append({"role": "system", "parts": [{
                "tags": ["Prompts", "System"] ,
                'tpId': systemPrompt.id, 
                'data': { 'workingdir': agentInstance.workingdir, 'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'current_timestamp': int(time.time())},
        }]})

        messages.append({"role": "system", "parts": [{
            "tags": ["Prompts", "OutputRules"],
            'tpId': outputFormat.id, 
        }]})

        messages.append({"role": "user", "parts": [{
                "tags": ["Prompts", "MainInstructions"] ,
                'tpId': agentDescription.id, 
        }]})

        messages.append({"role": "user", "parts": [{
                "tags": ["Prompts", "ToolInstructions"] ,
                'tpId': toolInstructions.id, 
        }]})

        toolheaderparts = []
        for tool in agentInstance.available_tools:
            toolheaderparts.extend(tool(agentInstance).get_header_parts())
        messages.append({"role": "user", "parts": toolheaderparts })

        toolcontentparts = []
        for tool in agentInstance.available_tools:
            toolcontentparts.extend(tool(agentInstance).get_content_parts())
        messages.append({"role": "user", "parts": toolcontentparts })

        # Execute active tool subscriptions and inject their output into the context
        subscription_parts = []
        subscriptions = ToolSubscription.objects.filter(agentInstance=agentInstance, is_active=True)
        if subscriptions:
            try:
                subscriptionResultInjectionTemplate = PromptString.get_template(agentInstance=agentInstance, source="Tools.Subscription", key="SubscriptionResultInjection")
                for subscription in subscriptions:
                    try:
                        tool_function = agentInstance.get_tool_function(subscription.tool_name)
                        if tool_function:
                            # We don't want the subscription execution to create another subscription, so we force one-shot mode.
                            args = subscription.arguments
                            if 'mode' in args:
                                args['mode'] = 'one-shot' 
                            
                            success, result = tool_function['callable'](**args)
                            
                            # Consolidate output from stdout or other result fields
                            output = result.get('stdout', '') or result.get('content', '')
                            if result.get('stderr'):
                                output += f"\nSTDERR:\n{result.get('stderr')}"

                            subscription_parts.append({
                                'tpId': subscriptionResultInjectionTemplate.pk,
                                "tags": ["Tool", "Subscription", subscription.tool_name],
                                'data': {
                                    'subscription_id': subscription.subscription_id,
                                    'tool_name': subscription.tool_name,
                                    'arguments': {k: v for k, v in subscription.arguments.items() if k != 'source'},
                                    'output': output.strip(),
                                    'status': 'success' if success else 'failed'
                                }
                            })
                    except Exception as e:
                        # Log the error but do not crash the entire query generation process
                        debugLogEntry = DebugLogEntry(agentInstance=agentInstance, event='exception', data={"exception": f'Error executing subscription {subscription.id}: {e}\n{traceback.format_exc()}'})
                        debugLogEntry.save()
                if subscription_parts:
                    messages.append({'role': 'user', 'parts': subscription_parts})
            except PromptString.DoesNotExist:
                debugLogEntry = DebugLogEntry(agentInstance=agentInstance, event='exception', data={"exception": "SubscriptionResultInjection prompt template not found. Subscriptions will not be executed."})
                debugLogEntry.save()


        cmessages = get_chat_messages(agentInstance=agentInstance)
        messages.extend(cmessages)

        reminder_props = {
            "chat_forget":   random.random() < 1/3, 
            "memory_forget": random.random() < 1/5, 
            "st_tracks":     random.random() < 1/5, 
            "mt_tracks":     random.random() < 1/50, 
            "lt_tracks":     random.random() < 1/100,
            "st2mt":     random.random() < 1/50, 
            "mt2lt":     random.random() < 1/100, 
        }
        if True in reminder_props.values():
            messages.append({"role": "user", "parts": [{
                "tags": ["Prompts", "OutputRules"],
                'tpId': outputFormatReminder.id, 
                'data': reminder_props
            }]})
            
        llmQuery = LLMQuery(agent=agentInstance.agent, agentInstance=agentInstance, model=agentInstance.model if agentInstance.model else agentInstance.agent.model)
        llmQuery.messages = messages
        llmQuery.save()
        execute_query(llmQuery)    # not celery for now, keep it that way.
    except Exception as e:
        print(e)
        debugLogEntry = DebugLogEntry(agentInstance = agentInstance, event = 'exception', data = {"exception": f'{e}\n{traceback.format_exc()}'})
        debugLogEntry.save() 
        agentInstance.status = 'ERROR'
        agentInstance.save()

      
def get_chat_messages(agentInstance):
    cmessages = []
    limit = agentInstance.limit_max_conversation_messages

    pinned_messages = agentInstance.conversationMessages.filter(hide_from_context=False, pin_to_context=True).order_by('created_at').all()
    recent_nonpinned_messages = agentInstance.conversationMessages.filter(hide_from_context=False, pin_to_context=False).order_by('-created_at').all()[:limit]
    combined_messages = list(pinned_messages) + list(recent_nonpinned_messages)
    conversationMessages = sorted({msg.id: msg for msg in combined_messages}.values(), key=lambda msg: msg.created_at)

    fs_entries = agentInstance.filesystemTool.get_loaded_items(refresh_from_disk=True)
    all_loaded_paths = [e.path for e in fs_entries]
    all_loaded_paths.extend([get_relative_path(agentInstance.workingdir, x) for x in all_loaded_paths])
    all_loaded_paths = set(all_loaded_paths)

    all_entries = conversationMessages + fs_entries
    all_entries.sort(key=lambda x: x.created_at, reverse=True) # Sort descending for HistoryLimiter processing

    # Collect history limiting rule templates from all available tools
    tool_call_rule_templates = []
    for tool_class in agentInstance.available_tools:
        tool_instance = tool_class(agentInstance)
        if hasattr(tool_instance, 'get_history_limiting_rules'):
            tool_call_rule_templates.extend(tool_instance.get_history_limiting_rules())

    limiter = HistoryLimiter(agentInstance, all_entries, all_loaded_paths, tool_call_rule_templates)
    
    resultInjectionTemplate = PromptString.get_template(agentInstance=agentInstance, source="Tools.Common", key="ResultInjection")
    filesystemInjectionTemplate = PromptString.get_template(agentInstance=agentInstance, source="Tools.Filesystem", key="ContentInjection")

    for entry in all_entries:
        if type(entry) == ConversationMessage:
            if entry.hide_from_context: # or not (entry.pin_to_context or entry in conversationMessages):
                continue

            msg_parts = []
            tool_result_parts = []

            for index, conversationMessagePart in enumerate(entry.data.get("parts",[])):
                if conversationMessagePart.get("content","").strip() == "":
                    continue

                tcId = conversationMessagePart.get('tcId', conversationMessagePart.get("toolCall__id", None)) 
                if not tcId:
                    msg_parts.append({"cmId": entry.id, "pnr": index, "tags": ["ChatMessage", f"{entry.role}"], })
                    continue

                toolCall = ToolCall.objects.get(id=tcId)
                if limiter.is_tool_call_limited(toolCall, entry):
                    continue

                msg_parts.append({
                    "tags": ["Tool",  "FsTool" if toolCall.function_name.startswith("fs_") else "MemoryTool" if toolCall.function_name.startswith("memory_") else f"{toolCall.function_name}", "ToolCall", toolCall.function_name],
                    "cmId": entry.id, 
                    "tcId": toolCall.id, 
                    "pnr": index
                })
                
                if toolCall.function_name.startswith("memory_") and toolCall.status == "success":
                    continue

                toolResponse = toolCall.toolResponses.last()
                tool_result_parts.append({
                    "tcId": toolCall.id, 
                    "trId": toolResponse.id if toolResponse else None, 
                    "tpId": resultInjectionTemplate.pk,
                    "tags": ["Tool", "FsTool" if toolCall.function_name.startswith("fs_") else "MemoryTool" if toolCall.function_name.startswith("memory_") else f"{toolCall.function_name}", "ToolResult"],
                    'data': {
                        'function_name': toolCall.function_name, 
                        'arguments': {k: v for k, v in toolCall.arguments.items() if k in ['path', 'action', 'track', 'layer', 'index', "subscription_id"]}, 
                        'status': toolCall.status
                    }
                })

            if len(tool_result_parts) > 0:
                cmessages.append({'role': 'user', 'parts': tool_result_parts, 'warn_forget': limiter.is_general_message_limited('messages_dont_warn_forget', entry)})

            if len(msg_parts) > 0:
                cmessages.append({'role': entry.role, 'parts': msg_parts, 'warn_forget': limiter.is_general_message_limited('messages_dont_warn_forget', entry)})

        elif type(entry) == FsLogEntry:
            cmessages.append({'role': "user", 'parts': [{
                'tpId':  filesystemInjectionTemplate.pk,
                "tags": ["Tool", "FsTool", 'Loaded', 'Directories' if entry.is_directory else 'Files'],
                'data': {
                    "is_directory":  entry.is_directory,
                    "refreshed_from_fs": entry.action == "refresh",
                    "exist_on_fs": entry.exists_on_fs,
                    'path': get_relative_path(agentInstance.workingdir, entry.path),
                    'fs_content_type': f'{entry.__class__.__name__}',
                    'fs_content_id': f'{entry.id}',
                    'load_mode': entry.load_mode,
                },
            }]})

    cmessages = list(reversed(cmessages))
    return cmessages


def execute_query(llmQuery, streaming=True  ):
    print("execute_query %s" % llmQuery)
    if not llmQuery:
        return 

    llmQuery.apikey = random.choice([x for x in llmQuery.model.apiProvider.apikeys.all()])
    llmQuery.status = "active"
    llmQuery.save()

    try:
        messages = llmQuery.compile()
    except Exception as e:
        debugLogEntry = DebugLogEntry(agentInstance = llmQuery.agentInstance, event = 'exception', data = {"exception": f'{e}\n{traceback.format_exc()}', "llmQuery_id": llmQuery.pk })
        debugLogEntry.save()
        llmQuery.status = "failed"
        llmQuery.save()
        llmQuery.agentInstance.status = 'ERROR'
        llmQuery.agentInstance.save()
        return

    log_raw_query = True
    if log_raw_query:
        debugLogEntry = DebugLogEntry(agentInstance = llmQuery.agentInstance, event = 'raw_query_messages', data = {"messages": messages, "llmQuery_id": llmQuery.id})
        debugLogEntry.save()

    client = OpenAI(api_key=llmQuery.apikey.key, base_url=llmQuery.model.apiProvider.url)
    toolCalls = []
    response_string_full = ""
    try:
        if not streaming:
            response = client.chat.completions.create(model=llmQuery.model.name, messages=messages)
            response = json.loads(response.model_dump_json())   
            llmResponse = LLMResponse()
            llmResponse.agent = llmQuery.agent
            llmResponse.agentInstance = llmQuery.agentInstance
            llmResponse.llmQuery = llmQuery
            llmResponse.data = response
            llmResponse.status = "success"
            llmResponse.save()
            conversationMessage = ConversationMessage()
            conversationMessage.agent = llmResponse.agent
            conversationMessage.agentInstance = llmResponse.agentInstance
            conversationMessage.llmResponse = llmResponse
            conversationMessage.role = 'assistant'
            conversationMessage.save(send_to_client=False)
            response_string_full = (response['choices'][0].get('message', "") if len(response['choices']) > 0 else {}).get("content", "")
        else:
            with client.chat.completions.stream(model=llmQuery.model.name, messages=messages, stream_options= {"include_usage": True}) as stream:
                llmResponse = LLMResponse()
                llmResponse.agent = llmQuery.agent
                llmResponse.agentInstance = llmQuery.agentInstance
                llmResponse.llmQuery = llmQuery
                llmResponse.data = {"stream":[]}
                llmResponse.status = "active"
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

                llmResponse.status = "success"
                llmResponse.save()

        parts = extract_tool_call_parts(response_string_full)

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
        llmQuery.status = "success"
        llmQuery.save()

    except Exception as e:
        debugLogEntry = DebugLogEntry(agentInstance = llmQuery.agentInstance, event = 'exception', data = {"exception": f"{e}\n{traceback.format_exc()}", "llmQuery_id": llmQuery.pk })
        debugLogEntry.save()
        llmQuery.status = "failed"
        llmQuery.save()
        llmQuery.agentInstance.status = 'ERROR'
        llmQuery.agentInstance.save()
        return # Stop execution

    instance = llmQuery.agentInstance
    if not toolCalls:
        decide_next_step(instance)
        return
    
    if not instance.system  or (instance.system and instance.system.status == 'online'):
        # Set status to EXECUTING_TOOLS before running them
        instance.status = 'EXECUTING_TOOLS'
        instance.save()
        for toolCall in toolCalls:
            try:
                toolCall.run()
            except Exception as e:
                print(f"Error running tool call {toolCall.id}: {e}")
        decide_next_step(instance)
        return 
    
    print(f"Cannot execute tool calls for instance {instance.pk}. Its assigned system is offline or not set.")
    instance.status = 'SYSTEM_OFFLINE'
    instance.save()


def decide_next_step(agent_instance):
    """
    The core of the new state machine. Determines the agent's next status after a cycle.
    A cycle is defined as one LLM query and the execution of any resulting tool calls.
    """
    # The `await_user_input` tool sets this flag. If it's true, we must wait.
    if agent_instance.require_user_interaction:
        agent_instance.status = 'AWAITING_USER_INPUT'
        agent_instance.automated_step_count = 0
        agent_instance.save()
        send_object_to_clients(agent_instance)
        return  # Stop the loop and wait.

    # If we are not waiting for a user, check if we can and should continue automatically.
    if agent_instance.limit_max_automated_steps > 0:
        if agent_instance.automated_step_count < agent_instance.limit_max_automated_steps:
            agent_instance.status = 'IDLE_AUTOMATED'
            agent_instance.automated_step_count += 1
            agent_instance.save()
            agent_instance.start_or_continue()  # Trigger the next automated cycle.
            return 
        # has reached its limit, or the task is complete.
        # For now, we default to IDLE. A future tool could set a 'FINISHED' state.
        agent_instance.status = 'AWAITING_USER_INPUT'
        agent_instance.automated_step_count = 0  # Reset counter
        agent_instance.save()
        return 
    
    # If automation is disabled, 
    agent_instance.status = 'IDLE'
    agent_instance.automated_step_count = 0  # Reset counter, just in case
    agent_instance.save()
