import copy
from django.db import models
from jinja2 import BaseLoader, Environment
import json

from core.models.base_model import BaseModel

class LLMQuery(BaseModel):
    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name="llmQueries")
    agentInstance = models.ForeignKey("agents.AgentInstance", on_delete=models.CASCADE, related_name="llmQueries")
    aimodel = models.ForeignKey("providers.AiModel", on_delete=models.CASCADE, related_name="llmQueries")
    apikey = models.ForeignKey("providers.ApiKey", on_delete=models.SET_NULL, related_name="llmQueries", default=None, null=True)
    status = models.CharField(default="pending", max_length=255)

    @property
    def messages(self):
        return self.data.get("messages", [])

    @messages.setter
    def messages(self, data):
        self.data["messages"] = data

    def as_client_dict(self):
        return {
            "object": "LLMQuery",
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "model_name": self.aimodel.name,
            "total_tokens": self.data.get("tokens", 0),
            "usage": self.data.get("usage", {}),
            "raw_data": self.data,
            "agentInstance_id": self.agentInstance_id,
            "agentId": self.agent_id,
        }

    def compile(self):
        from core.models.prompt_string import PromptString
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
                    template = PromptString.objects.get(pk=part["tpId"]).value
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
