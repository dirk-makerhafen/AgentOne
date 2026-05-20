import json
import math
from django.db import models
from django_enum import EnumField

from server.models.base_model import BaseModel
from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
from server.models.content import  GenericContent

from server.models.queries.query_message_part import QueryMessagePart


class QueryMessage(BaseModel):
    # refernces
    query         = models.ForeignKey("server.Query"                     , on_delete=models.CASCADE     , related_name='query_messages')
    tool_calls    = models.ManyToManyField("server.AgentTaskCall"                                       , related_name='query_messages', default=None)
    tool_response = models.ForeignKey("server.AgentTaskRun"          , on_delete=models.SET_DEFAULT , related_name='query_messages', default=None, null=True)
    message = models.ForeignKey("server.Message", on_delete=models.SET_DEFAULT , related_name='query_messages', default=None, null=True)

    role = EnumField(MessageRole, default=None)
    index = models.FloatField(default=0)

    content_prefix = models.ForeignKey(GenericContent,  default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="query_messages_prefix")
    content_postfix = models.ForeignKey(GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="query_messages_postfix")

    tags_token_usage = models.JSONField(default=dict, null=True, blank=True)
    tokens = models.IntegerField(default=None, blank=True, null=True)
    
    class Meta:
        ordering = ("index","pk")

    def add_message_part(self, content:str|dict, content_template: str|None = None):
        if isinstance(content, str):
            db_content = GenericContent.from_text(content)
            db_content_type = MessageContentType.TEXT
        elif isinstance(content, dict):
            db_content = GenericContent.from_data(content)
            db_content_type = MessageContentType.TEMPLATE
        db_content_template = None
        if content_template:
            db_content_template = GenericContent.from_text(content_template)
        
        return QueryMessagePart.objects.create(
            content = db_content,
            content_type = db_content_type,
            content_template = db_content_template,
            query_message = self,
        )

    def compile(self, fail_on_error=True):
        new_parts = []
        tokens = 0
        tags_token_usage = {}
        querymessage_parts = list(self.query_message_parts.all())
        is_mixed = True in [p.content_type.lower() != "text" and p.content_type.lower() != "file" for p in querymessage_parts]
        tool_call_models = []
        for querymessage_part in querymessage_parts:
            if querymessage_part.message_part:
                if  querymessage_part.message_part.type == MessagePartType.TOOLCALL:
                    tool_call_models.append(querymessage_part.message_part.tool_call)
                    continue
                if querymessage_part.message_part.type != MessagePartType.MESSAGE:
                    raise Exception("here broken")
            
            part_content = querymessage_part.compile(fail_on_error=fail_on_error)
            if isinstance(part_content, dict):
                is_mixed = True
                part_content_tokens = 0
                new_parts.append(part_content)
            elif querymessage_part.content_type == MessageContentType.TEXT or  querymessage_part.content_type == MessageContentType.TEMPLATE :
                if self.content_prefix:
                    part_content = f'{self.content_prefix.get()}{part_content}'
                if self.content_postfix:
                    part_content = f'{part_content}{self.content_postfix}'
                part_content_tokens = math.ceil(len(part_content) / 3.8)
                if is_mixed:
                    if len(new_parts) > 0 and new_parts[-1]["type"] == "TEXT":
                        new_parts[-1]["content"] += part_content
                    else:
                        new_parts.append({"type": "text", "text": part_content})
                else:
                    new_parts.append(part_content)
            elif querymessage_part.content_type == MessageContentType.IMAGE:
                part_content_tokens = 0
                new_parts.append(part_content)
            elif querymessage_part.content_type.lower() == "file":
                part_content_tokens = math.ceil(len(part_content) / 3.8)
                new_parts.append(part_content)
                if is_mixed:
                    if len(new_parts) > 0 and new_parts[-1]["type"] == "TEXT":
                        new_parts[-1]["content"] += part_content
                    else:
                        new_parts.append({"type": "text", "text": part_content})
                else:
                    new_parts.append(part_content)

            else:
                raise Exception(f"unknown content type {querymessage_part.content_type }")
            tokens += part_content_tokens
            c = tags_token_usage
            for tag in querymessage_part.tags:
                if tag not in c: 
                    c[tag] = {"tokens": 0}
                c[tag]["tokens"] += part_content_tokens
                c = c[tag]

        content_to_send = new_parts if is_mixed else  "".join(new_parts)

        if self.tokens != tokens:
            self.tags_token_usage = tags_token_usage
            self.tokens = tokens
            self.save()

        tool_calls = [{
            "id": f"tc-{toolCall.pk}",
            "type": "function",
            "function": {
                "name": toolCall.task_definition.name,
                "arguments": json.dumps(toolCall.carguments_json),
            }
        } for toolCall in list(tool_call_models)]

        message =  {"role": self.role, "content": content_to_send}

        if self.tool_response and self.role == "tool":
            message["tool_call_id"] = f"tc-{self.tool_response.agent_task_call.pk}"
            message["content"] = json.dumps(self.tool_response.result_json)
            message["name"] = self.tool_response.agent_task_definition.name

        elif tool_calls:
            message["tool_calls"] = tool_calls
            del message["content"]
        return message

    def save(self, *args, **kwargs):
        #if self.pk:
        #    raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs) 
