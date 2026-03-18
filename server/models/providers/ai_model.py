from django.db import models
from django.db.models import Sum
from server.models.base_model import BaseModel


class AiModel(BaseModel):
    api_provider = models.ForeignKey("server.ApiProvider", on_delete=models.CASCADE, related_name='aimodels')
    name = models.CharField(max_length=512)
    family = models.CharField(max_length=512, default="", blank=True)
    description = models.TextField(max_length=65000, default="", blank=True)

    enabled = models.BooleanField(default=True)

    context_length = models.IntegerField(default=1000000)
    is_cloud = models.BooleanField(default=True)
    filesize = models.IntegerField(default=-1)
    vision = models.BooleanField(default=False)
    billion_parameters = models.FloatField(default=0)

    max_prompt_tokens = models.IntegerField(default=1000000)
    max_response_tokens = models.IntegerField(default=1000000)
    limit_request_per_day = models.IntegerField(default=0)
    limit_request_per_minute = models.IntegerField(default=0)
    limit_tokens_per_day = models.IntegerField(default=0)
    limit_tokens_per_minute = models.IntegerField(default=0)
    
    @property
    def total_llm_queries(self):
        return self.queries.count()  # type: ignore  # reverse lookup

    @property
    def total_prompt_tokens(self):
        return self.queries.aggregate(total=Sum('related_response__prompt_tokens'))['total'] or 0  # type: ignore  # reverse lookup

    @property
    def total_completion_tokens(self):
        return self.queries.aggregate(total=Sum('related_response__completion_tokens'))['total'] or 0   # type: ignore  # reverse lookup

    @property
    def queries(self):
        return self.related_queries # pyright: ignore[reportAttributeAccessIssue]

    @property
    def responses(self):
        return self.related_responses # pyright: ignore[reportAttributeAccessIssue]

    def __str__(self):
        return "Model:" + self.name
    