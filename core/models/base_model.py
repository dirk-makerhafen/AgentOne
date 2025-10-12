from datetime import datetime
from dirtyfields import DirtyFieldsMixin
from dirtyfields.dirtyfields import reset_state
from django.db import models
import json
from django.utils import timezone
from django.contrib.auth.models import User

class BaseModel(DirtyFieldsMixin, models.Model):
    created_at = models.DateTimeField(db_index=True, editable=False)
    updated_at = models.DateTimeField(editable=False)
    raw_data = models.TextField(max_length=100 * 1024 * 1024, default='')

    # Forking and Data Deduplication fields
    fork_of = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='forks')
    raw_data_reference = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='data_references')

    @property
    def data(self):
        if not hasattr(self, '_data') or self._data is None:
            source_raw_data = self.raw_data
            if self.raw_data_reference:
                source_raw_data = self.raw_data_reference.raw_data
            try:
                self._data = json.loads(source_raw_data) if source_raw_data else {}
            except Exception as e:
                self._data = {'__error': f'Failed to load data for {self}: {e}'}
        return self._data

    @data.setter
    def data(self, new_data):
        # This is the copy-on-write logic. Setting new data breaks the reference.
        if self.raw_data_reference is not None:
            self.raw_data_reference = None
        self._data = new_data
    
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

        if self.pk is not None:
            if 'update_fields' not in kwargs:
                fields_to_update = list(_dirty_fields.keys())
                if 'updated_at' not in fields_to_update:
                    fields_to_update.append('updated_at')
                if 'raw_data' not in fields_to_update and 'raw_data' in _dirty_fields:
                    fields_to_update.append('raw_data')
                if fields_to_update:
                    kwargs['update_fields'] = fields_to_update
            else:
                if 'updated_at' not in kwargs['update_fields']:
                    kwargs['update_fields'].append('updated_at')
                if 'raw_data' in _dirty_fields and 'raw_data' not in kwargs['update_fields']:
                    kwargs['update_fields'].append('raw_data')
        
        r = super().save(*args, **kwargs)
        reset_state(sender=self.__class__, instance=self, update_fields=kwargs.get("update_fields",[]))
        if send_to_client:
            self.send_object_to_clients()
        return r

    def get_delete_broadcast_payload(self):
        """
        Subclasses should override this method to return a dictionary payload
        for the WebSocket broadcast upon deletion. If it returns None, no
        broadcast is sent.
        """
        return None

    def delete(self, *args, **kwargs):
        from core.tasks.send_websocket_update import celery_send_websocket_update
        from django.contrib.auth.models import User

        # Get the model-specific payload *before* the object is deleted.
        message_data = self.get_delete_broadcast_payload()

        # Perform the actual deletion.
        super().delete(*args, **kwargs)

        # If a payload was provided, broadcast it to all users.
        if message_data:
            all_user_pks = User.objects.values_list('pk', flat=True)
            for pk in all_user_pks:
                celery_send_websocket_update.delay(message_data, user_pk=pk)


    def send_object_to_clients(self, instance_pk=None):
        from agents.models.agent import Agent
        from agents.models.agent_instance import AgentInstance
        from agents.models.agent_fork import AgentFork # Import AgentFork
        from core.models.prompt_string import PromptString
        from core.tasks.send_websocket_update import celery_send_websocket_update
        from providers.models.ai_model import AiModel
        from providers.models.api_key import ApiKey
        from providers.models.api_provider import ApiProvider
        from systems.models.system import System
        from tools.definitions.models.tool_definition import ToolDefinition
        from tools.definitions.models.tool_installation import ToolInstallation
        from tools.instances.models.tool_instance import ToolInstance
        from django.contrib.auth.models import User

        # Ensure message_data is always a dictionary and copy it if it's already one
        base_message_data = self.as_client_dict() if not isinstance(self, dict) else dict(self)

        target_instance_pks = set() # Use a set to avoid duplicates and handle multiple targets
        target_user_pks = set()

        if instance_pk: # Explicit override via instance_pk parameter
            target_instance_pks.add(instance_pk)
        elif isinstance(self, AgentFork):
            # AgentFork needs to be sent to both parent and child instances
            target_instance_pks.add(self.parent_instance.pk)
            target_instance_pks.add(self.child_instance.pk)
        elif hasattr(self, 'agentInstance') and self.agentInstance:
            target_instance_pks.add(self.agentInstance.pk)
        elif isinstance(self, Agent):
            target_user_pks.update(self.owners.values_list('pk', flat=True))
        elif isinstance(self, AgentInstance):
            target_user_pks.update(self.agent.owners.values_list('pk', flat=True))
        elif isinstance(self, PromptString):
            # PromptString can be owned by a user or an agent.
            if self.owner_id:
                target_user_pks.add(self.owner_id)
            if hasattr(self, 'agent') and self.agent: # If associated with an agent, broadcast to its owners
                target_user_pks.update(self.agent.owners.values_list('pk', flat=True))
        elif isinstance(self, (AiModel, ApiKey, System, ApiProvider, ToolInstance, ToolDefinition, ToolInstallation)):
            # Global objects are broadcast to all users
            target_user_pks.update(User.objects.values_list('pk', flat=True))
        else:
            # Fallback for dictionaries that might specify scope
            if 'agentInstance_id' in base_message_data and base_message_data['agentInstance_id']:
                target_instance_pks.add(base_message_data['agentInstance_id'])
            elif 'user_pk' in base_message_data and base_message_data['user_pk']:
                target_user_pks.add(base_message_data['user_pk'])
            else:
                print(f'Warning: send_object_to_clients received unhandled object type: {type(self)} with no clear target.')
                return

        # Dispatch messages via Celery
        for instance_pk_target in target_instance_pks:
            # Create a copy and add target_instance_id before sending
            dispatch_message_data = dict(base_message_data)
            dispatch_message_data['target_instance_id'] = instance_pk_target
            celery_send_websocket_update.delay(dispatch_message_data, instance_pk=instance_pk_target)

        for user_pk_target in target_user_pks:
            dispatch_message_data = dict(base_message_data)
            # When dispatching to a user, we don't necessarily have a specific instance_id in mind for the UI context
            # So, we won't add target_instance_id to user-level broadcasts unless explicitly requested.
            #dispatch_message_data['target_instance_id'] = instance_pk_target
            celery_send_websocket_update.delay(dispatch_message_data, user_pk=user_pk_target)

    class Meta:
        abstract = True
