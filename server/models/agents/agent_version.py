from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import time
import os
import random
import re
import sys
import traceback
from typing import Dict, Type
from cachetools import LRUCache
from django.db import models
from django.core.exceptions import ValidationError

from server.models.agents.agent_profile import AgentProfile
from server.models.base_model import BaseModel
from server.models.content import GenericContent
from pathlib import Path

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from server.models.agents.agent_instance import AgentInstance
    from server.models.agents.agent_instance_version import AgentInstanceVersion

AGENT_VERSION_RUNTIME_CLASS_CACHE = LRUCache(maxsize=1024)

@contextmanager
def temp_sys_path(path:Path):
    """Temporarily adds a directory to sys.path."""
    pathstr = path.as_posix()
    if pathstr not in sys.path:
        sys.path.insert(0, pathstr)
        try:
            yield
        finally:
            sys.path.remove(pathstr)
    else:
        yield
        
class AgentVersionAvailableTool(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    parent_agent_version = models.ForeignKey("server.AgentVersion", related_name="available_tools", on_delete=models.CASCADE)
    tool_agent_version  = models.ForeignKey("server.AgentVersion", related_name="related_version_available_tools", on_delete=models.CASCADE)
    task_definition = models.ForeignKey("server.AgentTaskDefinition", blank=True, on_delete=models.CASCADE)


class AgentVersion(BaseModel):
    """
    A versioned snapshot of an agent 
    """
    agent    = models.ForeignKey("server.Agent"        , on_delete=models.CASCADE, related_name="related_agent_versions")
    profile = models.ForeignKey("server.AgentProfile" , on_delete=models.CASCADE, related_name="related_agent_versions") # top level profile
    parent   = models.ForeignKey("self"                , on_delete=models.CASCADE, related_name="child_agent_versions", default=None, null=True, blank=True)
    task_definitions = models.ManyToManyField("server.AgentTaskDefinition", symmetrical=False, blank=True, related_name="related_agent_versions")

    sub_agent_versions  = models.ManyToManyField("self"                      , symmetrical=False, blank=True, related_name="imported_by_agent_versions")

    # SOURCE CODE
    source_path = models.TextField(default=None, max_length=2048)
    source_code = models.ForeignKey(GenericContent,  default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="agent_version_source_code")
    class_name  = models.CharField(max_length=255)
    python_dependencies    = models.JSONField(default=list, blank=True)

    subagent_names    = models.JSONField(default=list)

    version_number = models.IntegerField()

    class Meta:
        unique_together = ("agent", "version_number")

    @property
    def tools(self):
        return self.available_tools

    @property
    def conversation_messages(self):
        return self.related_conversation_messages # pyright: ignore[reportAttributeAccessIssue]

    @property
    def queries(self):
        return self.related_queries # pyright: ignore[reportAttributeAccessIssue]

    @property
    def responses(self):
        return self.related_responses # pyright: ignore[reportAttributeAccessIssue]

    @property
    def agent_instance_versions(self):
        return self.related_agent_instance_versions # pyright: ignore[reportAttributeAccessIssue]

    @property
    def agent_task_calls(self):
        return self.related_agent_task_calls # pyright: ignore[reportAttributeAccessIssue]

    def get_or_create_instance(self, name = None, workingdir = None, parent_instance:AgentInstance|None=None) -> AgentInstanceVersion:
        from server.models.agents.agent_instance import AgentInstance
        from server.models.agents.agent_instance_version import AgentInstanceVersion

        if not name:
            name = "default"
        if workingdir:
            workingdir = Path(workingdir).resolve()

        agent_instance, acreated = AgentInstance.objects.get_or_create(name=name, agent=self.agent, parent= parent_instance)
        agent_instance_version = agent_instance.latest_agent_instance_version
        if agent_instance_version:
            print("latest_agent_instance_version", agent_instance_version.pk, "self", self.pk)     
            print("agent_version",  agent_instance_version.agent_version, self, agent_instance_version.workingdir, workingdir)
            if  agent_instance_version.agent_version == self and agent_instance_version.workingdir == workingdir:
                print("return here, is up to data", agent_instance_version)
                if parent_instance:
                    print("parent_instance.agent.name", parent_instance.agent.name)
                    parent_instance.latest_agent_instance_version.child_agent_instance_versions.add(agent_instance_version)
                return agent_instance_version
        else:
            print("NO CURRENT agent_instance_version", agent_instance_version)
        print("agent_instance", agent_instance.pk, "parent_instance", parent_instance)
        new_instance_version, created = AgentInstanceVersion.objects.get_or_create(
            agent = self.agent,
            agent_version = self,
            agent_instance = agent_instance,
            workingdir = workingdir,
        )

        if parent_instance:
            print("parent_instance.agent.name", parent_instance.agent.name if parent_instance else "no parent",  parent_instance.latest_agent_instance_version if parent_instance else "no last",  parent_instance.latest_agent_instance_version if parent_instance else "", new_instance_version)
            parent_instance.latest_agent_instance_version.child_agent_instance_versions.add(new_instance_version)
        print(new_instance_version)
        return new_instance_version

    def get_runtime_class(self):
        if not self.pk:
            raise Exception("Cant get runtime class, save AgentVersion model first")

        from server.models.agents.agent_instance_version import AgentInstanceVersion
        from server.models.agents.agent_instance import AgentInstance
        from server.models.agents.agent_profile import AgentProfile
        from server.models.agents.agent_version import AgentVersion
        from server.models.agents.agent import Agent

        from server.models.enums.message_enums import MessageRole, MessageSource, MessageContentType
        from server.models.enums.task_enums import TaskType
        from server.models.enums.hook_type import HookType

        from server.models.providers.ai_model import AiModel
        from server.models.providers.api_key import ApiKey
        from server.models.providers.api_provider import ApiProvider

        from server.models.queries.query import Query
        from server.models.queries.query_message import QueryMessage
        from server.models.queries.query_message_part import QueryMessagePart
        from server.models.queries.response import Response

        from server.models.tasks.agent_task_call import AgentTaskCall
        from server.models.tasks.agent_task_definition import AgentTaskDefinition
        from server.models.tasks.agent_task_instance import AgentTaskInstance
        from server.models.tasks.agent_task_run import AgentTaskRun
        
        from server.models.conversation_message import ConversationMessage
        from server.models.conversation_message_part import ConversationMessagePart

        from tools.builtin_filesystem.filesystem_api import FilesystemApi

        from registry import task_decorators 
        from registry.agent_def import AgentDef
        from registry.profile import Profile
        from registry.task_decorators import task, command, instance, hook,chain, tool

        if not self.source_code:
            raise ValueError(f"Agent {self.agent.name} has no pinned version or source to load from.")

        try:
            # Prepare execution environment
            '''
            exec_globals = {
                "__builtins__": __builtins__, 
                # Agents
                "AgentInstanceVersion": AgentInstanceVersion,  
                "AgentInstance": AgentInstance,
                "AgentProfile": AgentProfile,
                "AgentVersion": self.__class__,
                "Agent": self.agent.__class__, 
                # Providers
                "AiModel": AiModel, 
                "ApiKey": ApiKey, 
                "ApiProvider": ApiProvider, 
                # Queries
                "QueryMessagePart": QueryMessagePart,
                "QueryMessage": QueryMessage,
                "Query": Query,
                "Response": Response,
                # Tasks
                "AgentTaskCall": AgentTaskCall,
                "AgentTaskDefinition": AgentTaskDefinition,
                "AgentTaskInstance": AgentTaskInstance,
                "AgentTaskRun": AgentTaskRun,
                # Decorators
                "task_decorators": task_decorators,
                "task": task,
                "hook": hook,
                "tool": tool,
                "chain": chain,
                "command": command,
                "instance": instance,
                # Enums
                "HookType": HookType,
                "MessageRole": MessageRole,
                "Message": MessageRole,
                "MessageSource": MessageSource,
                "MessageContentType": MessageContentType, 
                # Conversation
                "ConversationMessage": ConversationMessage,
                "ConversationMessagePart": ConversationMessagePart,
                # OTHER
                "GenericContent": GenericContent,
                "FilesystemApi": FilesystemApi,
            }''' # removed for now, maybe forever, bevause its been replaced by python_dependencies 
            exec_globals = {
                    "__builtins__": __builtins__,
            }
            for sub_agent_version in self.sub_agent_versions.all():
                imported_agent_class = sub_agent_version.get_runtime_class()
                exec_globals[imported_agent_class.__name__] = imported_agent_class

            python_dependencies = f'\n{"\n".join(self.python_dependencies)}'
            python_dependencies = python_dependencies.replace("\nfrom AgentOne.public ", "\nfrom public ")
            src = f"{python_dependencies}\n{self.source_code.content}"
            print(f"##############\n{src}\n#####################")
            print(Path(self.source_path).parent)
            print(Path(self.source_path).parent.parent)
            print(Path(self.source_path).parent.parent.parent)
            print(Path(self.source_path).parent.parent.parent.parent)
            
            with temp_sys_path(Path(self.source_path).parent):
                with temp_sys_path(Path(self.source_path).parent.parent):
                    with temp_sys_path(Path(self.source_path).parent.parent.parent):
                        exec(src, exec_globals) # Execute the source code
  
            agent_class = exec_globals.get(self.agent.name)
            if not agent_class:
                raise ValueError(f"Agent class {self.agent.name} not found after exec in pinned version source.")

            agent_class.agent = self.agent
            agent_class.agent_version = self
            #AGENT_VERSION_RUNTIME_CLASS_CACHE[self.pk] = agent_class
            return agent_class

        except Exception as e:
            raise ValueError(f"Error dynamically loading agent class {self.agent.name} from pinned version source: {e}")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs) 

    def __str__(self):
        return f"{self.agent.name} v{self.version_number}"
