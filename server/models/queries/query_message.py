from __future__ import annotations

import json
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cachetools import LRUCache
from django.db import models
from django_enum import EnumField
from jinja2 import BaseLoader, Environment

from server.models.base_model import BaseModel, Observables
from server.models.content import GenericContent
from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
from server.models.message import Message, MessagePart
from server.models.queries.query_message_part import QueryMessagePart
if TYPE_CHECKING:
    from server.models.tasks.agent_task_call import AgentTaskCall

cache = LRUCache(maxsize=50000)


class QueryMessage(BaseModel):
    """A single message within a query, containing one or more parts."""
    class QueryMessageObservables(Observables):
        """Explicit observable keys for an QueryMessage (IDE autocomplete)."""
        @property
        def parts(self):
            return f"QueryMessagePart.query_message:{self.model.pk}"

    query = models.ForeignKey("server.Query", on_delete=models.CASCADE, related_name="related_query_messages")
    source_message = models.ForeignKey("server.Message",on_delete=models.SET_DEFAULT,related_name="related_query_messages",default=None,null=True)
    role = EnumField(MessageRole, default=None)
    tokens = models.IntegerField(default=None, blank=True, null=True)

    @property
    def has_toolcalls(self):
        for part in self.query_message_parts.all():
            if part.has_toolcalls:
                return True
        return False

    def add_part(self, content_type: MessageContentType | None = None, content: Any = None, template_data: Any = None, source_message_part: MessagePart | None = None,) -> QueryMessagePart:
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

    def to_openai_message(self, requires_reasoning_echo: bool = False, fail_on_error: bool = True) -> dict[str, Any] | list[dict[str, Any]]:
        """Convert this query message to the OpenAI message format."""
        cache_key = f"{self.pk}{requires_reasoning_echo}"
        if item := cache.get(cache_key):
            return item
       

        content_parts: list[dict[str, Any]] = []
        reasoning_parts: list[str] = []
        tool_call_dicts: list[dict[str, Any]] = []
        tool_call_objects: list[AgentTaskCall] = []
        has_user_toolcall = False

        for part in self.query_message_parts.all():
            part_contents = part.to_openai_message(fail_on_error=fail_on_error)
            if part.source_message_part and part.source_message_part.type == MessagePartType.TOOLCALL:
                if part.source_message_part.tool_call:
                    tool_call_dicts.extend(part_contents)
                    tool_call_objects.append(part.source_message_part.tool_call)
                else:
                    has_user_toolcall = True
                    content_parts.extend(part_contents)
            elif part.source_message_part and part.source_message_part.type == MessagePartType.REASONING:
                if requires_reasoning_echo and part.source_message_part.content: 
                    reasoning_parts.extend( [pc.get("text","") for pc in part_contents if pc.get("type","") == "reasoning"])
            else:
                content_parts.extend(part_contents)

        if self.role == "tool" and tool_call_objects:
            for tc in tool_call_objects:
                tool_response_string = self._serialize_result(tc.get_result())
                l = len(tool_response_string)
                if l > 30000*4:  # more than ~30k tokens
                    removed_chars = l - 24000*4
                    s = tool_response_string[:12000*4]
                    m = f"\n<RESPONSE SHORTEND BY TOOL RESPONSE BACKEND>{removed_chars} chars omited here to save context tokens.</RESPONSE SHORTEND BY TOOL RESPONSE BACKEND>\n"
                    e = tool_response_string[-12000*4:]
                    e1 = f"\n\n{removed_chars} of {l} characters ommited from response to save context tokens"
                    tool_response_string = f"{s}{m}{e}{e1}" 
                messages = [
                    {
                        "role": "tool",
                        "tool_call_id": f"tc-{tc.pk}",
                        "content": tool_response_string,
                    }
                ]           
                message = messages[0] if len(messages) == 1 else messages

        elif self.role == "tool":
            merged = self._merge_text_parts(content_parts)
            if isinstance(merged, str):
                merged = f"USER TOOLCALL RESPONSE: {merged}"
            else:
                merged.insert(0, {"type": "text", "text": "USER TOOLCALL RESPONSE: "})
            message: dict[str, Any] = {"role": MessageRole.ASSISTANT, "content": merged}

        else:
            
            merged = self._merge_text_parts(content_parts)
            message: dict[str, Any] = {"role": self.role, "content": merged}
            if has_user_toolcall:
                if isinstance(merged, str):
                    message["content"] = f"USER TOOLCALL: {merged}"
                elif isinstance(merged, list):
                    message["content"] = [{"type": "text", "text": "USER TOOLCALL: "}] + merged
            if tool_call_dicts:
                message["tool_calls"] = tool_call_dicts
        # DeepSeek requires reasoning_content to be echoed back in subsequent
        # assistant messages when thinking mode is active.
        # Only include when the model requires this (requires_reasoning_echo
        # in provider YAML manifests).
        if self.role == MessageRole.ASSISTANT and requires_reasoning_echo and reasoning_parts:
            message["reasoning_content"] = "".join(reasoning_parts)

        if not self.tokens:
            """Rough token estimate token counts"""
            token_count =  math.ceil(len(json.dumps(message)) / 3.8)
            if self.tokens != token_count:
                self.tokens = token_count
                self.save(update_fields=["tokens"])

        cache[cache_key] = message
        return message

    def _merge_text_parts(self, parts: list[dict[str, Any]]) -> str | list[dict[str, Any]]:
        """Merge adjacent text parts, prepend prefix, append postfix."""

        if not parts:
            return ""

        merged = [parts[0]]
        for part in parts[1:]:
            if merged[-1]["type"] == part["type"] == "text":
                merged[-1]["text"] += part["text"]
            else:
                merged.append(part)

        if len(merged) == 1 and merged[0]["type"] == "text":
            return merged[0]["text"]
        return merged

    def _serialize_result(self, data: Any) -> str:
        """JSON-serialise a tool result, handling Message / Path model references."""
        def _walk(obj: Any) -> Any:
            if obj is None or isinstance(obj, (str, int, float, bool)):
                return obj
            if isinstance(obj, dict):
                return {k: _walk(v) for k, v in obj.items()}
            if isinstance(obj, (list, set, tuple)):
                return type(obj)(_walk(item) for item in obj)
            if isinstance(obj, Message):
                return "".join(
                    part.to_string()
                    for part in obj.parts.filter(type=MessagePartType.MESSAGE)
                )
            if isinstance(obj, Path):
                return obj.as_posix()
            raise TypeError(f"Cannot serialize {type(obj).__name__}")
        return json.dumps(_walk(data))

    def save(self, *args: Any, **kwargs: Any) -> None:
        super().save(*args, **kwargs)
