from django.db import models
from server.models.base_model import BaseModel
from server.models.enums.task_enums import TaskType  
from django.core.exceptions import ValidationError

from server.models.tasks.task_definition_version import TaskDefinitionVersion

class TaskDefinition(BaseModel):
    parent_skill = models.ForeignKey("server.SkillModel", default=None, null=True, on_delete=models.CASCADE, related_name='related_task_definitions')# for */.agentone/Agent/someagent/skills/ , null for global skill in ~/.agentone/skills
    parent_agent = models.ForeignKey("server.AgentModel", default=None, null=True, on_delete=models.CASCADE, related_name='related_task_definitions')# for */.agentone/Agent/someagent/skills/ , null for global skill in ~/.agentone/skills
    parent_project = models.ForeignKey("server.Project", default=None, null=True, on_delete=models.CASCADE, related_name='related_task_definitions')# for */someproject/.agentone/skills/ , null for global skill in ~/.agentone/skills
    
    name            = models.CharField(max_length=255)
    task_type       = models.CharField(max_length=20, choices=TaskType.choices)
    latest_task_version = models.ForeignKey(TaskDefinitionVersion, default=None, null=True, on_delete=models.SET_NULL, related_name='related_newest_task')

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"TaskDefinition[{self.name} pk:{self.pk}]"

