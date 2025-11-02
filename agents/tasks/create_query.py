from datetime import datetime
import time
from celery import shared_task
import traceback
import random
from agents.history_limiter import HistoryLimiter
from agents.models.agent_instance import BUILTIN_TOOL_CLASS_MAP
from agents.models.conversation_message import ConversationMessage
from agents.models.debug_log_entry import DebugLogEntry
from agents.models.llm_query import LLMQuery, QueryMessage, QueryMessagePart
from agents.tasks.execute_query import execute_query
from core.models.prompt import Prompt
from tools.builtin_filesystem.models.fs_log_entry import FsLogEntry
from tools.builtin_filesystem.utils.fsutils import get_relative_path
from tools.builtin_subscriptions.models.tool_subscription import ToolSubscription
from tools.calls.models.tool_call import ToolCall

@shared_task
def celery_create_query(agentinstance_id):
    from agents.models.agent_instance import AgentInstance, BUILTIN_TOOL_CLASS_MAP
    from agents.rate_limiter import rate_limiter, RateLimitExceeded
    agentInstance = AgentInstance.objects.get(instance_pk=agentinstance_id)
    agent = agentInstance.agent

    try:
        # Check and record requests rate limit before proceeding with query creation
        rate_limiter.check_and_record_usage(agentInstance, requests_cost=1, tokens_cost=0)
    except RateLimitExceeded as e:
        # Set status to AWAITING_RATE_LIMIT and reschedule the task
        if agentInstance.status != AgentInstance.AgentInstanceStatusChoices.AWAITING_RATE_LIMIT:
            agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.AWAITING_RATE_LIMIT)
     
        # Reschedule the task
        celery_create_query.apply_async(args=[agentinstance_id], countdown=e.time_to_reset)
        return # Stop execution in current task, it will be retried

    if agentInstance.status != AgentInstance.AgentInstanceStatusChoices.THINKING:
        agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.THINKING)
      

    try:

        llmQuery = LLMQuery(agent=agent, agentInstance=agentInstance, aimodel=agentInstance.aimodel if agentInstance.aimodel else agentInstance.agent.aimodel)
        messages = []
        agent = agentInstance.agent
        top_prompt_relations = []
        post_top_relations = []
        pre_chat_relations = []
        post_chat_relations = []
        if hasattr(agent, "agent_prompt_relations"):
            top_prompt_relations = list(agent.agent_prompt_relations.filter(insert_at="TOP").order_by("index"))
            post_top_relations = list(agent.agent_prompt_relations.filter(insert_at="POST_TOP").order_by("index"))
            pre_chat_relations = list(agent.agent_prompt_relations.filter(insert_at="PRE_CHAT").order_by("index"))
            post_chat_relations = list(agent.agent_prompt_relations.filter(insert_at="POST_CHAT").order_by("index"))

        for top_prompt_relation in top_prompt_relations:
            queryMessage = QueryMessage(role=top_prompt_relation.role, agent=agent, agentInstance=agentInstance, llmQuery=llmQuery)
            queryMessage._parts_to_save = [QueryMessagePart(
                tags = ["Prompts", top_prompt_relation.prompt.source, top_prompt_relation.prompt.key],
                promptVariant = random.choice(list(top_prompt_relation.prompt.variants.filter(is_enabled=True))),
                template_data = eval(top_prompt_relation.prompt.data_lambda)(agentInstance) if top_prompt_relation.prompt.data_lambda else {},
                queryMessage = queryMessage
            )]
            messages.append(queryMessage)

        for post_top_relation in post_top_relations:
            queryMessage = QueryMessage(role=post_top_relation.role, agent=agent, agentInstance=agentInstance, llmQuery=llmQuery)
            queryMessage._parts_to_save = [QueryMessagePart(
                tags = ["Prompts", post_top_relation.prompt.source, post_top_relation.prompt.key],
                promptVariant = random.choice(list(post_top_relation.prompt.variants.filter(is_enabled=True))),
                template_data = eval(post_top_relation.prompt.data_lambda)(agentInstance) if post_top_relation.prompt.data_lambda else {},
                queryMessage = queryMessage
            )]
            messages.append(queryMessage)

        toolheaderparts = []
        toolcontentparts = []

        for tool_definition in agentInstance.agent.available_tools.all():
            tool_call_instance = BUILTIN_TOOL_CLASS_MAP[tool_definition.name](agentInstance)
            toolheaderparts.extend(tool_call_instance.get_header_parts())
            toolcontentparts.extend(tool_call_instance.get_content_parts())
        
        if toolheaderparts:
            queryMessage = QueryMessage(role="user", agent=agent, agentInstance=agentInstance, llmQuery=llmQuery)
            queryMessage._parts_to_save = []
            for toolheaderpart in toolheaderparts:
                toolheaderpart.queryMessage = queryMessage
                queryMessage._parts_to_save.append(toolheaderpart)
            messages.append(queryMessage)
            #messages.append({"role": "user", "parts": toolheaderparts })
        
        if toolcontentparts:
            queryMessage = QueryMessage(role="user", agent=agent, agentInstance=agentInstance, llmQuery=llmQuery)
            queryMessage._parts_to_save = []
            for toolcontentpart in toolcontentparts:
                toolcontentpart.queryMessage = queryMessage
                queryMessage._parts_to_save.append(toolcontentpart)
            messages.append(queryMessage)
            #messages.append({"role": "user", "parts": toolcontentparts })
        

        messages.extend(get_tool_subscription_messages(agentInstance=agentInstance, llmQuery=llmQuery))
        
        for pre_chat_relation in pre_chat_relations:
            queryMessage = QueryMessage(role=pre_chat_relation.role, agent=agent, agentInstance=agentInstance, llmQuery=llmQuery)
            queryMessage._parts_to_save = [QueryMessagePart(
                tags = ["Prompts", pre_chat_relation.prompt.source, pre_chat_relation.prompt.key],
                promptVariant = random.choice(list(pre_chat_relation.prompt.variants.filter(is_enabled=True))),
                template_data = eval(pre_chat_relation.prompt.data_lambda)(agentInstance) if pre_chat_relation.prompt.data_lambda else {},
                queryMessage = queryMessage
            )] 
            messages.append(queryMessage)
            #messages.append({"role": pre_chat_relation.role, "parts": [{
            #    "tags": ["Prompts", pre_chat_relation.prompt.source, pre_chat_relation.prompt.key] ,
            #    'tpId': random.choice(list(pre_chat_relation.prompt.variants.filter(is_enabled=True))).id,
            #    'data': eval(pre_chat_relation.prompt.data_lambda)(agentInstance) if pre_chat_relation.prompt.data_lambda else {},
            #}]})
  
        messages.extend(get_chat_messages(agentInstance=agentInstance, llmQuery= llmQuery))

        for post_chat_relation in post_chat_relations:
            queryMessage = QueryMessage(role=post_chat_relation.role, agent=agent, agentInstance=agentInstance, llmQuery=llmQuery)
            queryMessage._parts_to_save = [QueryMessagePart(
                tags = ["Prompts", post_chat_relation.prompt.source, post_chat_relation.prompt.key],
                promptVariant = random.choice(list(post_chat_relation.prompt.variants.filter(is_enabled=True))),
                template_data = eval(post_chat_relation.prompt.data_lambda)(agentInstance) if post_chat_relation.prompt.data_lambda else {},
                queryMessage = queryMessage
            )]
            messages.append(queryMessage)
            #messages.append({"role": post_chat_relation.role, "parts": [{
            #    "tags": ["Prompts", post_chat_relation.prompt.source, post_chat_relation.prompt.key] ,
            #    'tpId': random.choice(list(post_chat_relation.prompt.variants.filter(is_enabled=True))).id,
            #    'data': eval(post_chat_relation.prompt.data_lambda)(agentInstance) if post_chat_relation.prompt.data_lambda else {},
            #}]})
            
        llmQuery.save()
        for index, message in enumerate(messages):
            message.index = index
            message.save()
            for index1, part_to_save in enumerate(message._parts_to_save):
                part_to_save.index = index1
                part_to_save.save()

        #llmQuery.messages = messages
        #
        execute_query.delay(llmQuery.pk)    # not celery for now, keep it that way.
    except Exception as e:
        print(e)
        debugLogEntry = DebugLogEntry(agentInstance = agentInstance, event = 'exception', data = {"exception": f'{e}\n{traceback.format_exc()}'})
        debugLogEntry.save() 
        agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.ERROR)

      
def get_chat_messages(agentInstance, llmQuery):
    cmessages = []

    conversationMessages = agentInstance.get_conversation_messages(limit=agentInstance.effective_limit_max_conversation_messages)
    conversationMessages = sorted({msg.id: msg for msg in conversationMessages}.values(), key=lambda msg: msg.created_at)

    fs_entries = agentInstance.filesystem.get_loaded_items(refresh_from_disk=True)
    all_loaded_paths = [e.path for e in fs_entries]
    all_loaded_paths.extend([get_relative_path(agentInstance.workingdir, x) for x in all_loaded_paths])
    all_loaded_paths = set(all_loaded_paths)

    all_entries = conversationMessages + fs_entries
    all_entries.sort(key=lambda x: x.updated_at if type(x) == FsLogEntry else x.created_at, reverse=True) # Sort descending for HistoryLimiter processing

    # Collect history limiting rule templates from all available tools
    limiter = HistoryLimiter(agentInstance, all_entries, all_loaded_paths)
    resultInjectionTemplate = Prompt.get_template(agentInstance=agentInstance, source="tools", key="ResultInjection")
    filesystemInjectionTemplate = Prompt.get_template(agentInstance=agentInstance, source='tools.builtin_filesystem', key="content_injection")

    for entry in all_entries:
        if type(entry) == ConversationMessage:
            if entry.hide_from_context: # or not (entry.pin_to_context or entry in conversationMessages):
                continue

            msg_parts = []
            tool_result_parts = []
            for conversationMessagePart in entry.conversationMessageParts.all():
                if not conversationMessagePart.toolCall:
                    msg_parts.append(QueryMessagePart( 
                        conversationMessage = entry,
                        conversationMessagePart = conversationMessagePart,
                        tags = ["ChatMessage", f"{entry.role}"],
                        content_type=conversationMessagePart.content_type,
                    ))
                    #msg_parts.append({"cmId": entry.id, "pnr": index, "tags": ["ChatMessage", f"{entry.role}"], })
                    continue

                toolCall = conversationMessagePart.toolCall
                if limiter.is_tool_call_limited(toolCall, entry):
                    continue

                msg_parts.append(QueryMessagePart(
                    conversationMessage = entry,
                    conversationMessagePart = conversationMessagePart,
                    toolCall = toolCall,
                    tags = ["Tool",  "FsTool" if toolCall.function_name.startswith("fs_") else "MemoryTool" if toolCall.function_name.startswith("memory_") else f"{toolCall.function_name}", "ToolCall", toolCall.function_name],
                ))
                #msg_parts.append({
                #    "tags": ["Tool",  "FsTool" if toolCall.function_name.startswith("fs_") else "MemoryTool" if toolCall.function_name.startswith("memory_") else f"{toolCall.function_name}", "ToolCall", toolCall.function_name],
                #    "cmId": entry.id, 
                #    "tcId": toolCall.id, 
                #    "pnr": index
                #})
                
                if toolCall.function_name.startswith("memory_") and toolCall.status == ToolCall.ToolCallStatusChoices.SUCCESS:
                    continue

                toolResponse = toolCall.toolResponses.last()
                tool_result_parts.append(QueryMessagePart(
                    toolCall = toolCall,
                    toolResponse = toolResponse,
                    promptVariant = resultInjectionTemplate,
                    tags = ["Tool",  "FsTool" if toolCall.function_name.startswith("fs_") else "MemoryTool" if toolCall.function_name.startswith("memory_") else f"{toolCall.function_name}", "ToolCall", toolCall.function_name],
                    template_data =  {
                        'function_name': toolCall.function_name, 
                        'arguments': {k: v for k, v in toolCall.arguments.items() if k in ['path', 'action', 'track', 'layer', 'index', "subscription_id"]}, 
                        'status': toolCall.status
                    }
                ))
                #tool_result_parts.append({
                    #"tcId": toolCall.id, 
                    #"trId": toolResponse.id if toolResponse else None, 
                    #"tpId": resultInjectionTemplate.pk,
                    #"tags": ["Tool", "FsTool" if toolCall.function_name.startswith("fs_") else "MemoryTool" if toolCall.function_name.startswith("memory_") else f"{toolCall.function_name}", "ToolResult"],
                    #'data': {
                    #    'function_name': toolCall.function_name, 
                    #    'arguments': {k: v for k, v in toolCall.arguments.items() if k in ['path', 'action', 'track', 'layer', 'index', "subscription_id"]}, 
                    #    'status': toolCall.status
                    #}
                #})

            if tool_result_parts:
                queryMessage = QueryMessage(role='user', agent=agentInstance.agent, agentInstance=agentInstance, llmQuery=llmQuery)
                queryMessage._parts_to_save = []
                for i, tool_result_part in enumerate(tool_result_parts):
                    tool_result_part.queryMessage = queryMessage
                    tool_result_part.index = i
                    queryMessage._parts_to_save.append(tool_result_part)
                cmessages.append(queryMessage)
                if limiter.is_general_message_limited('messages_dont_warn_forget', entry):
                    queryMessage.content_prefix = '@@@TO_BE_FORGOTTEN@@@'
                #cmessages.append({
                #   'role': 'user', 
                #   'parts': tool_result_parts, 
                #   'warn_forget': limiter.is_general_message_limited('messages_dont_warn_forget', entry)})

            if msg_parts:
                queryMessage = QueryMessage(role= entry.role, agent=agentInstance.agent, agentInstance=agentInstance, llmQuery=llmQuery)
                queryMessage._parts_to_save = []
                for i, msg_part in enumerate(msg_parts):
                    msg_part.queryMessage = queryMessage
                    msg_part.index = i
                    queryMessage._parts_to_save.append(msg_part)
                cmessages.append(queryMessage)
                if limiter.is_general_message_limited('messages_dont_warn_forget', entry):
                    queryMessage.content_prefix = '@@@TO_BE_FORGOTTEN@@@'
                #cmessages.append({
                #cmessages.append({'role': entry.role, 'parts': msg_parts, 'warn_forget': limiter.is_general_message_limited('messages_dont_warn_forget', entry)})

        elif type(entry) == FsLogEntry:
            queryMessage = QueryMessage(role="user", agent=agentInstance.agent, agentInstance=agentInstance, llmQuery=llmQuery)
            queryMessagePart = QueryMessagePart(
                promptVariant=filesystemInjectionTemplate, 
                tags=["Tool", "FsTool", 'Loaded', 'Directories' if entry.is_directory else 'Files'],
                queryMessage = queryMessage,
                fsLogEntry = entry,
                template_data = entry.as_query_dict(),
            )
            queryMessage._parts_to_save = [queryMessagePart, ]
            cmessages.append(queryMessage)
            #cmessages.append({"role": "user", "parts": [{
            #    "tags": ["Tool", "FsTool", 'Loaded', 'Directories' if entry.is_directory else 'Files'],
            #    'tpId': filesystemInjectionTemplate.pk, 
            #    'data': entry.as_query_dict(),
            #}]})


    cmessages = list(reversed(cmessages))
    return cmessages


def get_tool_subscription_messages(agentInstance, llmQuery):
    messages = []
    # Execute active tool subscriptions and inject their output into the context
    subscription_parts = []
    subscriptions = ToolSubscription.objects.filter(agentInstance=agentInstance, is_active=True)
    if not subscriptions:
        return []

    try:
        subscriptionResultInjectionTemplate = Prompt.get_template(agentInstance=agentInstance, source='tools.builtin_subscriptions', key="SubscriptionResultInjection")
        for subscription in subscriptions:
            try:
                tool_function = agentInstance.get_tool_function(subscription.tool_name)
                if tool_function:
                    # We don't want the subscription execution to create another subscription, so we force one-shot mode.
                    args = subscription.arguments
                    if 'mode' in args:
                        args['mode'] = 'one-shot' 
                    
                    success, result = tool_function['callable'](**args)
                    subscription_parts.append(QueryMessagePart(
                        promptVariant=subscriptionResultInjectionTemplate, 
                        tags=["Tool", "Subscription", subscription.tool_name],
                        template_data= {
                            'subscription_id': subscription.subscription_id,
                            'tool_name': subscription.tool_name,
                            'arguments': {k: v for k, v in subscription.arguments.items() if k != 'source'},
                            'output': result,
                            'status': 'success' if success else 'failed'
                        }
                    ))
                    #subscription_parts.append({
                    #    #'tpId': subscriptionResultInjectionTemplate.pk,
                    #    #"tags": ["Tool", "Subscription", subscription.tool_name],
                    #    'data': {
                    #        'subscription_id': subscription.subscription_id,
                    #        'tool_name': subscription.tool_name,
                    #        'arguments': {k: v for k, v in subscription.arguments.items() if k != 'source'},
                    #        'output': output.strip(),
                    #        'status': 'success' if success else 'failed'
                    #    }
                    #})
            except Exception as e:
                # Log the error but do not crash the entire query generation process
                debugLogEntry = DebugLogEntry(agentInstance=agentInstance, event='exception', data={"exception": f'Error executing subscription {subscription.id}: {e}\n{traceback.format_exc()}'})
                debugLogEntry.save()
        if subscription_parts:
            queryMessage = QueryMessage(role="user", agent=agentInstance.agent, agentInstance=agentInstance, llmQuery=llmQuery)
            queryMessage._parts_to_save = []
            for i, subscription_part in enumerate(subscription_parts):
                subscription_part.queryMessage = queryMessage
                subscription_part.index = i
                queryMessage._parts_to_save.append(subscription_part)
            messages.append(queryMessage)
            #messages.append({'role': 'user', 'parts': subscription_parts})
    except Prompt.DoesNotExist:
        debugLogEntry = DebugLogEntry(agentInstance=agentInstance, event='exception', data={"exception": "SubscriptionResultInjection prompt template not found. Subscriptions will not be executed."})
        debugLogEntry.save()
    return messages
