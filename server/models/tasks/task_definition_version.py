from django.db import models
from server.models.base_model import BaseModel
from server.models.enums.task_enums import TaskType  
from django.core.exceptions import ValidationError
from sortedm2m.fields import SortedManyToManyField

class TaskDefinitionVersion(BaseModel):
    task_definition = models.ForeignKey("server.TaskDefinition", default=None, null=True, on_delete=models.CASCADE, related_name='versions')# for */someproject/.agentone/skills/ , null for global skill in ~/.agentone/skills

    description     = models.TextField()
    function_schema = models.JSONField()

    # Options - Startup
    requires_approval = models.BooleanField(default=False)  # required user approval before run
    
    # Options - Run
    time_limit      = models.IntegerField(default=None, null=True)     #   
    max_subtask_errors     = models.IntegerField(default=0)   # for groups,absolute number, also used when timeout
    max_subtask_error_rate = models.IntegerField(default=0)# for groups, in percent, also used when timeout
    limit_subtask_parallel_runs  = models.IntegerField(default=0) # how many subtasks cn run in parallel, for groups 0=no limit
    limit_per_instance_parallel_runs  = models.IntegerField(default=1) #how many times this task can run in parallel per agentInstance it belongs to, 0=no limit
    priority = models.IntegerField(default=0)   # 0 = highest, 1..999 less important

    # Options - Retry
    max_retries  = models.IntegerField(default=0)   # how many retries to we make in case of error
    retry_delay  = models.IntegerField(default=10)  # time between retries in seconds
    retry_requires_approval = models.BooleanField(default=True)  # required user approval before run

    trigger = models.CharField(max_length=255, default=None, blank=True, null=True)

    path = models.CharField(max_length=1024, default=None, blank=True, null=True)
    commit = models.CharField(max_length=1024, default="")

    child_tasks = SortedManyToManyField("self", help_text="", symmetrical=False, blank=True, related_name="parent_tasks")

    @property
    def agent_task_instances(self):
        return self.related_agent_task_instances # pyright: ignore[reportAttributeAccessIssue]

    @property
    def agent_versions(self):
        return self.related_agent_versions # pyright: ignore[reportAttributeAccessIssue]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"TaskDefinitionVersion[{self.task_definition.name if self.task_definition else ''} pk:{self.pk}]"

