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
from registry.profile import Profile
from django.core.exceptions import ValidationError
from server.models.agents.agent_instance import AgentInstance

from server.models.content import GenericContent
from registry.utils import generate_schema_for_function, get_import_strings, get_ai_model

class AgentDef():
    """
    Base class for all agent definitions.
 
    Class-level attributes (agent, agent_version, etc.) are populated either by
    AgentRegistry.register() at startup, or lazily by _reload_is_registered() at
    first instantiation. Instance-level attributes shadow them after __init__ runs.
    """
    profile= Profile()
    parent: "AgentDef | None"
    agent: Agent
    agent_version: AgentVersion
    agent_instance: AgentInstance
    agent_instance_version: AgentInstanceVersion
    is_registered: bool = False
    def __init__(self, name=None, workingdir=None, profile=None, agent_instance_version=None):
        # Inherit workingdir from parent agent if not explicitly provided.
        if not workingdir and self.parent and self.parent.agent_instance_version:
            workingdir = self.parent.agent_instance_version.workingdir
 
        parent_agent_instance = self.parent.agent_instance if self.parent else None
 
        if not agent_instance_version:
            # No instance version injected (normal construction path) — check whether
            # this agent class is already registered in the DB. This is a lightweight
            # check; full re-registration with sub-agent diff is handled by AgentRegistry.
            try:
                self._reload_is_registered()
            except Exception as e:
                pass
        else:
            # Instance version was injected directly (runtime loading path via
            # AgentInstanceVersion.get_runtime_instance). Trust it, skip DB check.
            self.agent = agent_instance_version.agent
            self.agent_version = agent_instance_version.agent_version
            self.is_registered = True
 
        self.agent_instance_version = agent_instance_version
        if not self.agent_instance_version:
            self.agent_instance_version = self.agent_version.get_or_create_instance(
                name=name,
                workingdir=workingdir,
                parent_instance=parent_agent_instance,
            )
 
        self.agent_instance = self.agent_instance_version.agent_instance
        self.workingdir = self.agent_instance_version.workingdir
        self.is_registered = True

        
    def __init_subclass__(cls, **kwargs):
        """
        Wraps __init__ for every subclass of AgentDef (ChatAgent, BaseAgent, etc.)
        to inject two behaviours before the real __init__ runs:
 
          1. Parent tracking: set self.parent to the AgentDef instance currently
             active on the RuntimeContextTracker stack. This captures the agent that
             is constructing this one (e.g. a parent agent spinning up a sub-agent).
 
          2. Instance reset: clear all instance-level agent attributes so each new
             instance starts clean, regardless of what is cached on the class.
 
        Why the try/except for self.parent:
            __init_subclass__ fires once per class in the MRO, so for a hierarchy
            like ChatAgent -> BaseAgent -> AgentDef, three wrappers are composed.
            The outermost wrapper (ChatAgent's) runs first and sets self.parent.
            The inner wrappers (BaseAgent's, AgentDef's) must NOT overwrite it —
            self.parent is already correct by the time they execute. The
            AttributeError guard achieves this: only the first wrapper to run
            (which finds no self.parent yet) actually sets it from the tracker.
        """
        original_init = cls.__init__
 
        @wraps(original_init)
        def wrapped_init(self, *args, **kwargs):
            self.id = f"{cls.__name__}:{random.random():.5f}"
 
            # Only set parent if not already set by an outer (more-derived) wrapper.
            try:
                _ = self.parent  # will raise AttributeError on first (outermost) call
            except AttributeError:
                self.parent = RuntimeContextTracker.current
 
            # Reset instance state so class-level cached values don't bleed through.
            self.profile = None
            self.agent = None
            self.agent_version = None
            self.agent_instance = None
            self.agent_instance_version = None
            self.is_registered = False
 
            # Push self onto the context stack so any agents constructed during
            # __init__ (sub-agents) will find this instance as their parent.
            with RuntimeContextTracker(self):
                original_init(self, *args, **kwargs)
 
        cls.__init__ = wrapped_init

    def _reload_is_registered(self):
        """
        Lightweight DB check: is this agent class already registered and up-to-date?
        Only compares own source code and direct Python dependencies.
        Sub-agent and tool diffs are handled by AgentRegistry.register().
        Sets self.agent and self.agent_version as a side effect.
        """
        agent, created = Agent.objects.get_or_create(
            name=self.__class__.__name__,
            defaults={"description": getattr(self.__class__, "description", "")},
        )
        agent_version = agent.agent_versions.order_by("-version_number").first() if agent else None
        self.agent = agent
        self.agent_version = agent_version
 
        source_path = inspect.getfile(self.__class__)
        source_code = inspect.getsource(self.__class__)
        python_dependencies = get_import_strings(source_path, self.__class__.__name__)
 
        source_changed = (
            not agent_version
            or agent_version.source_path != source_path
            or agent_version.source_code.content != source_code  # GenericContent.content field
        )
        python_dependencies_changed = (
            not agent_version
            or agent_version.python_dependencies != python_dependencies
        )
 
        self.is_registered = not (source_changed or python_dependencies_changed)
 
    @classmethod
    def register(cls, recursive=False):
        ar = AgentRegistry()
        return ar.register(cls,recursive=recursive)

    