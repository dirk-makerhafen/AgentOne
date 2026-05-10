from django.db import models
from server.models.content import GenericContent
from django_enum import EnumField
from server.models.base_model import BaseModel

class ResponseStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active' # query is active
    WAITING = 'WAITING', 'Waiting (System Blocked)' # tool call or something else blocks, or waiting for exection
    SUCCESS = 'SUCCESS', 'Success (Terminal)'
    FAILURE = 'FAILURE', 'Failure (Terminal)' # data parsing error

class Response(BaseModel):
    query          = models.OneToOneField("server.Query"     , null=True , on_delete=models.CASCADE, related_name="related_response")
    aimodel        = models.ForeignKey("server.AiModel"   , null=False, on_delete=models.CASCADE, related_name="related_responses")
    agent_instance_version = models.ForeignKey("server.InstanceVersionModel", on_delete=models.CASCADE, related_name="related_response")
    agent_profile  = models.ForeignKey("server.ProfileModel" , null=True,  on_delete=models.CASCADE, related_name='related_responses', default=None, blank=True)
    tool_calls     = models.ManyToManyField("server.AgentTaskCall",related_name='related_responses')

    status = EnumField(ResponseStatus, default=ResponseStatus.WAITING)

    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)

    message_content = models.ForeignKey(GenericContent,  default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="reponse_messages")
    message_reasoning = models.ForeignKey(GenericContent,  default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="reponse_reason")

    @property
    def conversation_messages(self):
        return self.related_conversation_messages # pyright: ignore[reportAttributeAccessIssue]

    def save(self, *args, **kwargs):
        usage_data = self.data.get("usage", {})
        self.completion_tokens = usage_data.get("completion_tokens", 0)
        self.prompt_tokens = usage_data.get("prompt_tokens", 0)
        super().save(*args, **kwargs)
        if self.status==ResponseStatus.SUCCESS and self.query:
            query = self.query
            estimated_total = query.tokens
            actual_total = self.prompt_tokens
            if estimated_total > 0 and actual_total > 0:
                correction_factor = actual_total / estimated_total
                if correction_factor > 1.01 or correction_factor < 0.99:
                    recalculated_total = 0
                    for query_message in query.query_messages.all():
                        recalculated_message_total = 0
                        for querymessage_part in query_message.query_message_parts.all():
                            corrected_tokens = int(round(querymessage_part.tokens * correction_factor))
                            if querymessage_part.tokens != corrected_tokens:
                                querymessage_part.tokens = corrected_tokens
                                querymessage_part.save()
                            recalculated_message_total += corrected_tokens
                        if query_message.tokens != recalculated_message_total:
                            query_message.tokens = recalculated_message_total
                            query_message.save()
                        recalculated_total += recalculated_message_total
                    if query.tokens != recalculated_total:
                        query.tokens = recalculated_total
                        query.save()

