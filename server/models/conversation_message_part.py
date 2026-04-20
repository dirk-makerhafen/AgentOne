from django.db import models
from django_enum import EnumField
from server.models.enums.message_enums import MessageContentType
from server.models.base_model import BaseModel
from server.models.content import  GenericContent
from django.core.exceptions import ValidationError


class ConversationMessagePart(BaseModel):
    message = models.ForeignKey("server.ConversationMessage", on_delete=models.CASCADE, related_name='parts')

    tokens = models.IntegerField(default=0)
    index  = models.FloatField(default=0)

    content          = models.ForeignKey(GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="conversation_message_parts_content")
    content_type     = EnumField(MessageContentType, default=MessageContentType.TEXT)
    content_template = models.ForeignKey(GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="conversation_message_parts_template")

    def save(self, *args, **kwargs):
        #if self.pk:
        #    raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs) 

    class Meta:
        ordering = ("index","pk")