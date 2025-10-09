
from django.db import models
from django.db.models import Sum

from agents.models.llm_query import LLMQuery
from agents.models.llm_response import LLMResponse
from core.models.base_model import BaseModel

class ApiProvider(BaseModel):
    name = models.CharField(max_length=512)
    url = models.CharField(max_length=512,default="")

    @property
    def total_llm_queries(self):
        return LLMQuery.objects.filter(aimodel__apiProvider=self).count()

    @property
    def total_prompt_tokens(self):
        return LLMResponse.objects.filter(llmQuery__aimodel__apiProvider=self).aggregate(total=Sum('prompt_tokens'))['total'] or 0

    @property
    def total_completion_tokens(self):
        return LLMResponse.objects.filter(llmQuery__aimodel__apiProvider=self).aggregate(total=Sum('completion_tokens'))['total'] or 0

    def __str__(self):
        return "ApiProvider:" + self.name
    
    def save(self, send_to_client=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if send_to_client:
            self.send_object_to_clients()

    def as_client_dict(self):
        return {
            'object': 'ApiProvider', 
            'id': self.pk, 
            'name': self.name,
            'url': self.url,
            'models': [model.as_client_dict() for model in self.aimodels.all()],
            'apikeys': [key.as_client_dict() for key in self.apikeys.all()],
            'total_llm_queries': self.total_llm_queries,
            'total_prompt_tokens': self.total_prompt_tokens,
            'total_completion_tokens': self.total_completion_tokens,
        }
    