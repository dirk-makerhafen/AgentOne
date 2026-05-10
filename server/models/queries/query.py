from django.db import models
from django_enum import EnumField
from server.models.base_model import BaseModel
from django.core.exceptions import ValidationError

class QueryStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    WAITING = 'WAITING', 'Waiting (System Blocked)'
    SUCCESS = 'SUCCESS', 'Success (Terminal)'
    FAILURE = 'FAILURE', 'Failure (Terminal)'

class QueryAvailableTool(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    query = models.ForeignKey("server.Query", related_name="available_tools", on_delete=models.CASCADE)
    tool_agent_version  = models.ForeignKey("server.AgentVersionModel", related_name="related_query_available_tools", on_delete=models.CASCADE)
    task_definition = models.ForeignKey("server.TaskDefinition", blank=True, on_delete=models.CASCADE)

class Query(BaseModel):
    aimodel        = models.ForeignKey("server.AiModel"        , null=False, on_delete=models.CASCADE, related_name="related_queries")
    apikey         = models.ForeignKey("server.ApiKey"         , null=True , on_delete=models.SET_NULL,related_name="related_queries", blank=True)
    agent_instance_version = models.ForeignKey("server.InstanceVersionModel", null=False, on_delete=models.CASCADE, related_name='related_queries')
    agent_profile  = models.ForeignKey("server.ProfileModel" , null=True , on_delete=models.CASCADE, related_name='related_queries', blank=True)

    status = EnumField(QueryStatus, default=QueryStatus.WAITING)

    tags_token_usage = models.JSONField(default=dict, null=True, blank=True)
    tokens =  models.IntegerField(default=None, blank=True, null=True)

    @property
    def conversation_messages(self):
        return self.related_conversation_messages # pyright: ignore[reportAttributeAccessIssue]

    @property
    def response(self):
        return self.related_response # pyright: ignore[reportAttributeAccessIssue]

    def compile(self):
        messages = []
        tokens = 0
        tags_token_usages = []
        for message in self.query_messages.all().order_by("index", "-pk"):
            try:
                qm =  message.compile()
                messages.append(qm)
                tokens += message.tokens
                tags_token_usages.append(message.tags_token_usage)
            except Exception as e:
                print("Failed to compile", message)
                raise e
        tags_token_usage = self.merge_tag_usage(tags_token_usages)
        if self.tokens != tokens:
            self.tokens = tokens
            self.tags_token_usage = tags_token_usage
            self.save()
        return messages

    def merge_tag_usage(self, list_of_tag_dicts):
        def merge_into(a, b):
            for key, bval in b.items():
                if key == "tokens":
                    a["tokens"] = a.get("tokens", 0) + bval
                else:
                    if key not in a:
                        a[key] = {}
                    merge_into(a[key], bval)
            return a
        result = {}
        for d in list_of_tag_dicts:
            merge_into(result, d)
        return result

    def save(self, *args, **kwargs):
        #if self.pk:
        #    raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs) 
