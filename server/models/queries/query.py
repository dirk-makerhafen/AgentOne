from django.db import models
from django_enum import EnumField
from server.models.base_model import BaseModel
from django.core.exceptions import ValidationError

from server.models.content import GenericContent
from server.models.enums.message_enums import MessageContentType, MessagePartType
from server.models.message import Message
from server.models.queries.query_message import QueryMessage

class QueryStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    WAITING = 'WAITING', 'Waiting (System Blocked)'
    SUCCESS = 'SUCCESS', 'Success (Terminal)'
    FAILURE = 'FAILURE', 'Failure (Terminal)'

class Query(BaseModel):
    apikey           = models.ForeignKey("server.ApiKey"  , null=True , on_delete=models.SET_NULL,related_name="related_queries", blank=True)
    session_version  = models.ForeignKey("server.SessionVersionModel", null=False, on_delete=models.CASCADE, related_name='related_queries')
    trigger_message = models.ForeignKey("server.Message" , null=True, blank=True, on_delete=models.CASCADE, related_name='related_queries')  # the newest message in this query, the one that triggered it

    status = EnumField(QueryStatus, default=QueryStatus.WAITING)

    tags_token_usage = models.JSONField(default=dict, null=True, blank=True)
    tokens =  models.IntegerField(default=None, blank=True, null=True)

    @property
    def response(self):
        return self.related_response # pyright: ignore[reportAttributeAccessIssue]

    def add_message(self, role:str, content_type: MessageContentType, content, template_data=None, source_message:Message|None=None):
        if source_message:
            if content_type or content or template_data:
                raise Exception("Set either source_message or  content_type,content,template_data")
            query_message = QueryMessage.objects.create(role=role, query=self, source_message=source_message)
            for part in source_message.parts.all():
                if part.type not in [ MessagePartType.MESSAGE, MessagePartType.TOOLCALL]:
                    continue
                _ = query_message.add_part(source_message_part=part)

            return query_message

        if not content_type or content is None:
            raise Exception("Set either content_type, content or source_message_part")
        
        query_message = QueryMessage.objects.create(role=role, query=self)
        _ = query_message.add_part(content_type=content_type, content=content, template_data=template_data)
        return query_message

    def to_openai_message(self):
        messages = []
        tokens = 0
        tags_token_usages = []
        related_query_messages = getattr(self,"related_query_messages", None)
        if not related_query_messages:
            print("NO MESSAGES")
            return []
        
        for message in related_query_messages.all():
            try:
                qm =  message.to_openai_message()
                if qm is None:
                    continue
                if isinstance(qm, list):
                    for m in qm:
                        messages.append(m)
                else:
                    messages.append(qm)
                tokens += message.tokens
                tags_token_usages.append(message.tags_token_usage)
            except Exception as e:
                print("Failed to_openai_message", message)
                raise e
        tags_token_usage = self.merge_tag_usage(tags_token_usages)
        if self.tokens != tokens:
            self.tokens = tokens
            self.tags_token_usage = tags_token_usage
            self.save()
        return messages

    def merge_tag_usage(self, list_of_tag_dicts):
        def merge_into(a, b):
            for key, bval in b.items():
                if key == "tokens":
                    a["tokens"] = a.get("tokens", 0) + bval
                else:
                    if key not in a:
                        a[key] = {}
                    merge_into(a[key], bval)
            return a
        result = {}
        for d in list_of_tag_dicts:
            merge_into(result, d)
        return result

    def save(self, *args, **kwargs):
        #if self.pk:
        #    raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs) 
