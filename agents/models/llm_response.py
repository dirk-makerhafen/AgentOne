from django.db import models
from core.models.base_model import BaseModel

class LLMResponse(BaseModel):
    class LLMResponseStatusChoices(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        ACTIVE = 'ACTIVE', 'Active'
        SUCCESS = 'SUCCESS', 'Successfull'
        FAILED = 'FAILED', 'Failed'

    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name="llmResponses")
    agentInstance = models.ForeignKey("agents.AgentInstance", on_delete=models.CASCADE, related_name="llmResponses")
    llmQuery = models.ForeignKey("agents.LLMQuery", on_delete=models.CASCADE, related_name="llmResponses")
    completion_tokens = models.IntegerField(default=0)
    prompt_tokens = models.IntegerField(default=0)
    status = models.CharField(max_length=255, choices=LLMResponseStatusChoices.choices, default=LLMResponseStatusChoices.PENDING)

    def save(self, send_to_client=True, *args, **kwargs):
        usage_data = self.data.get("usage", {})
        self.completion_tokens = usage_data.get("completion_tokens", 0)
        self.prompt_tokens = usage_data.get("prompt_tokens", 0)
        super().save(send_to_client=False, *args, **kwargs)
        if self.status==LLMResponse.LLMResponseStatusChoices.SUCCESS and self.llmQuery:
            query = self.llmQuery
            estimated_total = query.data.get("tokens", 0)
            actual_total = self.prompt_tokens
            if estimated_total > 0 and actual_total > 0:
                correction_factor = actual_total / estimated_total
                recalculated_total = 0
                for message in query.data.get("messages", []):
                    recalculated_message_total = 0
                    for part in message.get("parts", []):
                        estimated_part_tokens = part.get("tokens", 0)
                        corrected_tokens = round(estimated_part_tokens * correction_factor)
                        part["tokens"] = corrected_tokens
                        recalculated_message_total += corrected_tokens
                    message["tokens"] = recalculated_message_total
                    recalculated_total += recalculated_message_total
                query.data["tokens"] = recalculated_total
                query.save()
        if send_to_client:
            self.send_object_to_clients()

    def as_client_dict(self):
        usage_data = self.data.get("usage", {})
        total_tokens = usage_data.get("total_tokens", 0) if usage_data else 0
        return {
            "object": "LLMResponse",
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            'status_display': self.get_status_display(),
            "model_name": self.llmQuery.aimodel.name if self.llmQuery else "N/A",
            "total_tokens": total_tokens,
            "usage": usage_data,
            "raw_data": self.data,
            "agentInstance_id": self.agentInstance_id,
            "agentId": self.agent_id,
            "query_id": self.llmQuery_id,
        }
