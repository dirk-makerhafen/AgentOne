from __future__ import annotations

from contextlib import contextmanager
import sys
from typing import Any, Dict, Optional, Type
from cachetools import LRUCache
from django.db import models
from django.core.exceptions import ValidationError

from runtime.agents.agent import Agent
from server.models.settings import SettingsModel
from server.models.base_model import BaseModel
from server.models.content import GenericContent
from pathlib import Path

from typing import TYPE_CHECKING
from server.models.skills.skill_version import SkillModelVersion
from server.models.tasks.task_definition_version import TaskDefinitionVersion
from sortedm2m.fields import SortedManyToManyField

if TYPE_CHECKING:
    from server.models.sessions.session_version import SessionVersionModel

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


class AgentVersionModel(BaseModel):
    """
    A versioned snapshot of an agent 
    """    
    agent = models.ForeignKey("server.AgentModel"        , on_delete=models.CASCADE, related_name="related_agent_versions")

    description = models.TextField(max_length=65500, default="")

    extends_agent_names = models.JSONField(default=list, blank=True)
    extends_agent_versions = SortedManyToManyField("self", related_name="related_inheritors", default=None, symmetrical=False, )

    defined_skill_versions = models.ManyToManyField(SkillModelVersion ,default=None,  related_name="related_agent_versions", symmetrical=False) # top level profile
    defined_task_versions = models.ManyToManyField(TaskDefinitionVersion ,default=None,related_name="related_agent_versions", symmetrical=False) # top level profile
    defined_subagent_versions = models.ManyToManyField("self", related_name="related_parents", default=None, symmetrical=False, )

    agent_settings = models.ForeignKey(SettingsModel ,default=None,null=True, on_delete=models.SET_NULL, related_name="related_agent_versions") # top level profile

    version_number = models.IntegerField(default=0)
    commit = models.CharField(max_length=1024, default="")
    hash = models.CharField(max_length=1024, default="")

    class Meta:
        unique_together = ("agent", "version_number")

    def get_or_create_instance(self, name:Optional[str] = None, display_name:Optional[str]=None, workingdir: Optional[str|Path] = None, parent_instance_version:SessionVersionModel|None=None) -> SessionVersionModel:
        from server.models.sessions.session import SessionModel
        from server.models.sessions.session_version import SessionVersionModel
        if not workingdir and parent_instance_version:
            workingdir = parent_instance_version.workingdir
        if workingdir:
            workingdir = Path(workingdir).resolve()
        parent_instance = parent_instance_version.session if parent_instance_version else None
        if not name:
            name = f"p{parent_instance.pk}:{self.agent.name}" if parent_instance else f"default:{self.agent.name}"

        if not display_name:
            display_name = f"{self.agent.name}"

        session, _ = SessionModel.objects.get_or_create(
            name = name,
            defaults = dict(
                created_by = parent_instance,
            )
        )
        session_version = session.latest_session_version
        aiv_created = False
        if not session_version \
            or session_version.agent_version != self \
            or session_version.session != session \
            or session_version.workingdir != workingdir:
                session_version, aiv_created = SessionVersionModel.objects.get_or_create(
                    agent = self.agent,
                    agent_version = self,
                    session = session,
                    workingdir = workingdir,
                    display_name = display_name,
                    defaults = dict(
                        created_by = parent_instance_version,
                    )
                )
        if aiv_created:
            SessionModel.objects.filter(pk=session.pk).update(latest_session_version=session_version)
            
        if parent_instance_version:
            parent_instance_version.child_session_versions.add(session_version)
        return session_version

    def get_runtime(self):
        return Agent(agent_model=self.agent, pinned_agent_version=self)

    def _resolve_property(self, name:str) -> Any:
        # check inherited values if our is not set
        
        extend_at_index = None
        if (value := getattr(self, name)) is not None:
            if isinstance(value, (str,int,bool, GenericContent)):
                return value
            if isinstance(value, (list,)):
                if "*" not in value: # overwrite parent list 
                    return value
                extend_at_index = value.index("*")
            else:
                raise Exception(f"_resolve_property does not yet support type of '{name}': {type(value)}")
        #for extendsAgentVersion in self.extends_agent_versions.all():
        print(list(self.extendsAgent.all()))
        for extendsAgent in self.extendsAgent.all():
            extendsAgentVersion = extendsAgent.latest_agent_version
            print("extendsAgentVersion", extendsAgentVersion)
            if (ext_value := extendsAgentVersion._resolve_property(name)) is not None:
                if isinstance(value, (list,)) and extend_at_index is not None:
                    value[extend_at_index:extend_at_index+1] = ext_value
                else:
                    return ext_value
        return value

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs) 

    def __str__(self):
        return f"{self.agent.name} v{self.version_number}"
