from django.db import models
from django.db.models import Sum
from server.models.queries.response import Response
from server.models.base_model import BaseModel

class ApiKey(BaseModel):
    api_provider = models.ForeignKey("server.ApiProvider", on_delete=models.CASCADE, related_name='api_keys')
    comment = models.CharField(max_length=512, default="", null=True)
    key = models.CharField(max_length=512)

    @property
    def total_llm_queries(self):
        return self.queries.count() # type: ignore  # reverse lookup

    @property
    def total_prompt_tokens(self):
        return Response.objects.filter(query__apikey=self).aggregate(total=Sum('prompt_tokens'))['total'] or 0

    @property
    def total_completion_tokens(self):
        return Response.objects.filter(query__apikey=self).aggregate(total=Sum('completion_tokens'))['total'] or 0

    @property
    def queries(self):
        return self.related_queries # pyright: ignore[reportAttributeAccessIssue]
