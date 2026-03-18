from __future__ import annotations
import inspect
import json
import random
from typing import List, Any, Dict, Type, Union
from django.db import transaction
import re
from typing import get_type_hints, get_origin, get_args, Annotated, Union, Literal, List, Dict
from django.core.exceptions import ValidationError
from registry.task_decorators import TaskDescriptor
from server.models.enums.task_enums import TaskType
from server.models.agents.agent import Agent
from server.models.agents.agent_version import AgentVersion, AgentVersionAvailableTool
from server.models.agents.agent_profile import AgentProfile
from server.models.tasks.agent_task_definition import AgentTaskDefinition
from server.models.content import GenericContent
from server.models.providers.ai_model import AiModel

AGENT_REGISTRY: Dict[str, Type[_AgentClassLoader]] = {}

def register_agent(agent_cls):
    a = _AgentClassLoader(agent_cls=agent_cls)
    return a.register()

class _AgentClassLoader():
    def __init__(self, agent_cls):
        self.agent_cls = agent_cls
        self.name = getattr(agent_cls, "name", agent_cls.__name__)

    def register(self):
        print(f'\nLoading Agent "{self.name}" from definition')
        with transaction.atomic():
            agent, created = Agent.objects.get_or_create(
                name=self.name,
                defaults={
                    "description": getattr(self.agent_cls, "description", ""),
                }
            )

            print(f" {' Created in database' if created else 'Already exists in database'}")
            
            # Build metadata for versioning check
            source_content = inspect.getsource(self.agent_cls)
            source_path = inspect.getfile(self.agent_cls)


            subagents = []
            imported_agent_versions = {}
            python_dependencies = []
            # Register imported agents recursively
            for imp in getattr(self.agent_cls, "subagents", []):
                sub_ua = _AgentClassLoader(imp)
                sub_version = sub_ua.register()
                subagents.append(sub_version)
                imported_agent_versions[sub_ua.name] = sub_version
            
            python_dependencies.extend(getattr(self.agent_cls, "python_dependencies", []))
            python_dependencies = sorted(list(set(python_dependencies))) # Remove duplicates and sort for consistency
            
            # Register imported tool agents recursively, if they are not imported yet
            for imp in getattr(self.agent_cls, "tools", []):
                if not isinstance(imp, TaskDescriptor):
                    sub_ua = _AgentClassLoader(imp)
                    sub_version = sub_ua.register()
                    subagents.append(sub_version)
                    imported_agent_versions[sub_ua.name] = sub_version
            
            python_dependencies.extend(getattr(self.agent_cls, "python_dependencies", []))
            python_dependencies = sorted(list(set(python_dependencies))) # Remove duplicates and sort for consistency
                
            subagent_names = sorted([f"Agent#{imp.agent.pk},v{imp.version_number}" for imp in subagents])
            print(subagent_names)

            # Current settings with fallbacks to class attributes
            s = getattr(self.agent_cls, "settings", Settings())
            aimodelname = s.model or getattr(self.agent_cls, "model", None)
            task_prompt   = s.task_prompt or getattr(self.agent_cls, "task_prompt", None)
            system_prompt = s.system_prompt or getattr(self.agent_cls, "system_prompt", None)
            input_schema  = s.input_schema or getattr(self.agent_cls, "input_schema", [])
            output_schema = s.output_schema or getattr(self.agent_cls, "output_schema", {})
         
            variants = getattr(self.agent_cls, "variants", [])
            print(f" > {len(variants) if variants else 'No'} variants found")

            # --- Validate AI Models ---
            aimodel = self._get_ai_model(aimodelname)
            if aimodel:
                print(f" Ai Model: '{aimodel.name}'")
            else:
                print(" WARNING: No ai model defined")

            for v_data in variants:
                variant_model = v_data.get("settings", {}).get("model")
                self._get_ai_model(variant_model)

            # --- Idempotency Check ---
            # We look for an existing version of this agent that matches source, settings, variants, and tasks
            latest_agent_version_in_db = agent.agent_versions.order_by("-version_number").first()  # type: ignore   # reverset lookup
            if latest_agent_version_in_db:
                print(f" Latest version in database: {latest_agent_version_in_db.version_number}")
            else:
                print(" No version in database")

            # Task declarations for comparison
            declarations = self._get_declarations()

            is_identical = False
            if latest_agent_version_in_db:
                # 1. Compare Settings
                st = latest_agent_version_in_db.settings
                settings_match = (
                    st.aimodel == aimodel and
                    st.max_retries == s.max_retries and
                    st.max_task_steps == s.max_task_steps and
                    st.unattended_steps == s.unattended_steps and
                    st.max_history_messages == s.max_history_messages and
                    json.dumps(st.input_schema or [], sort_keys=True) == json.dumps(input_schema, sort_keys=True) and
                    json.dumps(st.output_schema or {}, sort_keys=True) == json.dumps(output_schema, sort_keys=True) and
                    (st.task_prompt.content   if st.task_prompt   else None) == task_prompt and
                    (st.system_prompt.content if st.system_prompt else None) == system_prompt and
                    st.execution_mode == s.execution_mode and
                    st.tool_call_syntax == s.tool_call_syntax and
                    json.dumps(st.extra_settings or {}, sort_keys=True) == json.dumps(s.extra_settings, sort_keys=True)
                )
                print(f" > Setting {'equal' if settings_match else 'changed'}")
                # 2. Compare Source Code / subagents
                source_match = (
                    latest_agent_version_in_db.source.sourcecode == source_content and
                    json.dumps(latest_agent_version_in_db.source.subagent_names, sort_keys=True) == json.dumps(subagent_names, sort_keys=True) and
                    json.dumps(latest_agent_version_in_db.source.python_dependencies, sort_keys=True) == json.dumps(python_dependencies, sort_keys=True)
                )
                print(f" > Source {'equal' if source_match else 'changed'}")
                
                # 3. Compare Variants
                variants_match = json.dumps(latest_agent_version_in_db.variants, sort_keys=True) == json.dumps(variants, sort_keys=True)
                print(f" > Variants {'equal' if variants_match else 'changed'}")

                # 4. Compare Task Declarations
                
                #print("declarations", declarations)
                tasks_match = self._tasks_equal(latest_agent_version_in_db, declarations)
                print(f" > Task {'equal' if tasks_match else 'changed'}")

                if settings_match and source_match and variants_match and tasks_match:
                    is_identical = True

            print(f" >> {'No changes detected' if is_identical else 'Agent definition Changed'}")
            if is_identical:
                newest_agent_version = latest_agent_version_in_db
            else:
                # Create New Version
                source_obj = AgentSource.objects.create(
                    name = self.name,
                    path = source_path,
                    classname = self.agent_cls.__name__,
                    sourcecode = source_content,
                    subagent_names = subagent_names,
                    python_dependencies = python_dependencies
                )

                settings_obj = AgentSettings.objects.create(
                    aimodel = aimodel,
                    max_retries = s.max_retries,
                    max_task_steps = s.max_task_steps,
                    unattended_steps = s.unattended_steps,
                    max_history_messages = s.max_history_messages,
                    input_schema = input_schema,
                    output_schema = output_schema,
                    task_prompt = GenericContent.from_text(task_prompt) if task_prompt else None,
                    system_prompt = GenericContent.from_text(system_prompt) if system_prompt else None,
                    execution_mode = s.execution_mode,
                    tool_call_syntax = s.tool_call_syntax,
                    extra_settings = s.extra_settings
                )

                newest_agent_version = AgentVersion.objects.create(
                    agent=agent,
                    source=source_obj,
                    settings=settings_obj,
                    variants=variants,
                    version_number=latest_agent_version_in_db.version_number + 1 if latest_agent_version_in_db else 1
                )
                newest_agent_version.sub_agent_versions.set(subagents)
                #newest_agent_version.agent_tool_imports.set(tools)

                self._register_tasks( newest_agent_version, declarations)
                self._register_available_tools(newest_agent_version, imported_agent_versions)


            #AGENT_REGISTRY[self.agent_cls.__name__] = self.agent_cls
            self.agent_cls.is_registered = True
            self.agent_cls.agent = agent
            self.agent_cls.agent_version = newest_agent_version
            return newest_agent_version

    def _tasks_equal(self, latest_agent_version_in_db, declarations):
        # We check if the set of task definitions matches exactly
        if latest_agent_version_in_db.agent_task_definitions.count() != len(declarations):
            print(" Number of declared tasks changed")
            return False
        existing = {t.name: t for t in latest_agent_version_in_db.agent_task_definitions.all()}
        for name, decl in declarations.items():
            print(f" Comparing Task '{name}'")
            if name not in existing:
                print(" > Task is new")
                return False
            t = existing[name]
            if t.task_type != decl["task_type"]:
                print(" > Task type has changed")
                return False
            if t.trigger != (decl.get("trigger") or ""):
                print(" > Task trigger has changed")
                return False
            if t.description != (decl.get("description") or ""):
                print(" > Task description has changed")
                return False
            if json.dumps(t.function_schema or {}, sort_keys=True) != json.dumps(decl.get("schema", {}), sort_keys=True):
                print(" > Task schema has changed")
                return False
        print(" > No changes detected in tasks")
        return True

    def _register_tasks(self, newest_agent_version, declarations):
        task_objs = []
        for name, decl in declarations.items():
            canonical_function_schema = decl.get("schema", {})
            if not canonical_function_schema:
                canonical_function_schema = {}

            # Normalize trigger for consistent lookup and storage
            normalized_trigger = decl.get("trigger", "")
            if normalized_trigger is None: # Ensure None is always treated as empty string for consistency
                normalized_trigger = ""

            # Defensive step: Check for and clean up duplicate entries if they exist due to prior issues.
            # This ensures `update_or_create` does not encounter `MultipleObjectsReturned`.
            existing_tasks_filter_kwargs = {
                "name": name,
                "task_type": decl["task_type"],
                "description": decl.get("description", ""),
                "trigger": normalized_trigger,
                "function_schema": canonical_function_schema,
            }
            if requires_approval := decl.get("requires_approval", None):
                existing_tasks_filter_kwargs["requires_approval"] = requires_approval
            if max_retries := decl.get("max_retries", None):
                existing_tasks_filter_kwargs["max_retries"] = max_retries
            if retry_delay := decl.get("retry_delay", None):
                existing_tasks_filter_kwargs["retry_delay"] = retry_delay
            if retry_requires_approval := decl.get("retry_requires_approval", None):
                existing_tasks_filter_kwargs["retry_requires_approval"] = retry_requires_approval
                
            '''
            existing_tasks = latest_agent_version_in_db.agent_task_definitions.filter(**existing_tasks_filter_kwargs) if latest_agent_version_in_db else None
            if existing_tasks and existing_tasks.count() > 1:
                print(f"WARNING: Found {existing_tasks.count()} duplicate AgentTaskDefinitions for lookup {existing_tasks_filter_kwargs}. Deleting all but the first to prevent MultipleObjectsReturned.")
                # Keep the first one, delete the rest
                for duplicate_task in existing_tasks[1:]:
                    duplicate_task.delete()
             '''
            task_obj, created = AgentTaskDefinition.objects.get_or_create(
                **existing_tasks_filter_kwargs, # Use the same normalized fields for lookup
            )
            print("was created:", created)
            task_objs.append(task_obj)

        newest_agent_version.agent_task_definitions.set(task_objs)

    def _register_available_tools(self, newest_agent_version, imported_agent_versions, ):
        # Register available tools
        tools = []
        for imp in getattr(self.agent_cls, "tools", []):
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
                parent_agent_version = newest_agent_version,
                tool_agent_version = tool_agent_version,
                task_definition = tool_agent_task_definition
            )
            
    def _get_ai_model(self, model_name: str|None):
        if model_name is None:
            return None
        print("model_name", model_name)
        try:
            ai_model = AiModel.objects.get(name=model_name)
            if not ai_model.enabled:
                raise ValidationError(f"AI Model '{model_name}' exists but is not enabled.")
            return ai_model
        except AiModel.DoesNotExist as e:
            raise ValidationError(f"AI Model '{model_name}' specified in agent '{self.name}' does not exist in the database.") from e


    def _get_declarations(self):
        decls = {}
        # Iterate over all methods, including inherited ones
        for attr_name in dir(self.agent_cls):
            attr = getattr(self.agent_cls, attr_name, None)
            if attr and hasattr(attr, "_agent_decl"):
                decl = attr._agent_decl.copy()
                # Task/Tool schema generation if missing
                if not decl.get("schema") and decl["task_type"] in [TaskType.TOOL, TaskType.TASK, TaskType.COMMAND]:
                    # We pass the function to generate schema from its signature
                    description, decl["schema"] = self._generate_schema(attr)
                    decl["description"]  = description
                decls[decl["name"]] = decl
                #print(f' Found task "{decl.get("name")}"')
        #print("DCECLELCLEC", decls)
        return decls
    

    def _generate_schema(self, func):
        """
        Generates a robust JSON Schema for the function's parameters.
        Features:
        - Resolves full type hints (handles forward references and string annotations).
        - Extracts parameter descriptions from docstrings (Sphinx, Google, and Numpy styles).
        - Handles complex typing: Optional, Union, List, Dict, Literal, and Annotated.
        - Supports standard Python Enums.
        - Identifies required fields and includes default values.
        """
        import enum
        import re
        from typing import get_type_hints, get_origin, get_args, Annotated, Union, Literal, List, Dict
        
        sig = inspect.signature(func)
        
        # 1. Resolve Type Hints effectively
        try:
            # Using func.__globals__ allows resolving types imported in the agent's file
            type_hints = get_type_hints(func, globalns=func.__globals__)
        except Exception:
            # Fallback to parameter annotations if resolution fails
            type_hints = {name: param.annotation for name, param in sig.parameters.items()}

        # 2. Robust Docstring Parsing for parameter-level descriptions
        doc = inspect.getdoc(func) or ""
        param_descriptions = {}
        
        desc_lines = doc.splitlines()
        in_params_section = False
        current_param = None
        #print("desc_lines", desc_lines)
        description_lines=[]
        for line in desc_lines:
            stripped = line.strip()
            # Try Sphinx style: :param name: description
            sphinx_match = re.search(r":param\s+(\w+):\s*(.*)", stripped)
            if sphinx_match:
                param_descriptions[sphinx_match.group(1)] = sphinx_match.group(2).strip()
                continue
                
            # Detect section headers (Google/Numpy style)
            if stripped.lower() in ("args:", "parameters:", "params:"):
                in_params_section = True
                continue
            elif in_params_section and line and not line.startswith(" ") and line.endswith(":"):
                in_params_section = False
            
            if in_params_section:
                # Matches 'name (type): description' or 'name: description'
                param_match = re.search(r"^([\w\d_]+)\s*(?:\([^)]+\))?\s*:\s*(.*)", stripped)
                if param_match:
                    p_name, p_desc = param_match.groups()
                    param_descriptions[p_name] = p_desc.strip()
                    current_param = p_name
                elif current_param and line.startswith("    ") and stripped:
                    # Multi-line description continuation
                    param_descriptions[current_param] += " " + stripped
            else:
                description_lines.append(stripped)

        # 3. JSON Schema Mapping Logic
        def resolve_json_type(annotation):
            """Recursively maps Python types to JSON Schema types."""
            # Handle Annotated[T, metadata]
            if get_origin(annotation) is Annotated:
                inner_args = get_args(annotation)
                base = inner_args[0]
                schema = resolve_json_type(base)
                # Check for description metadata
                for meta in inner_args[1:]:
                    if isinstance(meta, str):
                        schema["description"] = meta
                    elif hasattr(meta, 'description'):
                        schema["description"] = getattr(meta, 'description')
                return schema

            origin = get_origin(annotation)
            args = get_args(annotation)

            # Handle Union (including Optional[T] which is Union[T, None])
            if origin is Union:
                pure_args = [a for a in args if a is not type(None)]
                if len(pure_args) == 1:
                    return resolve_json_type(pure_args[0])
                return {"anyOf": [resolve_json_type(a) for a in pure_args]}

            # Handle Literals (Enums equivalent in typing)
            if origin is Literal:
                return {"enum": list(args)}

            # Handle standard Python Enums
            if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
                return {
                    "type": "string",
                    "enum": [e.value for e in annotation],
                    "description": f"Must be one of: {', '.join([e.name for e in annotation])}"
                }

            # Handle Lists/Arrays
            if origin in (list, List) or annotation is list:
                item_schema = {"type": "string"}
                if args:
                    item_schema = resolve_json_type(args[0])
                return {"type": "array", "items": item_schema}
            
            # Handle Dicts/Objects
            if origin in (dict, Dict) or annotation is dict:
                return {"type": "object"}

            # Primitive Mapping
            mapping = {
                str: "string", int: "integer", float: "number", bool: "boolean", bytes: "string",
            }
            # Fallback for common string-named types
            if annotation == "str": 
                return {"type": "string"}
            if annotation == "int": 
                return {"type": "integer"}
            if annotation == "float": 
                return {"type": "number"}
            if annotation == "bool": 
                return {"type": "boolean"}

            return {"type": mapping.get(annotation, "string")}

        # 4. Construct Final Parameters Object
        params_schema = {"type": "object", "properties": {}, "required": []}

        for name, param in sig.parameters.items():
            # Skip framework-specific arguments
            if name in ["self", "task_run", "task_context"]:
                continue

            # Generate type schema
            p_annotation = type_hints.get(name, param.annotation)
            field_schema = resolve_json_type(p_annotation)
            
            # Attach description from docstring if metadata didn't provide one
            if "description" not in field_schema or not field_schema["description"]:
                field_schema["description"] = param_descriptions.get(name, "")

            # Set Default vs Required
            if param.default is inspect.Parameter.empty:
                params_schema["required"].append(name)
            else:
                field_schema["default"] = param.default

            params_schema["properties"][name] = field_schema
        description = "\n".join(description_lines)
        #params_schema["description"] = description
        return description, params_schema