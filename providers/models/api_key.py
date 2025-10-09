from django.db import models
from django.db.models import Sum
from agents.models.llm_response import LLMResponse
from core.models.base_model import BaseModel

class ApiKey(BaseModel):
    apiProvider = models.ForeignKey("providers.ApiProvider", on_delete=models.CASCADE, related_name='apikeys')
    key = models.CharField(max_length=512)
    comment = models.CharField(max_length=512)

    @property
    def total_llm_queries(self):
        return self.llmqueries.count()

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
    def delete(self, *args, **kwargs):
        from django.contrib.auth.models import User
        from core.tasks.send_websocket_update import celery_send_websocket_update

        key_pk_to_broadcast = self.pk
        provider_pk_to_broadcast = self.apiProvider.pk

        super().delete(*args, **kwargs)

        message_data = {
            'object': 'ApiKeyDeleted',
            'key_pk': key_pk_to_broadcast,
            'provider_pk': provider_pk_to_broadcast
        }
        all_user_pks = User.objects.values_list('pk', flat=True)
        for pk in all_user_pks:
            celery_send_websocket_update.delay(message_data, user_pk=pk)
