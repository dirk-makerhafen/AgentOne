from agents.models.agent_instance import AgentInstance
from agents.models.conversation_message import ConversationMessage
from agents.models.agent_instance_fork import AgentInstanceFork
from celery import shared_task
from django.db import transaction
from tools.builtin_memory.models.memory_item import MemoryItem
from tools.builtin_filesystem.models.fs_log_entry import FsLogEntry
from tools.calls.models.tool_call import ToolCall
from tools.builtin_python.models.python_tool_var import PythonToolVar
from tools.builtin_a2a.models.a2a_description import AgentToAgentDescription
from tools.builtin_memory.prompts import TRACKS
import traceback

@shared_task
def celery_clone_agentinstance(agentinstance_id):
    source = AgentInstance.objects.get(instance_pk=agentinstance_id)
        
    child_instance = None
    with transaction.atomic():
        child_instance = AgentInstance.objects.create(
            agent=source.agent, system=source.system, aimodel=source.aimodel,
            name=f'Fork of {source.name or f"Instance {source.pk}"}',
            description_text=source.description_text, status='IDLE',
            workingdir=source.workingdir, workingdir_write_allowed=source.workingdir_write_allowed,
            access_rules=source.access_rules,
            limit_max_conversation_messages=source.limit_max_conversation_messages,
            limit_max_memory_items=source.limit_max_memory_items,
            limit_max_automated_steps=source.limit_max_automated_steps
        )
        
        fork_record = AgentInstanceFork.objects.create(
            parent_instance=source, child_instance=child_instance
        )
        fork_time = fork_record.created_at

        # 1. ConversationMessages: Get the latest 'limit' messages to fork.
        parent_messages_to_fork = source.conversationMessages.filter(
            created_at__lt=fork_time
        ).order_by('-created_at')[:source.limit_max_conversation_messages]
        message_ids_to_fork = {msg.id for msg in parent_messages_to_fork}

        # 2. FsLogEntries: Get only the latest version of currently loaded files.
        fs_entries_to_fork = source.fsLogEntries.filter(
            created_at__lt=fork_time, is_newest_version=True
        ).exclude(load_mode=None)

        # 3. ToolCalls: Only fork calls related to the messages being forked.
        tool_calls_to_fork = source.toolCalls.filter(
            created_at__lt=fork_time, conversationMessage_id__in=message_ids_to_fork
        )

        # 4. PythonToolVars: Fork the latest version of each variable.
        python_vars_to_fork = source.python_tool_vars.filter(
            created_at__lt=fork_time, next_version=None
        )

        # 5. AgentToAgentDescription: Fork only the single most recent description.
        description_to_fork = source.description_logs.filter(
            created_at__lt=fork_time
        ).order_by('-created_at').first()

        # 6. MemoryItems: Fork the latest 'limit' items per track and layer.
        memory_items_to_fork = []
        for trackname in TRACKS.keys():
            for layername in TRACKS[trackname]['layers'].keys():
                items = MemoryItem.objects.filter(
                    agentInstance=source, track=trackname, layer=layername,
                    next_version=None, created_at__lt=fork_time
                ).order_by('-index')[:source.effective_limit_max_memory_items]
                memory_items_to_fork.extend(items)

        # Combine all objects to be forked into a single structure
        all_objects_to_fork = {
            ConversationMessage: parent_messages_to_fork,
            FsLogEntry: fs_entries_to_fork,
            ToolCall: tool_calls_to_fork,
            PythonToolVar: python_vars_to_fork,
            MemoryItem: memory_items_to_fork,
        }
        if description_to_fork:
            all_objects_to_fork[AgentToAgentDescription] = [description_to_fork]

        # Process and bulk_create ghost objects for each model type
        for model_class, parent_queryset in all_objects_to_fork.items():
            new_child_objects = []
            for parent_obj in parent_queryset:
                child_obj = model_class()
                # Copy fields
                for field in parent_obj._meta.fields:
                    if not field.primary_key and field.name not in ['id', 'pk', 'agentinstance', 'agent_instance', 'agentInstance']:
                        setattr(child_obj, field.name, getattr(parent_obj, field.name))

                child_obj.agentInstance = child_instance
                child_obj.fork_of = parent_obj
                child_obj.raw_data_reference = parent_obj
                new_child_objects.append(child_obj)

            if new_child_objects:
                model_class.objects.bulk_create(new_child_objects)
