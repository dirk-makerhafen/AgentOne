from __future__ import annotations

import json
import math
from typing import Any

from django.db import models
from django_enum import EnumField
from jinja2 import BaseLoader, Environment

from server.models.base_model import BaseModel
from server.models.content import GenericContent
from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
from server.models.message import Message, MessagePart
from server.models.queries.query_message_part import QueryMessagePart

_JINJA_ENV = Environment(loader=BaseLoader())

class QueryMessage(BaseModel):
    """A single message within a query, containing one or more parts."""

    query = models.ForeignKey(
        "server.Query", on_delete=models.CASCADE, related_name="related_query_messages"
    )
    source_message = models.ForeignKey(
        "server.Message",
        on_delete=models.SET_DEFAULT,
        related_name="related_query_messages",
        default=None,
        null=True,
    )

    role = EnumField(MessageRole, default=None)

    content_prefix = models.ForeignKey(
        GenericContent,
        default=None,
        null=True,
        blank=True,
        on_delete=models.SET_DEFAULT,
        related_name="query_messages_prefix",
    )
    content_postfix = models.ForeignKey(
        GenericContent,
        default=None,
        null=True,
        blank=True,
        on_delete=models.SET_DEFAULT,
        related_name="query_messages_postfix",
    )

    tags_token_usage = models.JSONField(default=dict, null=True, blank=True)
    tokens = models.IntegerField(default=None, blank=True, null=True)

    def add_part(
        self,
        content_type: MessageContentType | None = None,
        content: Any = None,
        template_data: Any = None,
        source_message_part: MessagePart | None = None,
    ) -> QueryMessagePart:
        """Add a part to this query message.

        Either provide ``source_message_part`` (copied) or provide
        ``content_type`` / ``content`` / ``template_data``.
        """
        if source_message_part:
            if content_type or content or template_data:
                raise Exception(
                    "Set either source_message_part or content_type,content,template_data"
                )
            return QueryMessagePart.objects.create(
                query_message=self, source_message_part=source_message_part
            )

        if not content_type or not content:
            raise Exception(
                "Set either content_type, content or source_message_part"
            )

        if content is not None and not isinstance(content, GenericContent):
            if content_type == MessageContentType.IMAGE:
                content = GenericContent.from_image(content)
            elif content_type in (MessageContentType.TEMPLATE, MessageContentType.TEXT):
                content = GenericContent.from_text(content)
            elif content_type == MessageContentType.JSON:
                content = GenericContent.from_data(content)
            else:
                raise Exception(f"unknown content type {content_type}")

        if template_data is not None and not isinstance(template_data, GenericContent):
            template_data = GenericContent.from_data(template_data)

        return QueryMessagePart.objects.create(
            query_message=self,
            content_type=MessageContentType[content_type.upper()],
            content=content,
            template_data=template_data,
            source_message_part=source_message_part,
        )

    def to_openai_message(
        self, fail_on_error: bool = True
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Convert this query message to the OpenAI message format."""
        tags_token_usage: dict[str, Any] = {}
        message_tool_calls: list[Any] = []
        message_parts: list[dict[str, Any]] = []

        for part in self.query_message_parts.all():
            if part.source_message_part:
                if part.source_message_part.type == MessagePartType.TOOLCALL:
                    message_tool_calls.append(part.source_message_part.tool_call)
                    continue
                if part.source_message_part.type != MessagePartType.MESSAGE:
                    raise Exception("here broken")

            part_contents = part.to_openai_message(fail_on_error=fail_on_error)
            message_parts.extend(part_contents)
            c = tags_token_usage
            for tag in part.tags:
                if tag not in c:
                    c[tag] = {"tokens": 0}
                c[tag]["tokens"] += part.tokens
                c = c[tag]

        if prefix := (self.content_prefix.get() if self.content_prefix else None):
            message_parts.insert(0, {"type": "text", "text": prefix})
        if postfix := (self.content_postfix.get() if self.content_postfix else None):
            message_parts.append({"type": "text", "text": postfix})

        merged_message_parts = [message_parts.pop(0)] if message_parts else []
        while message_parts:
            message_part = message_parts.pop(0)
            if merged_message_parts[-1]["type"] == message_part["type"] == "text":
                merged_message_parts[-1]["text"] += message_part["text"]
            else:
                merged_message_parts.append(message_part)

        content_to_send = merged_message_parts
        if len(content_to_send) == 1 and content_to_send[0]["type"] == "text":
            content_to_send = content_to_send[0]["text"]
            token_count = math.ceil(len(content_to_send) / 3.8)
        else:
            token_count = math.ceil(len(json.dumps(content_to_send)) / 3.8)

        if self.tokens != token_count:
            self.tags_token_usage = tags_token_usage
            self.tokens = token_count
            self.save()

        message: dict[str, Any] = {"role": self.role, "content": content_to_send}

        if not message_tool_calls:
            return message

        if self.role == "tool":
            messages: list[dict[str, Any]] = []
            for message_tool_call in message_tool_calls:
                tool_call_result = message_tool_call.get_result()
                tool_call_result_str = ""
                if isinstance(tool_call_result, Message):
                    tcr = []
                    for part in tool_call_result.parts.all():
                        part:MessagePart
                        if part.content_type == MessageContentType.TEXT:
                            tcr.append(part.content.get())

                        elif part.content_type == MessageContentType.TEMPLATE:
                            try:
                                rtemplate = _JINJA_ENV.from_string(part.content.get())
                                data: dict[str, Any] = {}
                                context = {**part.template_data.get(), **data}
                                tcr.append(rtemplate.render(**context))               
                            except Exception as e:
                                if fail_on_error:
                                    raise e
                        elif part.content_type == MessageContentType.JSON:     
                            tcr.append(json.dumps(part.content.get()))
                        else:
                            raise Exception(f"No message_content for content {part.content}")
                    tool_call_result_str = "".join(tcr)
                else:
                    tool_call_result_str = json.dumps(tool_call_result)

                messages.append({
                    "role": "tool",
                    "tool_call_id": f"tc-{message_tool_call.pk}",
                    "content": tool_call_result_str,
                })

            return messages if len(messages) > 1 else messages[0] if messages else []

        message["tool_calls"] = []
        for tool_call in message_tool_calls:
            message["tool_calls"].append(
                {
                    "id": f"tc-{tool_call.pk}",
                    "type": "function",
                    "function": {
                        "name": tool_call.task_definition.name,
                        "arguments": json.dumps(tool_call.carguments_json),
                    },
                }
            )

        return message

    def save(self, *args: Any, **kwargs: Any) -> None:
        super().save(*args, **kwargs)
