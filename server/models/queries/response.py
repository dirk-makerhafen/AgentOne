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

    query = models.OneToOneField(
        "Query", null=True, on_delete=models.CASCADE, related_name="related_response"
    )
    session_version = models.ForeignKey(
        "server.SessionVersionModel",
        on_delete=models.CASCADE,
        related_name="related_response",
    )

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

    finish_reason = models.CharField(
        default="", null=True, blank=True, max_length=5000
    )

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save the response and optionally recalibrate query token estimates.

        On success, if there is a discrepancy between estimated and actual
        token counts, all related query messages are corrected proportionally.
        """
        super().save(*args, **kwargs)
        if self.status == ResponseStatus.SUCCESS and self.query:
            query = self.query
            estimated_total = query.tokens
            actual_total = self.prompt_tokens
            print("estimated_total", estimated_total)
            print("actual_total", actual_total)
            if estimated_total and actual_total and estimated_total > 0 and actual_total > 0:
                correction_factor = actual_total / estimated_total
                print("correction_factor", correction_factor)
                if correction_factor > 1.01 or correction_factor < 0.99:
                    recalculated_total = 0
                    for query_message in query.related_query_messages.all():
                        print("query_message", query_message)
                        recalculated_message_total = 0
                        for querymessage_part in query_message.query_message_parts.all():
                            print("querymessage_part", querymessage_part)
                            if not querymessage_part.tokens:
                                continue
                            corrected_tokens = int(
                                round(querymessage_part.tokens * correction_factor)
                            )
                            if querymessage_part.tokens != corrected_tokens:
                                querymessage_part.tokens = corrected_tokens
                                querymessage_part.save()
                                print("querymessage_part.save", querymessage_part)
                            recalculated_message_total += corrected_tokens
                        if query_message.tokens != recalculated_message_total:
                            query_message.tokens = recalculated_message_total
                            query_message.save()
                        recalculated_total += recalculated_message_total
                    if query.tokens != recalculated_total:
                        query.tokens = recalculated_total
                        query.save()
