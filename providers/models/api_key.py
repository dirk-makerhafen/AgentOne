from django.db import models
from django.db.models import Sum
from agents.models.llm_response import LLMResponse
from core.models.base_model import BaseModel

class ApiKey(BaseModel):
    apiProvider = models.ForeignKey("providers.ApiProvider", on_delete=models.CASCADE, related_name='apikeys')
    comment = models.CharField(max_length=512, default="", null=True)
    key = models.CharField(max_length=512)

    @property
    def total_llm_queries(self):
        return self.llmQueries.count()

    @property
    def total_prompt_tokens(self):
        return LLMResponse.objects.filter(llmQuery__apikey=self).aggregate(total=Sum('prompt_tokens'))['total'] or 0

    @property
    def total_completion_tokens(self):
        return LLMResponse.objects.filter(llmQuery__apikey=self).aggregate(total=Sum('completion_tokens'))['total'] or 0

    def as_client_dict(self):
        return {
            'object': 'ApiKey', 
            'id': self.pk, 
            'key': '***',
            'comment': self.comment,
            'total_llm_queries': self.total_llm_queries,
            'total_prompt_tokens': self.total_prompt_tokens,
            'total_completion_tokens': self.total_completion_tokens,
            'apiProvider_id': self.apiProvider_id
        }
    def get_delete_broadcast_payload(self):
        return {
            'object': 'ApiKeyDeleted',
            'key_pk': self.pk,
            'provider_pk': self.apiProvider.pk
        }
