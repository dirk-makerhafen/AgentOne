from ast import arguments
from django.db import models
import traceback
import random
from core.models.base_model import BaseModel
from tools.definitions.models.tool_installation import ToolInstallation
from tools.instances.models.tool_instance import ToolInstance

class ToolCall(BaseModel):
    class ToolCallStatusChoices(models.TextChoices):
        PENDING = 'IDLE', 'Idle'
        SUCCESS = 'SUCCESS', 'Success'
        FAILED = 'FAILED', 'Failed'

    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name='toolCalls')
    agentInstance = models.ForeignKey("agents.AgentInstance", on_delete=models.CASCADE, related_name='toolCalls')
    conversationMessage = models.ForeignKey("agents.ConversationMessage", null=True, default=None, on_delete=models.CASCADE, related_name='toolCalls')
    conversationMessagePart = models.ForeignKey("agents.ConversationMessagePart", null=True, default=None, blank=True, on_delete=models.SET_DEFAULT, related_name='toolCalls')

    tool_name = models.CharField(max_length=255, default="")
    function_name = models.CharField(max_length=64)
    status = models.CharField(max_length=10, default=ToolCallStatusChoices.PENDING, choices=ToolCallStatusChoices.choices)

    @property
    def arguments(self):
        return self.data.get('arguments', {})

    @arguments.setter
    def arguments(self, data):
        self.data['arguments'] = data

    def as_client_dict(self):
        toolResponse = self.toolResponses.last()
        return {
            'object': 'ToolCall', 
            'id': self.id, 
            "agent_id": self.agent_id,
            "agentInstance_id": self.agentInstance_id, 
            'created_at': self.created_at.isoformat(), 
            'function_name': self.function_name, 
            'arguments': self.arguments, 
            'status': self.status, 
            'result': toolResponse.data if toolResponse else None
        }

    def run(self):
        from tools.calls.models.tool_response import ToolResponse
        from tools.base.buildin_tools_map import BUILTIN_TOOL_CLASS_MAP

        if self.status != ToolCall.ToolCallStatusChoices.PENDING:
            raise Exception('Tool call not pending, cant run')
        success = False
        result = None
        try:
            if "." in self.function_name:
                tool_name, method_name = self.function_name.split('.', 1)
                available_tool_definitions = list(self.agent.available_tools.filter(name= tool_name, is_active= True))
            else:
                method_name = self.function_name
                available_tool_definitions = list(self.agent.available_tools.filter(is_builtin=True, is_active= True))

            tool_installations = []
            builtin_function = None
            
            for tool_definition in available_tool_definitions:
                if tool_definition.has_tool_name(method_name):
                    if tool_definition.is_builtin:
                        builtin_tool_instance = BUILTIN_TOOL_CLASS_MAP[tool_definition.name](agentInstance=self.agentInstance)
                        builtin_function = builtin_tool_instance.call_tool
                        break
                    else:
                        per_agent_installations = tool_definition.installations.filter(status=ToolInstallation.ToolInstallationStatusChoices.INSTALLED, agent_instance=self, system=self.system).all()
                        per_system_installations = tool_definition.installations.filter(status=ToolInstallation.ToolInstallationStatusChoices.INSTALLED, agent_instance=None, system=self.system).all()
                        tool_installations.extend(per_agent_installations)
                        tool_installations.extend(per_system_installations)
            
            if builtin_function:
                success, result = builtin_function(toolCall=self, name=method_name, arguments = self.arguments)
            else:
                if tool_installations:
                    tool_instances = []
                    for tool_installation in tool_installations:
                        tool_instances.extend(tool_installation.instances.filter(status=ToolInstance.ToolInstanceStatusChoices.RUNNING))
                    tool_instances = list(set(tool_installations))
                    if tool_instances:
                        mcp_client = random.choice(tool_instances).mcp_client
                        mcp_result =  mcp_client.call_tool(name=method_name, arguments=arguments)
                        if "result" in mcp_result:
                            result = mcp_result["result"]
                            success = True 
                        elif "error" in mcp_result:
                            result = {"status": "error"}
                            success = False 
                            if "message" in mcp_result:
                                result["message"] = mcp_result["message"]
                            if "data" in mcp_result:
                                result["data"] = mcp_result["data"]
                else:
                    success = False
                    result = {"status": "error", "message": f"no tool named {self.function_name} found"}
        except Exception as e:
            result = {'status': 'failed', 'exception': f'{e} - {traceback.format_exc()}'}
        toolresponse = ToolResponse()
        toolresponse.agent = self.agentInstance.agent
        toolresponse.agentInstance = self.agentInstance
        toolresponse.toolCall = self
        toolresponse.status = ToolResponse.ToolResponseStatusChoices.SUCCESS if success else ToolResponse.ToolResponseStatusChoices.FAILED
        toolresponse.data = result
        toolresponse.save()
        self.status =  ToolCall.ToolCallStatusChoices.SUCCESS if success else ToolCall.ToolCallStatusChoices.FAILED
        self.save()
