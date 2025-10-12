from django.db import models
from django.db.models import Sum
from core.models.base_model import BaseModel

class AiModel(BaseModel):
    apiProvider = models.ForeignKey("providers.ApiProvider", on_delete=models.CASCADE, related_name='aimodels')
    name = models.CharField(max_length=512)
    enabled = models.BooleanField(default=True)
    max_prompt_tokens =  models.IntegerField(default=1000000)
    max_response_tokens = models.IntegerField(default=1000000)
    limit_request_per_day =  models.IntegerField(default=0)
    limit_request_per_minute =  models.IntegerField(default=0)
    limit_tokens_per_day =  models.IntegerField(default=0)
    limit_tokens_per_minute =  models.IntegerField(default=0)
    

    @property
    def total_llm_queries(self):
        return self.llmQueries.count()

    @property
    def total_prompt_tokens(self):
        return self.llmQueries.aggregate(total=Sum('llmResponses__prompt_tokens'))['total'] or 0

    @property
    def total_completion_tokens(self):
        return self.llmQueries.aggregate(total=Sum('llmResponses__completion_tokens'))['total'] or 0

    def __str__(self):
        return "Model:" + self.name
    
    def as_client_dict(self):
        return {
            'object': 'AiModel', 
            'id': self.pk, 
            'name': self.name,
            'enabled': self.enabled,
            'max_prompt_tokens': self.max_prompt_tokens,
            'limit_request_per_day': self.limit_request_per_day,
            'limit_request_per_minute': self.limit_request_per_minute,
            'limit_tokens_per_day': self.limit_tokens_per_day,
            'limit_tokens_per_minute': self.limit_tokens_per_minute,
            'total_llm_queries': self.total_llm_queries,
            'total_prompt_tokens': self.total_prompt_tokens,
            'total_completion_tokens': self.total_completion_tokens,
            'apiProvider_id': self.apiProvider_id
        }
    def get_delete_broadcast_payload(self):
        return {
            'object': 'AiModelDeleted',
            'model_pk': self.pk,
            'provider_pk': self.apiProvider.pk
        }
