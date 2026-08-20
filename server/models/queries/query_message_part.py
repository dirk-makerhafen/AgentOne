from __future__ import annotations

import json
import math
from typing import Any

from cachetools import LRUCache
from django.db import models
from django_enum import EnumField
from jinja2 import BaseLoader, Environment

from server.models.base_model import BaseModel, Observables
from server.models.content import GenericContent
from server.models.enums.message_enums import MessageContentType, MessagePartType

_JINJA_ENV = Environment(loader=BaseLoader())
cache = LRUCache(maxsize=100000)


class QueryMessagePart(BaseModel):
    """A single content part within a query message."""

    class QueryMessagePartObservables(Observables):
        """Explicit observable keys for a QueryMessagePart (IDE autocomplete)."""
        pass
    
    query_message = models.ForeignKey("server.QueryMessage", on_delete=models.CASCADE, related_name="query_message_parts")
    source_message_part = models.ForeignKey( "server.MessagePart", default=None, null=True, on_delete=models.SET_DEFAULT, related_name="query_message_parts")

    tokens = models.IntegerField(default=None, blank=True, null=True)

    content = models.ForeignKey( GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="query_message_parts_content")
    template_data = models.ForeignKey( GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="query_message_parts_template_data")
    content_type = EnumField(MessageContentType, default=MessageContentType.TEXT)

    @property
    def has_toolcalls(self):
        if self.source_message_part and self.source_message_part.tool_call:
            return True
        return False

    def to_openai_message(self, fail_on_error: bool = True) -> list[dict[str, Any]]:
        """Convert this part to the OpenAI content-part format.

        Handles TEXT, TEMPLATE, IMAGE, and JSON content types.
        """
        cache_key = f"qmp{self.pk}"
        if item := cache.get(cache_key):
            return item
        
        if self.source_message_part:
            content = self.source_message_part.content
            template_data = self.source_message_part.template_data
            content_type = self.source_message_part.content_type
            part_type = self.source_message_part.type
        else:
            content = self.content
            template_data = self.template_data
            content_type = self.content_type
            part_type = None

        if not content:
            raise ValueError("No content set")

        message_contents = self._build_message_contents(content, content_type, template_data, part_type, fail_on_error)

        if not self.tokens:
            tokens = int(len(json.dumps(message_contents)) / 3.8)
            if self.tokens != tokens:
                self.tokens = tokens
                self.save(update_fields=["tokens"])
        cache[cache_key] = message_contents
        return message_contents

    def _build_message_contents(
        self,
        content: GenericContent,
        content_type: MessageContentType,
        template_data: GenericContent | None,
        part_type: MessagePartType | None,
        fail_on_error: bool,
    ) -> list[dict[str, Any]]:
        """Route content rendering by type."""
        if part_type == MessagePartType.REASONING and self.source_message_part and self.source_message_part.content:
            return [{"type": "reasoning", "text": self.source_message_part.content.get()}]

        if self.source_message_part and part_type == MessagePartType.TOOLCALL:
            tc = self.source_message_part.tool_call
            if tc:
                return [{
                    "id": f"tc-{tc.pk}",
                    "type": "function",
                    "function": {
                        "name": tc.task_definition.name,
                        "arguments": json.dumps(tc.carguments_json),
                    },
                }]

        if content_type == MessageContentType.TEXT:
            return [{"type": "text", "text": content.get()}]

        if content_type == MessageContentType.TEMPLATE:
            try:
                context = template_data.get() if template_data else {}
                text = _JINJA_ENV.from_string(content.get()).render(**context)
                return [{"type": "text", "text": text}]
            except Exception as e:
                if fail_on_error:
                    raise
                return [{"type": "text", "text": f"Error in Template String:{e}\n{content.get()}"}]

        if content_type == MessageContentType.IMAGE:
            return [{"type": "image_url", "image_url": {"url": content.get()}}]

        if content_type == MessageContentType.JSON:
            return [{"type": "text", "text": json.dumps(content.get())}]

        raise ValueError(f"Unknown content type: {content_type}")
