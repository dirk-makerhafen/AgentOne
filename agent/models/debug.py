
from django.db import models
from common.models import ModelWithJsonData


class DebugLogEntry(ModelWithJsonData):
    agentInstance = models.ForeignKey("AgentInstance", on_delete=models.CASCADE, related_name='debugLogEntries')
    event = models.CharField(max_length=64)
    status = models.CharField(max_length=16)

    def save(self, send_to_client=True, *args, **kwargs):
        from dashboard.tasks import send_object_to_clients
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if send_to_client:
            send_object_to_clients(self)

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