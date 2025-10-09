from django.db import models
from django.db.models import Sum
from core.models.base_model import BaseModel

class AiModel(BaseModel):
    apiProvider = models.ForeignKey("providers.ApiProvider", on_delete=models.CASCADE, related_name='aimodels')
    name = models.CharField(max_length=512)
    enabled = models.BooleanField(default=True)
    max_tokens =  models.IntegerField(default=10000)
    free_limit_per_day =  models.IntegerField()

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
            'max_tokens': self.max_tokens,
            'free_limit_per_day': self.free_limit_per_day,
            'total_llm_queries': self.total_llm_queries,
            'total_prompt_tokens': self.total_prompt_tokens,
            'total_completion_tokens': self.total_completion_tokens,
            'apiProvider_id': self.apiProvider_id
        }
    def delete(self, *args, **kwargs):
        from django.contrib.auth.models import User
        from core.tasks.send_websocket_update import celery_send_websocket_update

        model_pk_to_broadcast = self.pk
        provider_pk_to_broadcast = self.apiProvider.pk

        super().delete(*args, **kwargs)

        message_data = {
            'object': 'AiModelDeleted',
            'model_pk': model_pk_to_broadcast,
            'provider_pk': provider_pk_to_broadcast
        }
        all_user_pks = User.objects.values_list('pk', flat=True)
        for pk in all_user_pks:
            celery_send_websocket_update.delay(message_data, user_pk=pk)
