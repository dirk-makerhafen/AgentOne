

import traceback
from agents.models.agent import Agent
from core.models.base_model import BaseModel
from django.db import models
from django.db.models import Q, CheckConstraint

from events.models.event_handler import EventHandler


class ExecutionMode(models.TextChoices):
    BLOCKING = 'BLOCKING', 'Block until event is finished (default)'
    PARALLEL = 'PARALLEL', 'Run in parallel with other EventSubscriptions'
    DETACHED = 'DETACHED', 'Run in background, not blocking'

class EventSubscription(BaseModel):
    emitter_agent = models.ForeignKey(Agent, default=None, on_delete=models.CASCADE, related_name='event_subscriptions', null=True, blank=True)
    emitter_agentInstance = models.ForeignKey("agents.AgentInstance", default=None, on_delete=models.CASCADE, related_name='emitted_event_subscriptions', null=True, blank=True)
    receiver_agentInstance = models.ForeignKey("agents.AgentInstance", default=None, on_delete=models.CASCADE, related_name='reveived_event_subscriptions', null=True, blank=True)

    eventHandler   = models.ForeignKey(EventHandler, default=None, on_delete=models.CASCADE, related_name='event_subscriptions', null=True, blank=True)
    description    = models.CharField(default="", help_text="description", max_length=100000, blank=True)
    ignore_error   = models.BooleanField(default=False, help_text="ignore exceptions and errors at runtime")
    execution_mode = models.CharField(max_length=32, choices=ExecutionMode.choices, default=ExecutionMode.BLOCKING)

    def as_client_dict(self):
        receiver_dict = None
        if self.eventHandler:
            receiver_agent_dict = None
            if self.eventHandler.receiver_agent:
                receiver_agent_dict = {
                    'pk': self.eventHandler.receiver_agent.pk, 
                    'name': self.eventHandler.receiver_agent.name
                }
            receiver_dict = {
                'id': self.eventHandler.pk,
                'name': self.eventHandler.name,
                'agent': receiver_agent_dict,
            }

        return {
            'object': 'EventSubscription',
            'id': self.pk,
            'agent': {'pk': self.emitter_agent.pk, 'name': self.emitter_agent.name} if self.emitter_agent else None,
            'agentInstance': {'pk': self.emitter_agentInstance.pk} if self.emitter_agentInstance else None,
            'eventHandler': receiver_dict,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
            

    class Meta:
        unique_together = (('emitter_agent', 'emitter_agentInstance', "eventHandler"),)
        constraints = [CheckConstraint(condition=Q(emitter_agent__isnull=False, emitter_agentInstance__isnull=True) | Q(emitter_agent__isnull=True, emitter_agentInstance__isnull=False),name='ensure_one_parent_is_set_for_EventSubscription')]
    
    def clean(self):
        if (self.emitter_agent is None and self.emitter_agentInstance is None) or (self.emitter_agent is not None and self.emitter_agentInstance is not None):
            raise models.ValidationError('A EventHandler must be owned by either Agent or AgentInstance, but not both.')
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

