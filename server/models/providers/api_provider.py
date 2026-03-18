
from django.db import models
from django.db.models import Sum

from server.models.queries.query import Query
from server.models.queries.response import Response
from server.models.base_model import BaseModel

class ApiProvider(BaseModel):
    name = models.CharField(max_length=512)
    url = models.CharField(max_length=512,default="")

    @property
    def total_llm_queries(self):
        return Query.objects.filter(aimodel__api_provider=self).count()

    @property
    def total_prompt_tokens(self):
        return Response.objects.filter(query__aimodel__api_provider=self).aggregate(total=Sum('prompt_tokens'))['total'] or 0

    @property
    def total_completion_tokens(self):
        return Response.objects.filter(query__aimodel__api_provider=self).aggregate(total=Sum('completion_tokens'))['total'] or 0

    def __str__(self):
        return "ApiProvider:" + self.name
