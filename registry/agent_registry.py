from __future__ import annotations
import inspect
import json
import random
import ast

from typing import List, Any, Dict, Type, Union
from django.db import transaction
import re
from typing import get_type_hints, get_origin, get_args, Annotated, Union, Literal, List, Dict
from server.models.enums.task_enums import TaskType
from server.models.agents.agent import Agent
from server.models.agents.agent_profile import AgentProfile
from server.models.agents.agent_version import AgentVersion, AgentVersionAvailableTool

from server.models.providers.ai_model import AiModel
from server.models.tasks.agent_task_definition import AgentTaskDefinition
from registry.profile_def import ProfileDef
from registry.task_decorators import TaskDescriptor
from django.core.exceptions import ValidationError

from server.models.content import GenericContent
from registry.utils import generate_schema_for_function, get_import_strings, get_ai_model


class AgentRegistry():
    def register(self, agent_cls, recursive=False) -> AgentVersion:
        print(f'\Registering Agent "{agent_cls.__name__}" from definition')
        subagent_defs = [ x for x in  getattr(agent_cls, "subagents", [])]
        tool_defs = [x for x in getattr(agent_cls, "tools", []) if not isinstance(x, TaskDescriptor)]
        subagent_versions = []
        if recursive:
            for subagent_def in subagent_defs:
                subagent_versions.append(subagent_def.register(recursive=True))
            for tool_def in tool_defs:
                tool_def.register(recursive=True)
        print("subagent_versions", subagent_versions)
        unregistered_subagent_defs = [a for a in subagent_defs if a.is_registered is False]
        unregistered_tool_defs = [a for a in tool_defs if a.is_registered is False]
        if unregistered_subagent_defs:
            raise Exception(f"unregistered_subagent_defs {unregistered_subagent_defs}")
        if unregistered_tool_defs:
            raise Exception(f"unregistered_tool_defs {unregistered_tool_defs}")

        profile = getattr(agent_cls, "profile")
        profile: ProfileDef
        agent_version = None
        aimodel = get_ai_model(profile.model)
        kwargs = {
            "name": profile.name,
            "aimodel": aimodel,
            "variant_defs":  profile.to_dict().get("variants", None),
            "max_retries": profile.max_retries,
            "max_task_steps": profile.max_task_steps,
            "unattended_steps": profile.unattended_steps,
            "max_history_messages": profile.max_history_messages,
            "task_prompt": GenericContent.from_text(profile.task_prompt) if profile.task_prompt else None,
            "system_prompt": GenericContent.from_text(profile.system_prompt) if profile.system_prompt else None,
            "execution_mode": profile.execution_mode,
            "tool_call_syntax": profile.tool_call_syntax,
            "extra_settings": profile.extra_settings
        }
        kwargs = {k:v for k,v in kwargs.items() if v is not None}
        source_code = inspect.getsource(agent_cls)
        source_path = inspect.getfile(agent_cls)
        python_dependencies = get_import_strings(source_path, agent_cls.__name__) # Remove duplicates and sort for consistency

        with transaction.atomic():
            profile, created = AgentProfile.objects.get_or_create(**kwargs)
            agent, created = Agent.objects.get_or_create(name=agent_cls.__name__, defaults={"description": getattr(agent_cls, "description", ""),})
            agent_version = agent.agent_versions.order_by("-version_number").first() if agent else None
            source_changed = not agent_version or agent_version.source_path != source_path or agent_version.source_code.get() != source_code
            python_dependencies_changed = not agent_version or agent_version.python_dependencies != python_dependencies
            imported_sub_agents_changed = False  #todo
            imported_tool_agents_changed = False  #todo
            print("self.source_changed", source_changed)
            is_registered = not(source_changed or python_dependencies_changed or imported_sub_agents_changed  or imported_tool_agents_changed )
            if not is_registered:
                agent_version = AgentVersion.objects.create(
                    agent=agent,
                    profile=profile,
                    parent = None,
                    #sub_agent_versions
                    source_path = source_path,
                    source_code = GenericContent.from_text(source_code) if source_code else "",
                    class_name = agent_cls.__name__,
                    python_dependencies = python_dependencies,
                    version_number = agent_version.version_number + 1 if agent_version else 1
                )
                registered_tasks = self._register_tasks(agent_cls)
                agent_version.task_definitions.set(registered_tasks)
                agent_version.sub_agent_versions.set(subagent_versions)
                #self._register_available_tools(newest_agent_version, imported_agent_versions)
            agent_cls.is_registered = True
        return agent_version

    def _register_tasks(self, agent_cls):
        task_objs = []
        task_definitions = self._read_task_definitions(agent_cls)
        for name, task_def in task_definitions.items():
            canonical_function_schema = task_def.get("schema", {}) or {}            
            normalized_trigger = task_def.get("trigger", "") or ""
            existing_tasks_filter_kwargs = {
                "name": name,
                "task_type": task_def["task_type"],
                "description": task_def.get("description", ""),
                "trigger": normalized_trigger,
                "function_schema": canonical_function_schema,
            }
            if requires_approval := task_def.get("requires_approval", None):
                existing_tasks_filter_kwargs["requires_approval"] = requires_approval
            if max_retries := task_def.get("max_retries", None):
                existing_tasks_filter_kwargs["max_retries"] = max_retries
            if retry_delay := task_def.get("retry_delay", None):
                existing_tasks_filter_kwargs["retry_delay"] = retry_delay
            if retry_requires_approval := task_def.get("retry_requires_approval", None):
                existing_tasks_filter_kwargs["retry_requires_approval"] = retry_requires_approval

            task_obj, created = AgentTaskDefinition.objects.get_or_create(
                **existing_tasks_filter_kwargs, # Use the same normalized fields for lookup
            )
            print("was created:", created)
            task_objs.append(task_obj)
        return task_objs

    def _register_available_tools(self, agent_cls, new_agent_version, imported_agent_versions, ):
        tools = []
        for imp in getattr(agent_cls, "tools", []):
            if isinstance(imp, TaskDescriptor):
                aname, fname = imp.func.__qualname__.split(".",1)
                tool_agent_version = imported_agent_versions[aname]
                tool_agent_task_definition = tool_agent_version.agent_task_definitions.filter(name=fname, task_type=TaskType.TOOL).last()
                tools.append((tool_agent_version, tool_agent_task_definition))
            else:
                agent_version = imported_agent_versions[imp.__name__]
                tool_agent_task_definitions = agent_version.agent_task_definitions.filter(task_type=TaskType.TOOL)
                for tool_agent_task_definition in tool_agent_task_definitions:
                    tools.append((agent_version, tool_agent_task_definition))
        for tool in tools:
            tool_agent_version, tool_agent_task_definition = tool
            AgentVersionAvailableTool.objects.get_or_create(
                parent_agent_version = new_agent_version,
                tool_agent_version = tool_agent_version,
                task_definition = tool_agent_task_definition
            )
            
    def _read_task_definitions(self, agent_cls):
        defs = {}
        # Iterate over all methods, including inherited ones
        for attr_name in dir(agent_cls):
            attr = getattr(agent_cls, attr_name, None)
            if attr and hasattr(attr, "_task_definition"):
                task_def = attr._task_definition.copy()
                # Task/Tool schema generation if missing
                if not task_def.get("schema") and task_def["task_type"] in [TaskType.TOOL, TaskType.TASK, TaskType.COMMAND]:
                    # We pass the function to generate schema from its signature
                    description, task_def["schema"] = generate_schema_for_function(attr)
                    task_def["description"]  = description
                defs[task_def["name"]] = task_def
        return defs
