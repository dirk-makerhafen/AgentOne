from __future__ import annotations

from typing import Any

from django.db import models
from django_enum import EnumField

from server.models.base_model import BaseModel, Observables


class ResponseStatus(models.TextChoices):
    """Status of an LLM response."""

    ACTIVE = "ACTIVE", "Active"
    WAITING = "WAITING", "Waiting (System Blocked)"
    SUCCESS = "SUCCESS", "Success (Terminal)"
    FAILURE = "FAILURE", "Failure (Terminal)"


class Response(BaseModel):
    """Stores the result of a single LLM query including token usage and timing."""
    class ResponseObservables(Observables):
        """Explicit observable keys for an Response (IDE autocomplete)."""

    query = models.ForeignKey("Query", null=True, on_delete=models.CASCADE, related_name="related_response")

    session = models.ForeignKey("server.SessionModel", on_delete=models.CASCADE, related_name="related_response")
    session_version = models.ForeignKey("server.SessionVersionModel", on_delete=models.CASCADE, related_name="related_response")

    status = EnumField(ResponseStatus, default=ResponseStatus.WAITING)

    aimodel = models.ForeignKey("server.AiModel", null=True, blank=True, on_delete=models.SET_NULL, related_name="related_responses")
    model_name = models.CharField(max_length=512, default="", blank=True)
    provider_name = models.CharField(max_length=512, default="", blank=True)

    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)
    cached_tokens = models.IntegerField(default=0)
    reasoning_tokens = models.IntegerField(default=0)

    time_to_first_token = models.FloatField(default=0)
    token_generation_time = models.FloatField(default=0)
    total_time = models.FloatField(default=0)
    reasoning_time = models.FloatField(default=0)

    tool_calls = models.JSONField(default=list, null=False, blank=True)
    content = models.TextField(default="", null=True, blank=True, max_length=500000)
    reasoning = models.TextField(default="", null=True, blank=True, max_length=500000)

    finish_reason = models.CharField( default="", null=True, blank=True, max_length=5000)


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
                if correction_factor > 1.02 or correction_factor < 0.98:
                    for query_message in query.related_query_messages.all():
                        if not query_message.tokens:
                            continue
                        corrected_tokens = int(round(query_message.tokens * correction_factor))
                        if query_message.tokens != corrected_tokens:
                            query_message.tokens = corrected_tokens
                            query_message.save(update_fields=["tokens"])

                        for part in query_message.query_message_parts.all():
                            if not part.tokens:
                                continue
                            corrected_tokens = int(round(part.tokens * correction_factor))
                            if part.tokens != corrected_tokens:
                                part.tokens = corrected_tokens
                                part.save(update_fields=["tokens"])
                                
                    # ``query.tokens`` is the authoritative backend count, not
                    # the (rounded) scaled estimate.
                    if query.tokens != actual_total:
                        query.tokens = actual_total
                        query.save(update_fields=["tokens"])
