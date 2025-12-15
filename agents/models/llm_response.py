from django.db import models
from core.models.base_model import BaseModel

class LLMResponse(BaseModel):
    class LLMResponseStatusChoices(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        ACTIVE  = 'ACTIVE', 'Active'
        SUCCESS = 'SUCCESS', 'Successfull'
        FAILED  = 'FAILED', 'Failed'

    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name="llmResponses")
    agentInstance = models.ForeignKey("agents.AgentInstance", on_delete=models.CASCADE, related_name="llmResponses")
    llmQuery = models.ForeignKey("agents.LLMQuery", on_delete=models.SET_DEFAULT, default=None, null=True, related_name="llmResponses")
    completion_tokens = models.IntegerField(default=0)
    prompt_tokens = models.IntegerField(default=0)
    status = models.CharField(max_length=255, choices=LLMResponseStatusChoices.choices, default=LLMResponseStatusChoices.PENDING)

    def save(self, send_to_client=True, *args, **kwargs):
        usage_data = self.data.get("usage", {})
        self.completion_tokens = usage_data.get("completion_tokens", 0)
        self.prompt_tokens = usage_data.get("prompt_tokens", 0)
        super().save(send_to_client=False, *args, **kwargs)
        if self.status==LLMResponse.LLMResponseStatusChoices.SUCCESS and self.llmQuery:
            llmQuery = self.llmQuery
            estimated_total = llmQuery.tokens
            actual_total = self.prompt_tokens
            if estimated_total > 0 and actual_total > 0:
                correction_factor = actual_total / estimated_total
                if correction_factor > 1.01 or correction_factor < 0.99:
                    recalculated_total = 0
                    for queryMessage in llmQuery.queryMessages.all():
                        recalculated_message_total = 0
                        for queryMessagePart in queryMessage.queryMessageParts.all():
                            corrected_tokens = int(round(queryMessagePart.tokens * correction_factor))
                            if queryMessagePart.tokens != corrected_tokens:
                                queryMessagePart.tokens = corrected_tokens
                                queryMessagePart.save(send_to_client=False)
                            recalculated_message_total += corrected_tokens
                        if queryMessage.tokens != recalculated_message_total:
                            queryMessage.tokens = recalculated_message_total
                            queryMessage.save(send_to_client=False)
                        recalculated_total += recalculated_message_total
                    if llmQuery.tokens != recalculated_total:
                        llmQuery.tokens = recalculated_total
                        llmQuery.save()
        if send_to_client:
            self.send_object_to_clients()

    def as_client_dict(self):
        return {
            "object": "LLMResponse",
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            'status_display': self.get_status_display(),
            "model_name": self.llmQuery.aimodel.name if self.llmQuery else "N/A",
            "completion_tokens": self.completion_tokens,
            "prompt_tokens": self.prompt_tokens,
            "usage": self.data.get("usage", {}),
            "raw_data": self.data,
            "agentInstance_id": self.agentInstance_id,
            "agentId": self.agent_id,
            "query_id": self.llmQuery_id,
        }
