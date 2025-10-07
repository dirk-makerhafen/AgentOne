from django.db import models
from core.models.base_model import BaseModel

class DebugLogEntry(BaseModel):
    agentInstance = models.ForeignKey("agents.AgentInstance", on_delete=models.CASCADE, related_name='debugLogEntries')
    event = models.CharField(max_length=64)
    status = models.CharField(max_length=16)

    def as_client_dict(self):
        return {
            'object': 'DebugLogEntry', 
            'id': self.id, 
            "agent_id": self.agentInstance.agent.agent_pk, 
            "agentInstance_id": self.agentInstance.instance_pk,  
            'created_at': self.created_at.isoformat(), 
            'event': self.event, 
            'data': self.data
        }
