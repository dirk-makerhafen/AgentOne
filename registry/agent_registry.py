from __future__ import annotations
import inspect
from typing import List, Any, Dict, Type, Union
from django.db import transaction
from registry.sub_agents import Subagents, Subagent
from server.models.enums.task_enums import TaskType
from server.models.agents.agent import AgentModel
from server.models.agents.profile import ProfileModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.tasks.task_definition import TaskDefinition
from registry.profile import Profile
from registry.task_decorators import TaskDescriptor
from server.models.content import GenericContent
from registry.utils import generate_schema_for_function, get_import_strings, get_ai_model


class AgentRegistry():
    def register(self, agent_cls, recursive=False) -> AgentVersionModel:

        print(f'Registering Agent "{agent_cls.__name__}" from definition')

        # 1. Collect all subagents and tools declared by the agent_cls
        subagent_defs =  getattr(agent_cls, "subagents", Subagents())
        if not subagent_defs:
            subagent_defs = Subagents()
        raw_tool_defs = [x for x in getattr(agent_cls, "tools", [])] # This list can contain TaskDescriptor or BaseAgent subclasses

        # Map to store AgentVersion for each *imported* agent (subagent or external tool agent)
        imported_agent_versions_map: Dict[str, AgentVersionModel] = {} 

        # 2. Recursively register subagents
        # This ensures they are up-to-date and we get their latest AgentVersion objects.
        subagent_versions: List[AgentVersionModel] = []
        if recursive:
            for key, subagent in subagent_defs.all().items():
                registered_sub_version = subagent.agent_class.register(recursive=True)
                subagent_versions.append(registered_sub_version)
                imported_agent_versions_map[subagent.agent_class.__name__] = registered_sub_version

        # Register external tool agents (BaseAgent subclasses) declared in .tools list
        # This is for tool agents that are separate BaseAgent classes, not internal @tool methods.
        registered_external_tool_agent_versions: List[AgentVersionModel] = []
        for tool_def_item in raw_tool_defs:
            if isinstance(tool_def_item, BaseAgent): # Check if it's an BaseAgent class
                registered_tool_version = tool_def_item.register(recursive=True)
                registered_external_tool_agent_versions.append(registered_tool_version)
                imported_agent_versions_map[tool_def_item.__name__] = registered_tool_version

        # 3. Prepare kwargs for Profile (removed bare except and used specific get_or_create logic)
        profile = getattr(agent_cls, "profile", ProfileModel())
        profile: ProfileModel
        print("profile.model", profile.model)
        print("raw_tool_defs", raw_tool_defs)
        aimodel = get_ai_model(profile.model)
        kwargs = {
            "name": profile.name if profile.name else f'{agent_cls.__name__}:default',
            "aimodel": aimodel,
            "variant_defs":  profile.to_dict().get("variants", None),
            "max_retries": profile.max_retries,
            "priority":  profile.priority,
            "thinking":profile.thinking,
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
        python_dependencies = get_import_strings(source_path, agent_cls.__name__)

        with transaction.atomic():
            profile_obj, created_profile = ProfileModel.objects.get_or_create(**kwargs) 
            agent, created_agent = AgentModel.objects.get_or_create(name=agent_cls.__name__, defaults={"description": getattr(agent_cls, "description", ""),})

            # Get the latest existing agent version
            agent_version: AgentVersionModel = agent.agent_versions.order_by("-version_number").first()

            # Determine if current agent's source/dependencies have changed
            source_changed = not agent_version or agent_version.source_path != source_path or ( not agent_version.source_code or agent_version.source_code.content != source_code)

            python_dependencies_changed = not agent_version or agent_version.python_dependencies != python_dependencies

            # Check for changes in imported sub-agents
            imported_sub_agents_changed = False
            if agent_version:
                existing_sub_agent_pks = {v.pk for v in agent_version.sub_agent_versions.all()}
                current_sub_agent_pks = {v.pk for v in subagent_versions}
                imported_sub_agents_changed = (existing_sub_agent_pks != current_sub_agent_pks)

            # Check for changes in available tools (from external tool agents OR internal @tool methods)
            imported_tool_agents_changed = False
            if agent_version:
                existing_available_tools_info = {
                    (avt.tool_agent_version, avt.task_definition)
                    for avt in agent_version.available_tools.all()
                }
                print("TOOLTOOL1", existing_available_tools_info)
                current_available_tools_info = set()
                
                for tool_item in raw_tool_defs:
                    #print("tool_item", tool_item, type(tool_item),  issubclass(tool_item, BaseAgent),tool_item.__mro__, BaseAgent)
                    if isinstance(tool_item, TaskDescriptor):
                        # Internal tool: its task definition is created during _register_tasks for this agent_version.
                        # Its presence is implicitly covered by source_changed/python_dependencies_changed if its definition changes.
                        # For explicit available_tools_info, we would need to know its final task_definition.pk
                        # For simplicity, we are focusing on *external* tool agent changes for this flag.
                        pass  
                    elif isinstance(tool_item, BaseAgent) or issubclass(tool_item, BaseAgent):
                        print("BaseAgent", tool_item)
                        tool_agent_name = tool_item.__name__
                        if tool_agent_name in imported_agent_versions_map:
                            tool_agent_version = imported_agent_versions_map[tool_agent_name]
                            for td in tool_agent_version.task_definitions.filter(task_type=TaskType.TOOL):
                                current_available_tools_info.add((tool_agent_version, td))
                    else:
                        print(BaseAgent.__class__, tool_item.__class__)
                        raise Exception(f"Unknown tool type { type(tool_item)}")
                print("TOOLTOOL2", current_available_tools_info)
                imported_tool_agents_changed = (existing_available_tools_info != current_available_tools_info)

            print(f"source_changed: {source_changed}")
            print(f"python_dependencies_changed: {python_dependencies_changed}")
            print(f"imported_sub_agents_changed: {imported_sub_agents_changed}")
            print(f"imported_tool_agents_changed: {imported_tool_agents_changed}")

            is_registered = not(source_changed or python_dependencies_changed or imported_sub_agents_changed  or imported_tool_agents_changed )

            if not is_registered:
                print("Agent needs re-registration or is new.")

                new_agent_version = AgentVersionModel.objects.create(
                    agent=agent,
                    profile=profile_obj,
                    source_path = source_path,
                    source_code = GenericContent.from_text(source_code) if source_code else None,
                    class_name = agent_cls.__name__,
                    python_dependencies = python_dependencies,
                    version_number = agent_version.version_number + 1 if agent_version else 1
                )
                

                for key, subagent in subagent_defs.all().items():
                    registered_sub_version = imported_agent_versions_map[subagent.agent_class.__name__]
                    '''AgentVersionSubAgentRelation.objects.get_or_create(
                        parent_agent_version = new_agent_version,
                        sub_agent_version = registered_sub_version,
                        create_option = subagent.create_option,
                        visible_to = subagent.visible_to,
                        instance_name = subagent.instance_name if subagent.instance_name else key,
                    )'''
                
                agent_version = new_agent_version # Update agent_version to the newly created one
            else:
                print("Agent is already registered and up-to-date.")
            registered_tasks = self._register_tasks(agent_cls, agent_version)
            self._register_available_tools(agent_cls, agent_version, imported_agent_versions_map)
            agent_cls.is_registered = True
            agent_version.task_definitions.set(registered_tasks)
            agent_version.sub_agent_versions.set(subagent_versions)

        return agent_version

    def _register_tasks(self, agent_cls, agent_version):
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
            if priority := task_def.get("priority", None):
                existing_tasks_filter_kwargs["priority"] = priority
            if thinking := task_def.get("thinking", None) is not None:
                existing_tasks_filter_kwargs["thinking"] = thinking
            task_obj, created = TaskDefinition.objects.get_or_create(
                **existing_tasks_filter_kwargs, # Use the same normalized fields for lookup
            )
            task_objs.append(task_obj)

            if task_def["task_type"] == "TOOL":
                print("TOOOOOOOOOLLLL", name)
                '''AgentVersionAvailableTool.objects.get_or_create(
                    parent_agent_version = agent_version,
                    tool_agent_version = agent_version,
                    task_definition = task_obj
                )'''
        return task_objs

    def _register_available_tools(self, agent_cls, new_agent_version: AgentVersionModel, imported_agent_versions_map: Dict[str, AgentVersionModel]):
        from runtime.agents.base_agent import BaseAgent

        # Clear existing available tools for this version to ensure only current ones are linked
        #AgentVersionAvailableTool.objects.filter(parent_agent_version=new_agent_version).delete()

        tools_to_link = []
        for tool_item in getattr(agent_cls, "tools", []):
            if isinstance(tool_item, TaskDescriptor):
                # This is an internal tool (e.g., @tool method in agent_cls)
                # Its task definition is part of the new_agent_version's own tasks.
                tool_task_def = new_agent_version.task_definitions.filter(name=tool_item.func.__name__, task_type=TaskType.TOOL).first()
                if tool_task_def:
                    tools_to_link.append((new_agent_version, tool_task_def)) # Link to itself as provider
                else:
                    raise Exception(f"WARNING: Internal tool {tool_item.func.__name__} not found in {new_agent_version.agent.name}'s task definitions.")
            elif isinstance(tool_item, BaseAgent) or issubclass(tool_item, BaseAgent):
                # This is an external tool agent (e.g., class MyToolAgent in agent_cls.tools)
                tool_agent_name = tool_item.__name__
                if tool_agent_name in imported_agent_versions_map:
                    tool_agent_version = imported_agent_versions_map[tool_agent_name]
                    # Link all its TOOL-type task definitions
                    for tool_task_def in tool_agent_version.task_definitions.filter(task_type=TaskType.TOOL):
                        tools_to_link.append((tool_agent_version, tool_task_def))
                else:
                    raise Exception(f"WARNING: External tool agent {tool_agent_name} not found in imported_agent_versions_map.")
            else:
                print(BaseAgent.__class__, tool_item.__class__)
                raise Exception(f"Unknown tool type {tool_item}")
            
        # Create or update AgentVersionAvailableTool entries
        '''
        for tool_agent_version, task_definition in tools_to_link:
            AgentVersionAvailableTool.objects.get_or_create(
                parent_agent_version = new_agent_version,
                tool_agent_version = tool_agent_version,
                task_definition = task_definition
            )
        '''
            
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
