from datetime import datetime
import time
from celery import shared_task
import traceback
import random
from agents.history_limiter import HistoryLimiter
from agents.models.agent_instance import BUILTIN_TOOL_CLASS_MAP
from agents.models.conversation_message import ConversationMessage
from agents.models.debug_log_entry import DebugLogEntry
from agents.models.llm_query import LLMQuery
from agents.tasks.execute_query import execute_query
from core.models.prompt_string import PromptString
from tools.builtin_filesystem.models.fs_log_entry import FsLogEntry
from tools.builtin_filesystem.utils.fsutils import get_relative_path
from tools.builtin_subscriptions.models.tool_subscription import ToolSubscription
from tools.calls.models.tool_call import ToolCall
from agents.apps import AgentsConfig

@shared_task
def celery_create_query(agentinstance_id):
    from agents.models.agent_instance import AgentInstance, BUILTIN_TOOL_CLASS_MAP

    agentInstance = AgentInstance.objects.get(instance_pk=agentinstance_id)
    agentInstance.status = AgentInstance.AgentInstanceStatusChoices.THINKING
    agentInstance.save()

    try:
        messages = []
        systemPrompt = PromptString.get_template(agentInstance=agentInstance, source=AgentsConfig.name, key="System")
        mainInstructions =  PromptString.get_template(agentInstance=agentInstance, source=AgentsConfig.name, key="Instructions")
        toolInstructions = PromptString.get_template(agentInstance=agentInstance, source="tools", key="Instructions")
        outputFormat = PromptString.get_template(agentInstance=agentInstance, source=AgentsConfig.name, key="OutputFormat")
        outputFormatReminder = PromptString.get_template(agentInstance=agentInstance, source=AgentsConfig.name, key="OutputFormatReminder")
        
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
                'tpId': mainInstructions.id, 
        }]})

        messages.append({"role": "user", "parts": [{
                "tags": ["Prompts", "ToolInstructions"] ,
                'tpId': toolInstructions.id, 
        }]})


        toolheaderparts = []
        toolcontentparts = []

        for tool_definition in  agentInstance.agent.available_tools.all():
            tool_call_instance = BUILTIN_TOOL_CLASS_MAP[tool_definition.name](agentInstance)
            toolheaderparts.extend(tool_call_instance.get_header_parts())
            toolcontentparts.extend(tool_call_instance.get_content_parts())

        messages.append({"role": "user", "parts": toolheaderparts })
        messages.append({"role": "user", "parts": toolcontentparts })
        messages.extend(get_tool_subscription_messages(agentInstance=agentInstance))
        messages.extend(get_chat_messages(agentInstance=agentInstance))

        messages.append({"role": "user", "parts": [{
            "tags": ["Prompts", "OutputRules"],
            'tpId': outputFormatReminder.id, 
        }]})
            
        llmQuery = LLMQuery(agent=agentInstance.agent, agentInstance=agentInstance, aimodel=agentInstance.aimodel if agentInstance.aimodel else agentInstance.agent.aimodel)
        llmQuery.messages = messages
        llmQuery.save()
        execute_query.delay(llmQuery.pk)    # not celery for now, keep it that way.
    except Exception as e:
        print(e)
        debugLogEntry = DebugLogEntry(agentInstance = agentInstance, event = 'exception', data = {"exception": f'{e}\n{traceback.format_exc()}'})
        debugLogEntry.save() 
        agentInstance.status = AgentInstance.AgentInstanceStatusChoices.ERROR
        agentInstance.save()

      
def get_chat_messages(agentInstance):
    cmessages = []

    conversationMessages = agentInstance.get_conversation_messages(limit=agentInstance.effective_limit_max_conversation_messages)
    conversationMessages = sorted({msg.id: msg for msg in conversationMessages}.values(), key=lambda msg: msg.created_at)

    fs_entries = agentInstance.filesystem.get_loaded_items(refresh_from_disk=True)
    all_loaded_paths = [e.path for e in fs_entries]
    all_loaded_paths.extend([get_relative_path(agentInstance.workingdir, x) for x in all_loaded_paths])
    all_loaded_paths = set(all_loaded_paths)

    all_entries = conversationMessages + fs_entries
    all_entries.sort(key=lambda x: x.created_at, reverse=True) # Sort descending for HistoryLimiter processing

    # Collect history limiting rule templates from all available tools
    limiter = HistoryLimiter(agentInstance, all_entries, all_loaded_paths)
    resultInjectionTemplate = PromptString.get_template(agentInstance=agentInstance, source="tools", key="ResultInjection")
    filesystemInjectionTemplate = PromptString.get_template(agentInstance=agentInstance, source='tools.builtin_filesystem', key="ContentInjection")

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
                
                if toolCall.function_name.startswith("memory_") and toolCall.status == ToolCall.ToolCallStatusChoices.SUCCESS:
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
            cmessages.append({"role": "user", "parts": [{
                "tags": ["Tool", "FsTool", 'Loaded', 'Directories' if entry.is_directory else 'Files'],
                'tpId': filesystemInjectionTemplate.pk, 
                'data': entry.as_query_dict(),
            }]})


    cmessages = list(reversed(cmessages))
    return cmessages


def get_tool_subscription_messages(agentInstance):
    messages = []
    # Execute active tool subscriptions and inject their output into the context
    subscription_parts = []
    subscriptions = ToolSubscription.objects.filter(agentInstance=agentInstance, is_active=True)
    if not subscriptions:
        return []

    try:
        subscriptionResultInjectionTemplate = PromptString.get_template(agentInstance=agentInstance, source='tools.builtin_subscriptions', key="SubscriptionResultInjection")
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
    return messages
