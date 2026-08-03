from __future__ import annotations

from typing import Any

from django.db import models
from django_enum import EnumField

from server.models.base_model import BaseModel


class ResponseStatus(models.TextChoices):
    """Status of an LLM response."""

    ACTIVE = "ACTIVE", "Active"
    WAITING = "WAITING", "Waiting (System Blocked)"
    SUCCESS = "SUCCESS", "Success (Terminal)"
    FAILURE = "FAILURE", "Failure (Terminal)"


class Response(BaseModel):
    """Stores the result of a single LLM query including token usage and timing."""

    query = models.ForeignKey("Query", null=True, on_delete=models.CASCADE, related_name="related_response")
    session_version = models.ForeignKey("server.SessionVersionModel", on_delete=models.CASCADE, related_name="related_response")

    status = EnumField(ResponseStatus, default=ResponseStatus.WAITING)

    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)

    time_to_first_token = models.FloatField(default=0)
    token_generation_time = models.FloatField(default=0)
    total_time = models.FloatField(default=0)
    reasoning_time = models.FloatField(default=0)

    tool_calls = models.JSONField(default=list, null=False, blank=True)
    content = models.TextField(default="", null=True, blank=True, max_length=500000)
    reasoning = models.TextField(default="", null=True, blank=True, max_length=500000)

    finish_reason = models.CharField( default="", null=True, blank=True, max_length=5000)

    observable_fields = set([
        "pk",
        "query",
        "session_version",
    ])
    @property
    def observable_keys(self):
        return set([
            "Response",
            f"Response.pk:{self.pk}",
            f"Response.query:{self.query_pk}",      
            f"Response.session_version:{self.session_version_pk}",               
        ])

    def notify_observers(self):
        keys = self.observable_keys
        #observers = redis_get keys
        #set(observers)
        #for each observer:
        # redis add observer self

    def register_observer(self, observer, field = None, value=None):
        redis_key = "Response"
        if field:
            if field not in self.observable_fields:
                raise Exception(f"Failed, field {field} is not observable for model 'Response'")
            redis_key += f".{field}"
        if value:
            redis_key += f":{value}"
        #redis add redis_key observer

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save the response and optionally recalibrate query token estimates.

        On success, if there is a discrepancy between estimated and actual
        token counts, the query message token estimates are corrected
        proportionally and ``query.tokens`` is set to the authoritative
        backend-reported ``prompt_tokens``.
        """
        super().save(*args, **kwargs)
        if self.status == ResponseStatus.SUCCESS and self.query:
            query = self.query
            estimated_total = query.tokens
            actual_total = self.prompt_tokens
            if estimated_total and actual_total and estimated_total > 0 and actual_total > 0:
                correction_factor = actual_total / estimated_total
                if correction_factor > 1.01 or correction_factor < 0.99:
                    # Scale at the *message* level, NOT the part level.  Tool
                    # result tokens are rendered dynamically at the message
                    # level (``_serialize_result(tc.get_result())``) and never
                    # exist as part tokens, so a part-based recalculation
                    # silently dropped them and collapsed ``query.tokens``.
                    recalculated_total = 0
                    for query_message in query.related_query_messages.all():
                        if not query_message.tokens:
                            continue
                        corrected_tokens = int(
                            round(query_message.tokens * correction_factor)
                        )
                        if query_message.tokens != corrected_tokens:
                            query_message.tokens = corrected_tokens
                            query_message.save(update_fields=["tokens"])
                        recalculated_total += corrected_tokens
                    # ``query.tokens`` is the authoritative backend count, not
                    # the (rounded) scaled estimate.
                    if query.tokens != actual_total:
                        query.tokens = actual_total
                        query.save(update_fields=["tokens"])
