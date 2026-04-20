from django.db import models
from django_enum import EnumField
from server.models.enums.message_enums import MessageRole, MessageSource
from server.models.conversation_message_part import ConversationMessagePart
from server.models.base_model import BaseModel
from server.models.content import GenericContent


class ConversationMessage(BaseModel):
    #reference tracking
    agent_instance_version = models.ForeignKey("server.AgentInstanceVersion", on_delete=models.CASCADE, related_name="related_conversation_messages")
    query          = models.ForeignKey("server.Query"        , null=True, blank=True, on_delete=models.CASCADE, related_name='related_conversation_messages')
    response       = models.ForeignKey("server.Response"     , null=True, blank=True, on_delete=models.CASCADE, related_name='related_conversation_messages')
    tool_calls     = models.ManyToManyField("server.AgentTaskCall",related_name='related_conversation_messages')
    index          = models.FloatField(default=0)

    role = models.CharField(choices=MessageRole.choices, default=MessageRole.USER, max_length=61)
    source = models.CharField(choices=MessageSource.choices, default=MessageSource.default, max_length=61)

    hide_from_context = models.BooleanField(default=False)
    pin_to_context = models.BooleanField(default=False)
    
    class Meta:
        ordering = ("index","pk")

    def add_part(self, content: str|GenericContent):
        ocontent = content
        try:
            if isinstance(content, str):
                content = GenericContent.from_text(content)
            ConversationMessagePart.objects.create(
                message=self,
                content=content,
                content_type="TEXT",
            )
        except Exception as e:
            raise Exception(f"failed to add {content}, ocontent: {ocontent}: {e}")

    def save(self, *args, **kwargs):
        if self.hide_from_context is True and self.pin_to_context is True:
            self.pin_to_context = False
        super().save(*args, **kwargs)
