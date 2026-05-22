from __future__ import annotations

import json
import math
from typing import Any

from django.db import models
from django_enum import EnumField
from jinja2 import BaseLoader, Environment

from server.models.base_model import BaseModel
from server.models.content import GenericContent
from server.models.enums.message_enums import MessageContentType

_JINJA_ENV = Environment(loader=BaseLoader())


class QueryMessagePart(BaseModel):
    """A single content part within a query message."""

    query_message = models.ForeignKey(
        "server.QueryMessage",
        on_delete=models.CASCADE,
        related_name="query_message_parts",
    )
    source_message_part = models.ForeignKey(
        "server.MessagePart",
        default=None,
        null=True,
        on_delete=models.SET_DEFAULT,
        related_name="query_message_parts",
    )

    tokens = models.IntegerField(default=None, blank=True, null=True)

    content = models.ForeignKey(
        GenericContent,
        default=None,
        null=True,
        blank=True,
        on_delete=models.SET_DEFAULT,
        related_name="query_message_parts_content",
    )
    content_prefix = models.ForeignKey(
        GenericContent,
        default=None,
        null=True,
        blank=True,
        on_delete=models.SET_DEFAULT,
        related_name="query_message_parts_prefix",
    )
    content_postfix = models.ForeignKey(
        GenericContent,
        default=None,
        null=True,
        blank=True,
        on_delete=models.SET_DEFAULT,
        related_name="query_message_parts_postfix",
    )
    template_data = models.ForeignKey(
        GenericContent,
        default=None,
        null=True,
        blank=True,
        on_delete=models.SET_DEFAULT,
        related_name="query_message_parts_template_data",
    )
    content_type = EnumField(MessageContentType, default=MessageContentType.TEXT)

    tags = models.JSONField(
        default=list, null=True, blank=True, help_text="List of tags used"
    )

    def to_openai_message(self, fail_on_error: bool = True) -> list[dict[str, Any]]:
        """Convert this part to the OpenAI content-part format.

        Handles TEXT, TEMPLATE, IMAGE, and JSON content types.
        """
        if self.source_message_part:
            content_type = self.source_message_part.content_type
            content = self.source_message_part.content
            template_data = self.source_message_part.template_data
        else:
            content_type = self.content_type
            content = self.content
            template_data = self.template_data

        if not content:
            raise Exception("No content set")

        message_contents: list[dict[str, Any]] | None = None

        if content_type == MessageContentType.TEXT:
            message_contents = [{"type": "text", "text": content.get()}]

        elif content_type == MessageContentType.TEMPLATE:
            try:
                rtemplate = _JINJA_ENV.from_string(content.get())
                data: dict[str, Any] = {}
                context = {**template_data.get(), **data}
                message_contents = [
                    {"type": "text", "text": rtemplate.render(**context)}
                ]
            except Exception as e:
                if fail_on_error:
                    raise e
                message_contents = [
                    {
                        "type": "text",
                        "text": f"Error in Template String:{e}\n{content.get()}",
                    }
                ]

        elif content_type == MessageContentType.IMAGE:
            message_contents = [
                {"type": "image_url", "image_url": {"url": content.get()}}
            ]

        elif content_type == MessageContentType.JSON:
            message_contents = [
                {"type": "text", "text": json.dumps(content.get())}
            ]

        if message_contents is None:
            raise Exception(f"No message_content for content {content}")

        if prefix := (self.content_prefix.get() if self.content_prefix else None):
            message_contents.insert(0, {"type": "text", "text": prefix})
        if postfix := (self.content_postfix.get() if self.content_postfix else None):
            message_contents.append({"type": "text", "text": postfix})

        tokens = 0
        for message_content in message_contents:
            if msg := message_content.get("text", None):
                tokens += math.ceil(len(msg) / 3.8)
        if self.tokens != tokens:
            self.tokens = tokens
            self.save()

        return message_contents
