from __future__ import annotations

from typing import Any

from cachetools import LRUCache
from django.db import models
from django_enum import EnumField
from sortedm2m.fields import SortedManyToManyField

from server.models.base_model import BaseModel, Observables
from server.models.enums.message_enums import MessageContentType, MessagePartType
from server.models.message import Message
from server.models.queries.query_message import QueryMessage


cache = LRUCache(maxsize=10000)

class QueryStatus(models.TextChoices):
    """Status of an LLM query."""

    ACTIVE = "ACTIVE", "Active"
    WAITING = "WAITING", "Waiting (System Blocked)"
    SUCCESS = "SUCCESS", "Success (Terminal)"
    FAILURE = "FAILURE", "Failure (Terminal)"


class Query(BaseModel):
    """Represents a single LLM query including its message history."""

    apikey = models.ForeignKey(  "server.ApiKey",  null=True,  on_delete=models.SET_NULL,  related_name="related_queries",  blank=True)
    session = models.ForeignKey(  "server.SessionModel",  null=False,  on_delete=models.CASCADE,  related_name="related_queries")
    session_version = models.ForeignKey(  "server.SessionVersionModel",  null=False,  on_delete=models.CASCADE,  related_name="related_queries")
    trigger_message = models.ForeignKey(  "server.Message",  null=True,  blank=True,  on_delete=models.CASCADE,  related_name="related_queries")
    status = EnumField(QueryStatus, default=QueryStatus.WAITING)
    tokens = models.IntegerField(default=None, blank=True, null=True)


    class QueryObservables(Observables):
        """Explicit observable keys for an Query (IDE autocomplete)."""

        @property
        def messages(self):
            return f"QueryMessage.query:{self.model.pk}"

    @property
    def response(self):
        """Return the related Response for this query."""
        return self.related_response  # pyright: ignore[reportAttributeAccessIssue]

    def add_message(  self,  role: str,  content_type: MessageContentType | None = None,  content: Any = None,  template_data: Any = None,  source_message: Message | None = None) -> QueryMessage:
        """Add a message to this query.

        Either provide ``source_message`` (copies its parts) or provide
        ``content_type`` / ``content`` / ``template_data`` directly.
        """
        if source_message:
            if content_type or content or template_data:
                raise Exception(
                    "Set either source_message or content_type,content,template_data"
                )
            query_message = QueryMessage.objects.create(role=role, query=self, source_message=source_message)
            for part in source_message.parts.all():
                if part.type not in [MessagePartType.MESSAGE, MessagePartType.TOOLCALL]:
                    continue
                _ = query_message.add_part(source_message_part=part)
            return query_message

        if not content_type or content is None:
            raise Exception(
                "Set either content_type, content or source_message_part"
            )

        query_message = QueryMessage.objects.create(role=role, query=self)
        _ = query_message.add_part(
            content_type=content_type, content=content, template_data=template_data
        )
        return query_message

    def to_openai_message(self) -> list[dict[str, Any]]:
        """Convert all query messages to the OpenAI message format."""
        messages: list[dict[str, Any]] = []
        tokens = 0
        related_query_messages = getattr(self, "related_query_messages", None)
        if not related_query_messages:
            return []

        aimodel = self.session_version.get_runtime().aimodel
        requires_reasoning_echo = aimodel and aimodel.requires_reasoning_echo
        cache_key = f"{self.pk}{requires_reasoning_echo}"
        if item := cache.get(cache_key):
            return item
       

        for message in related_query_messages.all():
            message: QueryMessage
            try:
                qm = message.to_openai_message(requires_reasoning_echo)
                if qm is None:
                    continue
                if isinstance(qm, list):
                    for m in qm:
                        messages.append(m)
                else:
                    messages.append(qm)
                tokens += message.tokens if message.tokens else 0
            except Exception as e:
                print("Failed to_openai_message", message)
                raise e
        if self.tokens != tokens:
            self.tokens = tokens
            self.save()
        cache[cache_key] = messages
        return messages

    def save(self, *args: Any, **kwargs: Any) -> None:
        super().save(*args, **kwargs)
