

from agents.models.agent import Agent
from core.models.base_model import BaseModel
from django.db import models
from django.db.models import Q, CheckConstraint
from events.models.event_type import EventType

'''
EvSub:Emitter   EvHandler:Receiver    Description    (
 AgentA          AgentB              Event emitted by any instance of AgentA is received by a instance of AgentB. This AgentB Instance will be created if it does not exist
 AgentA          AgentBInstance      Event emitted by any instance of AgentA is received by AgentInstanceB
 AgentAInstance  AgentB              Event emitted by         AgentAInstance is received by a instance of AgentB. This AgentB Instance will be created if it does not exist
 AgentAInstance  AgentBInstance      Event emitted by         AgentAInstance is received by AgentBInstance
'''

class EventHandler(BaseModel):
    receiver_agent = models.ForeignKey(Agent, default=None, on_delete=models.CASCADE, related_name='event_handlers', null=True, blank=True)
    receiver_agentInstance = models.ForeignKey("agents.AgentInstance", default=None, on_delete=models.CASCADE, related_name='event_handlers', null=True, blank=True)
    event = models.ForeignKey(EventType, default=None, on_delete=models.CASCADE, related_name='event_handlers', null=True, blank=True)
    name = models.CharField(help_text="unique name of eventhandler", max_length=512)
    description =  models.CharField(default="",help_text="description", max_length=100000, blank=True)
    enabled = models.BooleanField(default=True, help_text="enabled")
    source_path = models.CharField(default="",help_text="path of sourcecode to load function from", max_length=4000, blank=True)
    source_string = models.CharField(default="",help_text="sourcecode string to load function from", max_length=100000, blank=True)
    source_function_name = models.CharField(default="",help_text="full name of function to load/call", max_length=4000)

    def as_client_dict(self):
        return {
            'object': 'EventHandler',
            'id': self.pk,
            'agent': {'pk': self.receiver_agent.pk, 'name': self.receiver_agent.name} if self.receiver_agent else None,
            'agentInstance': {'pk': self.receiver_agentInstance.pk} if self.receiver_agentInstance else None,
            'event': self.event,
            'name': self.name,
            'description': self.description,
            'source': self.source_function_name,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

    class Meta:
        constraints = [CheckConstraint(condition=Q(receiver_agent__isnull=False, receiver_agentInstance__isnull=True) | Q(receiver_agent__isnull=True, receiver_agentInstance__isnull=False),name='ensure_one_parent_is_set_for_EventHandler')]
        unique_together = (('receiver_agent', 'receiver_agentInstance', "event", "name"),)

    def clean(self):
        if (self.receiver_agent is None and self.receiver_agentInstance is None) or (self.receiver_agent is not None and self.receiver_agentInstance is not None):
            raise models.ValidationError('A EventHandler must be owned by either Agent or AgentInstance, but not both.')
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
            return f'Pk:{self.pk} Event:{self.event.name} Name:{self.name}'
    