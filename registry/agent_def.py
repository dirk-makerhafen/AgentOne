from __future__ import annotations
from functools import wraps
import inspect
import json
import random
import ast

from typing import List, Any, Dict, Type, Union
from django.db import transaction
import re
from typing import get_type_hints, get_origin, get_args, Annotated, Union, Literal, List, Dict
from runtime.context_manager import RuntimeContextTracker
from registry.agent_registry import AgentRegistry
from server.models.agents.agent_instance_version import AgentInstanceVersion
from server.models.enums.task_enums import TaskType
from server.models.agents.agent import Agent
from server.models.agents.agent_profile import AgentProfile
from server.models.agents.agent_version import AgentVersion, AgentVersionAvailableTool

from server.models.providers.ai_model import AiModel
from server.models.tasks.agent_task_definition import AgentTaskDefinition
from registry.profile_def import ProfileDef
from registry.task_decorators import TaskDescriptor
from django.core.exceptions import ValidationError
from server.models.agents.agent_instance import AgentInstance

from server.models.content import GenericContent
from registry.utils import generate_schema_for_function, get_import_strings, get_ai_model

class AgentDef():
    parent: Agent
    agent: Agent
    agent_version: AgentVersion
    agent_instance: AgentInstance
    agent_instance_version: AgentInstanceVersion
    is_registered = False

    def __init__(self, name=None, workingdir = None, profile = None, agent_instance_version=None):
        if not workingdir and self.parent and self.parent.agent_instance_version:
            workingdir = self.parent.agent_instance_version.workingdir
        parent_agent_instance = self.parent.agent_instance if self.parent else None
        print("parent_agent_instance", parent_agent_instance)
        if not agent_instance_version:
            try:
                self._reload_is_registered()
            except Exception as e:
                pass
        else:
            self.agent = agent_instance_version.agent
            self.agent_version = agent_instance_version.agent_version
            self.is_registered = True
        #if not self.is_registered:
        #    raise Exception("Must be registered to instanciate")
        self.agent_instance_version = agent_instance_version
        if not self.agent_instance_version:
            self.agent_instance_version = self.agent_version.get_or_create_instance(name=name, workingdir=workingdir, parent_instance=parent_agent_instance)
        self.agent_instance = self.agent_instance_version.agent_instance
        self.workingdir =  self.agent_instance_version.workingdir
        self.is_registered = True

    def __init_subclass__(cls, **kwargs):
        #super().__init_subclass__(**kwargs)
        original_init = cls.__init__
        print("__init_subclass__")
        @wraps(original_init)
        def wrapped_init(self, *args, **kwargs):
            print("wrapped_init")
            self.id = f"{cls.__name__}:{random.random():.5f}"
            self.parent = RuntimeContextTracker.current
            self.agent = None
            self.agent_version = None
            self.agent_instance = None
            self.agent_instance_version = None
            self.is_registered = False
            print("AgentRuntime.__init__1", self.parent, self, self.__class__, type(self), type( self.parent))
            with RuntimeContextTracker(self):
                original_init(self, *args, **kwargs)

        cls.__init__ = wrapped_init


    def _reload_is_registered(self):
        agent, created = Agent.objects.get_or_create(name=self.__class__.__name__, defaults={"description": getattr(self.__class__, "description", ""),})
        agent_version = agent.agent_versions.order_by("-version_number").first() if agent else None
        self.agent = agent
        self.agent_version = agent_version
        source_path = inspect.getfile( self.__class__)
        source_code = inspect.getsource( self.__class__)
        python_dependencies = get_import_strings(source_path, self.__class__.__name__) # Remove duplicates and sort for consistency
        
        source_changed = not agent_version or agent_version.source_path != source_path or agent_version.source_code.get() != source_code
        python_dependencies_changed = not agent_version or agent_version.python_dependencies != python_dependencies
        imported_sub_agents_changed = False  #todo
        imported_tool_agents_changed = False  #todo
        print("self.source_changed", source_changed)
        print("self.python_dependencies_changed", python_dependencies_changed)
        print(" agent_version.python_dependencies",  agent_version.python_dependencies)
        print("python_dependencies", python_dependencies)
        self.is_registered = not(source_changed or python_dependencies_changed or imported_sub_agents_changed  or imported_tool_agents_changed )
        print("self.is_registered", self.is_registered)
        if self.is_registered:
            self.agent = agent
            self.agent_version = agent_version

    @classmethod
    def register(cls, recursive=False):
        ar = AgentRegistry()
        return ar.register(cls,recursive=recursive)

    