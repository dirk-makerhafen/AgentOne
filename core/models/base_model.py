from datetime import datetime
from dirtyfields import DirtyFieldsMixin
from dirtyfields.dirtyfields import reset_state
from django.db import models
import json
from django.utils import timezone
from django.contrib.auth.models import User

class BaseModel(DirtyFieldsMixin, models.Model):
    created_at = models.DateTimeField(db_index=True, editable=False, default=datetime.now)
    updated_at = models.DateTimeField(editable=False, default=datetime.now)
    raw_data = models.TextField(max_length=100 * 1024 * 1024, default='')

    @property
    def data(self):
        if not hasattr(self, '_data') or self._data is None:
            try:
                self._data = json.loads(self.raw_data) if self.raw_data else {}
            except Exception as e:
                self._data = {'__error': f'Failed to load data for {self}: {e}'}
        return self._data

    @data.setter
    def data(self, data):
        self._data = data
    
    def save(self, send_to_client=True, *args, **kwargs):
        now = timezone.now()
        if not self.pk and self.created_at is None:
            self.created_at = now
        
        _dirty_fields = self.get_dirty_fields(check_relationship=True)
        self.updated_at = now
        if hasattr(self, '_data'):
            new_raw_data = json.dumps(self.data)
            if self.raw_data != new_raw_data:
                self.raw_data = new_raw_data
                _dirty_fields['raw_data'] = self.raw_data

        update_fields = kwargs.get('update_fields')
        if self.pk is not None:
            if update_fields is None:
                update_fields = list(_dirty_fields.keys())
            
            if 'updated_at' not in update_fields:
                update_fields.append('updated_at')
            if 'raw_data' in _dirty_fields and 'raw_data' not in update_fields:
                update_fields.append('raw_data')
            
            kwargs['update_fields'] = update_fields

        r = super().save(*args, **kwargs)
        reset_state(sender=self.__class__, instance=self, update_fields=kwargs.get("update_fields",[]))
        if send_to_client:
            self.send_object_to_clients()
        return r


    def send_object_to_clients(self, instance_pk=None):
        from agents.models.agent import Agent
        from agents.models.agent_instance import AgentInstance
        from core.models.prompt_string import PromptString
        from core.tasks.send_websocket_update import celery_send_websocket_update
        from providers.models.api_provider import ApiProvider
        from systems.models.system import System
        from tools.definitions.models.tool_definition import ToolDefinition
        from tools.definitions.models.tool_installation import ToolInstallation
        from tools.instances.models.tool_instance import ToolInstance

        message_data = self if isinstance(self, dict) else self.as_client_dict()
        
        target_instance_pk = None
        target_user_pks = set()

        # Determine target(s) based on object type
        if instance_pk:
            target_instance_pk = instance_pk
        elif hasattr(self, 'agentInstance') and self.agentInstance:
            target_instance_pk = self.agentInstance.pk
        elif isinstance(self, Agent):
            target_user_pks.update(self.owners.values_list('pk', flat=True))
        elif isinstance(self, AgentInstance):
            target_user_pks.update(self.agent.owners.values_list('pk', flat=True))
        elif isinstance(self, PromptString):
            target_user_pks.add(self.owner_id)
        elif isinstance(self, (System, ApiProvider, ToolInstance, ToolDefinition, ToolInstallation)): # Added ToolInstallation
            # Global objects are broadcast to all users
            target_user_pks.update(User.objects.values_list('pk', flat=True))
        else:
            # Fallback for dictionaries that might specify scope
            if isinstance(self, dict) and 'agentInstance_id' in self and self['agentInstance_id']:
                target_instance_pk = self['agentInstance_id']
            elif isinstance(self, dict) and 'user_pk' in self and self['user_pk']:
                target_user_pks.add(self['user_pk'])
            else:
                print(f'Warning: send_object_to_clients received unhandled object type: {type(self)} with no clear target.')
                return

        # Dispatch messages via Celery
        if target_instance_pk:
            celery_send_websocket_update.delay(message_data, instance_pk=target_instance_pk)
        
        for user_pk in target_user_pks:
            celery_send_websocket_update.delay(message_data, user_pk=user_pk)



    class Meta:
        abstract = True
