from django.db import models
import traceback
from core.models.base_model import BaseModel

class ToolCall(BaseModel):
    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name='toolCalls')
    agentInstance = models.ForeignKey("agents.AgentInstance", on_delete=models.CASCADE, related_name='toolCalls')
    conversationMessage = models.ForeignKey("agents.ConversationMessage", null=True, default=None, on_delete=models.CASCADE, related_name='toolCalls')
    
    tool_name = models.CharField(max_length=255, default="")
    function_name = models.CharField(max_length=64)
    status = models.CharField(max_length=10, default='pending')

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
        if self.status != 'pending':
            raise Exception('Tool call not pending, cant run')
        success = False
        result = None
        try:
            _function = self.agentInstance.get_tool_function(self.function_name)
            if _function is None:
                result = {'status': 'failed', 'message': f"No such function '{self.function_name}'"}
            else:
                err = None
                for arg in self.arguments:
                    if arg not in _function['arguments']:
                        err = f"Unknown argument '{arg}'"
                        break
                for arg in _function['arguments']:
                    if _function['arguments'][arg]['required'] == True and arg not in self.arguments:
                        err = f'Missing required argument {arg}'
                        break
                if err is not None:
                    result = {'status': 'failed', 'message': err}
                else:
                    success, result = _function['callable'](toolCall=self, **self.arguments)
        except Exception as e:
            result = {'status': 'failed', 'exception': f'{e} - {traceback.format_exc()}'}
        toolresponse = ToolResponse()
        toolresponse.agent = self.agentInstance.agent
        toolresponse.agentInstance = self.agentInstance
        toolresponse.toolCall = self
        toolresponse.status = 'success' if success else 'failed'
        toolresponse.data = result
        toolresponse.save()
        self.status = 'success' if success else 'failed'
        self.save()
