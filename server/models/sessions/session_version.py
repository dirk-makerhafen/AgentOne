from __future__ import annotations

from typing import Any

from cachetools import LRUCache
from django.core.exceptions import ValidationError
from django.db import models

from runtime.session.session import Session
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.base_model import BaseModel
from server.models.sessions.session import SessionModel

AGENT_INSTANCE_VERSION_RUNTIME_CLASS_INSTANCE_CACHE = LRUCache(maxsize=1024)


class SessionVersionModel(BaseModel):
    """A versioned snapshot of a session's configuration and agent binding."""

    session = models.ForeignKey(SessionModel, on_delete=models.CASCADE, related_name="related_session_versions")
    agent = models.ForeignKey(AgentModel, on_delete=models.CASCADE, related_name="related_session_versions")
    pinned_agent_version = models.ForeignKey(AgentVersionModel,on_delete=models.CASCADE,related_name="related_session_versions",default=None,null=True,blank=True)

    parent_session_version = models.ForeignKey("self",on_delete=models.CASCADE,related_name="created_session_versions",default=None,null=True,blank=True)
    workspace = models.ForeignKey("server.WorkspaceModel",on_delete=models.CASCADE,related_name="related_session_versions",default=None,null=True,blank=True)

    name = models.CharField(max_length=255, default="", blank=True)
    display_name = models.CharField(max_length=2048, default=None, blank=True, null=True)
    description = models.TextField(max_length=65500, default="", blank=True)

    child_session_versions = models.ManyToManyField("self", related_name="parent_session_versions", default=None, blank=True, symmetrical=False)
    session_settings = models.ForeignKey("server.SettingsModel",on_delete=models.SET_NULL,default=None,null=True,blank=True,related_name="related_instance_versions")
    version_number = models.IntegerField(default=0)

    observable_fields = set([
        "pk",
        "session",  
        "agent",
        "pinned_agent_version",      
        "parent_session_version",
        "workspace",    
    ])

    @property
    def observable_keys(self):
        return set([
            "SessionVersionModel",
            f"SessionVersionModel.pk:{self.pk}",
            f"SessionVersionModel.session:{self.session_pk}",
            f"SessionVersionModel.agent:{self.agent_pk}",
            f"SessionVersionModel.pinned_agent_version:{self.pinned_agent_version_pk}",
            f"SessionVersionModel.parent_session_version:{self.parent_session_version_pk}",
            f"SessionVersionModel.workspace:{self.workspace_pk}",
        ])

    def get_runtime(self) -> Session:
        """Return a runtime Session wrapper pinned to this version."""
        return Session(session_model=self.session, pinned_session_version=self)

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Prevent updates to existing SessionVersionModel instances."""
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return (
            f"<AgentInstance#{self.session.pk}'{self.session.name}'"
            f"__AgentInstanceVersion#{self.pk}>"
        )
