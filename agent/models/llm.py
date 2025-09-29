import copy
from django.db import models
from django.db.models import F
from jinja2 import BaseLoader, Environment
from agent.models.conversation import ConversationMessage
from common.models import ModelWithJsonData, PromptString
from tools_common.models import ToolResponse
import json
from tools_filesystem.models import FsLogEntry
from tools_memory.models import MemoryItem


class LLMQuery(ModelWithJsonData):
    agent = models.ForeignKey("Agent", on_delete=models.CASCADE, related_name="llmqueries")
    agentInstance = models.ForeignKey("AgentInstance", on_delete=models.CASCADE, related_name="llmqueries")
    model = models.ForeignKey( "providers.Model", on_delete=models.CASCADE, related_name="llmqueries")
    apikey = models.ForeignKey("providers.ApiKey", on_delete=models.SET_NULL, related_name="llmqueries", default=None, null=True)
    status = models.CharField(default="pending")  # pending, active, failed, success

    @property
    def messages(self):
        return self.data.get("messages", [])

    @messages.setter
    def messages(self, data):
        self.data["messages"] = data

    def save(self, send_to_client=True, *args, **kwargs):
        from dashboard.tasks import send_object_to_clients

        is_new = self.pk is None
        super().save(*args, **kwargs)
        if send_to_client:
            send_object_to_clients(self)

    def as_client_dict(self):
        return {
            "object": "LLMQuery",
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "model_name": self.model.name,
            "total_tokens": self.data.get("tokens", 0),
            "usage": self.data.get("usage", {}),
            "raw_data": self.data,
            "agentInstance_id": self.agentInstance_id,
            "agentId": self.agent_id,
        }

    def compile(self):
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
                            data["result"] = ToolResponse.objects.get(
                                id=part["trId"]
                            ).data
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
                        msg_cache[
                            originalpart["cmId"]
                        ] = ConversationMessage.objects.get(
                            id=originalpart["cmId"]
                        )
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


class LLMResponse(ModelWithJsonData):
    agent = models.ForeignKey("Agent", on_delete=models.CASCADE, related_name="llmResponses")
    agentInstance = models.ForeignKey("AgentInstance", on_delete=models.CASCADE, related_name="llmResponses")
    llmQuery = models.ForeignKey(LLMQuery, on_delete=models.CASCADE, related_name="llmResponses")
    completion_tokens = models.IntegerField(default=0)
    prompt_tokens = models.IntegerField(default=0)
    status = models.CharField(default="pending")  # pending, active, failed, success

    def save(self, send_to_client=True, *args, **kwargs):
        from dashboard.tasks import send_object_to_clients

        usage_data = self.data.get("usage", {})
        self.completion_tokens = usage_data.get("completion_tokens", 0)
        self.prompt_tokens = usage_data.get("prompt_tokens", 0)
        super().save(*args, **kwargs)
        if self.status=="success" and self.llmQuery:
            query = self.llmQuery
            estimated_total = query.data.get("tokens", 0)
            actual_total = self.prompt_tokens
            if estimated_total > 0 and actual_total > 0:
                correction_factor = actual_total / estimated_total
                recalculated_total = 0
                for message in query.data.get("messages", []):
                    recalculated_message_total = 0
                    for part in message.get("parts", []):
                        estimated_part_tokens = part.get("tokens", 0)
                        corrected_tokens = round(
                            estimated_part_tokens * correction_factor
                        )
                        part["tokens"] = corrected_tokens
                        recalculated_message_total += corrected_tokens
                    message["tokens"] = recalculated_message_total
                    recalculated_total += recalculated_message_total
                query.data["tokens"] = recalculated_total
                query.save()
        if send_to_client:
            send_object_to_clients(self)

    def as_client_dict(self):
        usage_data = self.data.get("usage", {})
        total_tokens = usage_data.get("total_tokens", 0) if usage_data else 0
        return {
            "object": "LLMResponse",
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "status": "completed",
            "model_name": self.llmQuery.model.name if self.llmQuery else "N/A",
            "total_tokens": total_tokens,
            "usage": usage_data,
            "raw_data": self.data,
            "agentInstance_id": self.agentInstance_id,
            "agentId": self.agent_id,
            "query_id": self.llmQuery_id,
        }
