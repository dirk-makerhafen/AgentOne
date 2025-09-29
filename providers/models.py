
from common.models import ModelWithJsonData
from django.db import models
from django.db.models import Sum
from agent.models.llm import LLMQuery, LLMResponse # Import necessary LLM models

class ApiProvider(ModelWithJsonData):
    name = models.CharField(max_length=512)
    url = models.CharField(max_length=512,default="")

    @property
    def total_llm_queries(self):
        return LLMQuery.objects.filter(model__apiProvider=self).count()

    @property
    def total_prompt_tokens(self):
        return LLMResponse.objects.filter(llmQuery__model__apiProvider=self).aggregate(total=Sum('prompt_tokens'))['total'] or 0

    @property
    def total_completion_tokens(self):
        return LLMResponse.objects.filter(llmQuery__model__apiProvider=self).aggregate(total=Sum('completion_tokens'))['total'] or 0

    def __str__(self):
        return "ApiProvider:" + self.name
    
    def save(self, send_to_client=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if send_to_client:
            from dashboard.tasks import send_object_to_clients
            send_object_to_clients(self)

    def as_client_dict(self):
        return {
            'object': 'ApiProvider', 
            'id': self.pk, 
            'name': self.name,
            'url': self.url,
            'models': [model.as_client_dict() for model in self.models.all()],
            'apikeys': [key.as_client_dict() for key in self.apikeys.all()],
            'total_llm_queries': self.total_llm_queries,
            'total_prompt_tokens': self.total_prompt_tokens,
            'total_completion_tokens': self.total_completion_tokens,
        }
    
class Model(ModelWithJsonData):
    apiProvider = models.ForeignKey(ApiProvider, on_delete=models.CASCADE, related_name='models')
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
    
    
    def save(self, send_to_client=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if send_to_client:
            from dashboard.tasks import send_object_to_clients
            send_object_to_clients(self)

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
    
class ApiKey(ModelWithJsonData):
    apiProvider = models.ForeignKey(ApiProvider, on_delete=models.CASCADE, related_name='apikeys')
    key = models.CharField(max_length=512)
    comment = models.CharField(max_length=512)

    @property
    def total_llm_queries(self):
        return LLMQuery.objects.filter(apikey=self).count()

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
            'key': '***', # Never expose the raw API key
            'comment': self.comment,
            'total_llm_queries': self.total_llm_queries,
            'total_prompt_tokens': self.total_prompt_tokens,
            'total_completion_tokens': self.total_completion_tokens,
        }

    def save(self, send_to_client=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if send_to_client:
            from dashboard.tasks import send_object_to_clients
            send_object_to_clients(self)
