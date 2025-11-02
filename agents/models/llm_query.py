import copy
from django.db import models
from jinja2 import BaseLoader, Environment
import json

from core.models.base_model import BaseModel
from tools.builtin_memory.models.memory_item import MemoryItem

class LLMQuery(BaseModel):
    class LLMQueryStatusChoices(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        ACTIVE = 'ACTIVE', 'Active'
        SUCCESS = 'SUCCESS', 'successfull'
        FAILED = 'FAILED', 'Failed'

    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name="llmQueries")
    agentInstance = models.ForeignKey("agents.AgentInstance", on_delete=models.CASCADE, related_name="llmQueries")
    aimodel = models.ForeignKey("providers.AiModel", on_delete=models.CASCADE, related_name="llmQueries")
    apikey = models.ForeignKey("providers.ApiKey", on_delete=models.SET_NULL, related_name="llmQueries", default=None, null=True)
    status = models.CharField(max_length=255, choices=LLMQueryStatusChoices.choices, default=LLMQueryStatusChoices.PENDING)
    tags_token_usage = models.JSONField(default=dict, null=True, blank=True)
    tokens =  models.IntegerField(default=None, blank=True, null=True)

    def as_client_dict(self):
        return {
            "object": "LLMQuery",
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            'status_display': self.get_status_display(),
            "model_name": self.aimodel.name,
            "tokens": self.tokens if self.tokens else 0,
            "usage": self.tags_token_usage if self.tags_token_usage else {},
            "raw_data": self.data,
            "agentInstance_id": self.agentInstance_id,
            "agentId": self.agent_id,
            "messages": [m.as_client_dict() for m in self.queryMessages.order_by("index", "created_at").all()]
        }

    def compile_old(self):
        from core.models.prompt import PromptVariant
        from agents.models.conversation_message import ConversationMessage
        from tools.builtin_filesystem.models.fs_log_entry import FsLogEntry
        from tools.builtin_memory.models.memory_item import MemoryItem
        from tools.calls.models.tool_response import ToolResponse

        new_messages = []
        self.data["tokens"] = 0
        self.data["usage"] = {}
        for message in self.data.get("messages", []):
            new_parts = []
            message["tokens"] = 0
            msg_cache = {}
            for originalpart in message.get("parts", []):
                part = copy.deepcopy(originalpart)
                tags = originalpart.get("tags", ["Other"])
                c = self.data["usage"]
                for tag in tags:
                    if tag not in c:
                        c[tag] = {"tokens": 0}
                    c = c[tag]
                part_content = ""
                if "tpId" in part:
                    template = PromptVariant.objects.get(pk=part["tpId"]).value
                    rtemplate = Environment(loader=BaseLoader).from_string(template)
                    data = part.get("data", {})
                    if "memories" in data:
                        for m in data["memories"]:
                            m["content"] = MemoryItem.objects.get(pk=m["pk"]).value
                    if "trId" in part:
                        try:
                            data["result"] = ToolResponse.objects.get(id=part["trId"]).data
                        except ToolResponse.DoesNotExist:
                            data["result"] = None
                    if "data" in part and "fs_content_type" in part["data"]:
                        item = FsLogEntry.objects.get(id=int(part["data"]["fs_content_id"]))
                        if part["data"]["load_mode"] == "summary":
                            data["content"] = json.dumps(item.summary)
                        else:
                            data["content"] = item.content
                    part_content = rtemplate.render(**data)
                elif "cmId" in originalpart and "pnr" in originalpart:
                    if originalpart["cmId"] not in msg_cache:
                        msg_cache[originalpart["cmId"]] = ConversationMessage.objects.get(id=originalpart["cmId"])
                    part_content = msg_cache[originalpart["cmId"]].data["parts"][originalpart["pnr"]]["content"]
                else:
                    raise Exception(f"unable to render {originalpart}")
                if part_content != "":
                    if originalpart.get("warn_forget", False) is True:
                        part_content = f"@@@TO_BE_FORGOTTEN@@@{part_content}"
                    new_parts.append(part_content)
                originalpart["tokens"] = len(part_content) // 3.8
                c = self.data["usage"]
                for tag in tags:
                    c[tag]["tokens"] += originalpart["tokens"]
                    c = c[tag]
                message["tokens"] += originalpart["tokens"]
            self.data["tokens"] += message["tokens"]
            new_content = "".join(new_parts)
            if message.get("warn_forget", False) is True:
                new_content = f"@@@TO_BE_FORGOTTEN@@@{new_content}"
            new_messages.append({"role": message["role"], "content": new_content})
        self.save()
        return new_messages

    def compile(self):
        messages = []
        tokens = 0
        tags_token_usages = []
        for message in self.queryMessages.all():
            qm =  message.compile()
            messages.append(qm)
            tokens += message.tokens
            tags_token_usages.append(message.tags_token_usage)
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
                    if key not in a: a[key] = {}
                    merge_into(a[key], bval)
            return a
        result = {}
        for d in list_of_tag_dicts:
            merge_into(result, d)
        return result
    

class QueryMessage(BaseModel):
    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name="queryMessages")
    agentInstance = models.ForeignKey("agents.AgentInstance", on_delete=models.CASCADE, related_name="queryMessages")
    llmQuery = models.ForeignKey(LLMQuery, default=None, null=True, on_delete=models.SET_DEFAULT, related_name='queryMessages')
    role = models.CharField(max_length=32)
    tags_token_usage = models.JSONField(default=dict, null=True, blank=True)
    tokens =  models.IntegerField(default=None, blank=True, null=True)
    index =  models.IntegerField(default=0)
    content_prefix = models.CharField(max_length=10000, blank=True, null=True, default=None)
    content_postfix = models.CharField(max_length=10000, blank=True, null=True, default=None)

    def as_client_dict(self):
        return {
            'object': 'QueryMessage',
            "id": self.id,  
            "agent_id": self.agent_id, 
            "agentInstance_id": self.agentInstance_id, 
            "query_id": self.llmQuery_id,  
            'created_at': self.created_at.isoformat(), 
            'role': self.role,
            'content_prefix': self.content_prefix,
            'content_postfix': self.content_postfix,
            'parts': [p.as_client_dict() for p in self.queryMessageParts.all()]
        }
    
    def compile(self):
        new_parts = []
        tokens = 0
        tags_token_usage = {}
        queryMessageParts = list(self.queryMessageParts.all())
        is_mixed = True in [p.content_type.lower() != "text" for p in queryMessageParts]
        for queryMessagePart in queryMessageParts:
            part_content = queryMessagePart.compile()
            print(queryMessagePart.content_type )
            if queryMessagePart.content_type.lower() == "text":
                if self.content_prefix:
                    part_content = f'{self.content_prefix}{part_content}'
                if self.content_postfix:
                    part_content = f'{part_content}{self.content_postfix}'
                part_content_tokens = len(part_content) // 3.8
                if is_mixed:
                    if len(new_parts) > 0 and new_parts[-1]["type"] == "TEXT":
                        new_parts[-1]["content"] += part_content
                    else: 
                        new_parts.append({"type": "text", "text": part_content})
                else:
                    new_parts.append(part_content)
            elif queryMessagePart.content_type.lower() == "image":
                part_content_tokens = 0
                new_parts.append({"type": "image_url", "image_url": {
                    "url": part_content
                }})
            else:
                raise Exception(f"unknown content type {queryMessagePart.content_type }")
            tokens += part_content_tokens
            c = tags_token_usage
            for tag in queryMessagePart.tags:
                if tag not in c: c[tag] = {"tokens":0}
                c[tag]["tokens"] += part_content_tokens
                c = c[tag]
       
        content_to_send = new_parts if is_mixed else  "".join(new_parts)

        if self.tokens != tokens:
            self.tags_token_usage = tags_token_usage
            self.tokens = tokens
            self.save()
        return {"role": self.role, "content": content_to_send}


class QueryMessagePart(BaseModel):
    queryMessage = models.ForeignKey(QueryMessage, default=None, null=True, on_delete=models.SET_DEFAULT, related_name='queryMessageParts')
    toolCall = models.ForeignKey("calls.ToolCall", default=None, null=True, on_delete=models.SET_DEFAULT, related_name='queryMessageParts')
    toolResponse = models.ForeignKey("calls.ToolResponse",  default=None, null=True, on_delete=models.SET_DEFAULT, related_name='queryMessageParts')
    promptVariant = models.ForeignKey("core.PromptVariant",  default=None, null=True, on_delete=models.SET_DEFAULT, related_name='queryMessageParts')
    conversationMessage = models.ForeignKey("agents.ConversationMessage", default=None, null=True, on_delete=models.SET_DEFAULT, related_name='used_in_queryMessageParts')
    conversationMessagePart = models.ForeignKey("agents.ConversationMessagePart", default=None, null=True, on_delete=models.SET_DEFAULT, related_name='used_in_queryMessageParts')
    fsLogEntry = models.ForeignKey("builtin_filesystem.FsLogEntry", default=None, null=True, on_delete=models.SET_DEFAULT, related_name='used_in_queryMessageParts')

    tokens =  models.IntegerField(default=None, blank=True, null=True)
    index =  models.IntegerField(default=0)
    content = models.CharField(max_length=1000000, blank=True, null=True, default=None)
    content_prefix = models.CharField(max_length=10000, blank=True, null=True, default=None)
    content_postfix = models.CharField(max_length=10000, blank=True, null=True, default=None)
    class QueryMessagePartContentType(models.TextChoices):
            TEXT = 'TEXT', 'Text'
            IMAGE = 'IMAGE', 'Image'
    content_type = models.CharField(max_length=255, choices=QueryMessagePartContentType.choices, default=QueryMessagePartContentType.TEXT)

    tags = models.JSONField(default=list, null=True, blank=True, help_text="List of tags used")
    template_data = models.JSONField(default=dict, null=True, blank=True, help_text="the data field that we use to render the prompt, if existing")

    def as_client_dict(self):
        return {
            'object': 'QueryMessagePart',
            "id": self.id,  
            "query_message_id": self.queryMessage_id, 
            "tool_call_id": self.toolCall_id,
            "tool_response_id": self.toolResponse_id,
            'prompt_variant_id': self.promptVariant_id,
            'conversationMessage_id': self.conversationMessage_id,
            'conversation_message_part_id': self.conversationMessagePart_id,
            'fsLogEntry_id': self.fsLogEntry_id,
            'tokens': self.tokens,
            'index': self.index,
            'content': self.content,
            'content_prefix': self.content_prefix,
            'content_postfix': self.content_postfix,
            'tags': self.tags,
            'template_data': self.template_data,
        }

    def compile(self):
        part_content = ""
        if self.promptVariant:
            template = self.promptVariant.value
            rtemplate = Environment(loader=BaseLoader).from_string(template)
            data = copy.deepcopy(self.template_data)
            if "memories" in data:
                for m in data["memories"]:
                    m["content"] = MemoryItem.objects.get(pk=m["pk"]).value
            if self.toolResponse:
                data["result"] = self.toolResponse.data if self.toolResponse else None
            if self.fsLogEntry:
                if self.fsLogEntry.load_mode == "summary":
                    data["content"] = self.fsLogEntry.summary
                else:
                    data["content"] = self.fsLogEntry.content
            part_content = rtemplate.render(**data)
        elif self.conversationMessagePart:
            part_content = self.conversationMessagePart.content if self.conversationMessagePart else ""
        else:
            raise Exception(f"unable to render QueryMessagePart ID:{self.pk}")

        if self.content_prefix:
            part_content = f'{self.content_prefix}{part_content}'
        if self.content_postfix:
            part_content = f'{part_content}{self.content_postfix}'

        tokens = len(part_content) // 3.8
        if self.tokens != tokens:
            self.tokens = tokens
            self.save()
        return part_content
       