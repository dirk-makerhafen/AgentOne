from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import models

from server.models.base_model import BaseModel
from server.models.tasks.task_definition_version import TaskDefinitionVersion


class TaskDefinition(BaseModel):
    """Uniquely identifies a task across all versions.

    Each TaskDefinition has one canonical latest version
    and may be owned by a skill, agent, or project.
    """

    parent_skill = models.ForeignKey("server.SkillModel",default=None,null=True,blank=True,on_delete=models.CASCADE,related_name="related_task_definitions")
    parent_agent = models.ForeignKey("server.AgentModel",default=None,null=True,blank=True,on_delete=models.CASCADE,related_name="related_task_definitions")
    parent_project = models.ForeignKey("server.Project",default=None,null=True,blank=True,on_delete=models.CASCADE,related_name="related_task_definitions")
    parent_generation = models.ForeignKey("server.ScriptsGeneration",default=None,null=True,blank=True,on_delete=models.CASCADE,related_name="related_task_definitions")

    name = models.CharField(max_length=255)
    group_name =  models.CharField(max_length=255, default="")
    # Filesystem access posture declared in the manifest: "read", "write", or
    # None (unspecified — inferred from group_name at guardrail time).
    access_posture = models.CharField(max_length=16, default=None, null=True, blank=True, choices=[("read", "read"), ("write", "write")])
    latest_task_version = models.ForeignKey(TaskDefinitionVersion,default=None,null=True,on_delete=models.SET_NULL,related_name="related_newest_task")

    observable_fields = set([
        "pk",
        "parent_skill",
        "parent_agent",
        "parent_project",
        "parent_generation",
    ])
    
    class Meta:
        unique_together = ["parent_skill", "parent_agent", "parent_project", "name"]



    @property
    def observable_keys(self):
        return set([
            "TaskDefinition",
            f"TaskDefinition.pk:{self.pk}",
            f"TaskDefinition.parent_skill:{self.parent_skill_pk}",
            f"TaskDefinition.parent_agent:{self.parent_agent_pk}",
            f"TaskDefinition.parent_project:{self.parent_project_pk}",
            f"TaskDefinition.parent_generation:{self.parent_generation_pk}",
        ])

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Prevent updates to existing TaskDefinition instances."""
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"TaskDefinition[{self.name} pk:{self.pk}]"
