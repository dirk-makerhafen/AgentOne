from django.db import models

class MessageRole(models.TextChoices):
    ASSISTANT = "assistant"
    USER = "user"
    SYSTEM = "system"
    TOOL = "tool"

class MessageSource(models.TextChoices):
    default = "default"
    human_chat_message = "human_chat_message"
    tool_response = "tool_response"
    assistant_llm_response =  "llm_response"
    assistant_code_response = "assistant_code_response"

class MessageContentType(models.TextChoices):
    IMAGE = "IMAGE"
    TEXT = "TEXT"
    JSON = "JSON"
    TEMPLATE = "TEMPLATE"

class MessagePartType(models.TextChoices):
    REASONING = "REASONING"
    MESSAGE = "MESSAGE"
    TOOLCALL = "TOOLCALL"
