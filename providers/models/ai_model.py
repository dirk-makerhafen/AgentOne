from django.db import models
from django.db.models import Sum
from core.models.base_model import BaseModel

class AiModel(BaseModel):
    apiProvider = models.ForeignKey("providers.ApiProvider", on_delete=models.CASCADE, related_name='models')
    name = models.CharField(max_length=512)
    enabled = models.BooleanField(default=True)
    max_tokens =  models.IntegerField(default=10000)
    free_limit_per_day =  models.IntegerField()

    @property
    def total_llm_queries(self):
        return self.llmqueries.count()

    @property
    def total_prompt_tokens(self):
        return self.llmqueries.aggregate(total=Sum('llmResponses__prompt_tokens'))['total'] or 0

    @property
    def total_completion_tokens(self):
        return self.llmqueries.aggregate(total=Sum('llmResponses__completion_tokens'))['total'] or 0

    def __str__(self):
        return "Model:" + self.name
    
    def as_client_dict(self):
        return {
            'object': 'Model', 
            'id': self.pk, 
            'name': self.name,
            'enabled': self.enabled,
            'max_tokens': self.max_tokens,
            'free_limit_per_day': self.free_limit_per_day,
            'total_llm_queries': self.total_llm_queries,
            'total_prompt_tokens': self.total_prompt_tokens,
            'total_completion_tokens': self.total_completion_tokens,
        }
