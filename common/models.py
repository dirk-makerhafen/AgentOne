from dirtyfields import DirtyFieldsMixin
from dirtyfields.dirtyfields import reset_state
from django.db import models
import json
from django.utils import timezone
from django.contrib.auth.models import User


class PromptStringManager(models.Manager):
    def get_or_create(self, **kwargs):
        owner = kwargs.get('owner', None)
        source = kwargs.get('source')
        key = kwargs.get('key')
        value = kwargs.get('value')

        # Try to find the latest version of an existing prompt
        try:
            latest_prompt = self.filter(owner=owner, source=source, key=key, next_version__isnull=True).order_by("-pk").first()
            if not latest_prompt or latest_prompt.value != value:
                new_prompt = self.create(
                    owner=owner,
                    source=source,
                    key=key,
                    value=value,
                    **{k: v for k, v in kwargs.items() if k not in ['owner','source','key','value']} # Apply other defaults
                )
                if latest_prompt:
                    latest_prompt.next_version = new_prompt
                    latest_prompt.save() 
                
                return new_prompt, True
            else:
                # Value is the same, return the existing latest prompt
                return latest_prompt, False # False because no new object was explicitly created, it was 'gotten'

        except self.model.DoesNotExist:
            return super().get_or_create(**kwargs)


class PromptString(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(User, related_name='owned_templates', default=None, null=True, on_delete=models.SET_DEFAULT)  # system templates have owner None
    source = models.CharField(max_length=200, default='')
    key = models.CharField(max_length=200, default='')
    value = models.TextField(max_length=1 * 1024 * 1024, default=b'')
    next_version = models.OneToOneField('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='prev_version', help_text="Points to the next version in the prompt's history. Null for the latest version.")

    objects = PromptStringManager() # Assign the custom manager

    class Meta():
        pass  # The unique_together = ["owner", "key", "value"]

    def save(self, send_to_client=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if send_to_client:
            from dashboard.tasks import send_object_to_clients
            send_object_to_clients(self)

    def as_client_dict(self):
        return {
            'object': 'PromptString', 
            'id': self.pk, 
            'owner_id': self.owner_id,
            'owner_username': self.owner.username if self.owner else "System",
            'created_at': self.created_at.isoformat(), 
            'source': self.source, 
            'key': self.key, 
            'value': self.value, 
            'is_deleteable': self.owner != None,
            'is_editable':  self.owner != None,
            'is_newest_version': self.next_version is None,
        }
    @staticmethod
    def get_template(agentInstance, source, key):
        # get system template where owner is None
        #t = PromptString.objects.filter(owner=agentInstance.owner, source=source, key=key,next_version=None).order_by("-pk").first()
        return PromptString.objects.filter(owner=None, source=source, key=key,next_version=None).order_by("-pk").first()




class ModelWithJsonData(DirtyFieldsMixin, models.Model):
    created_at = models.DateTimeField(db_index=True, editable=False)
    updated_at = models.DateTimeField(editable=False)
    raw_data = models.TextField(max_length=100 * 1024 * 1024, default=b'')

    @property
    def data(self):
        if not hasattr(self, '_data') or self._data is None:
            try:
                self._data = json.loads(self.raw_data) if len(self.raw_data) > 0 else {}
            except Exception as e:
                self._data = {'__error': f'Failed to load data for {self}: {e}'}
        return self._data

    @data.setter
    def data(self, data):
        self._data = data

    def save(self, *args, **kwargs):
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
        if self.pk is not None and 'update_fields' not in kwargs:
            fields_to_update = list(_dirty_fields.keys())
            if 'updated_at' not in fields_to_update:
                fields_to_update.append('updated_at')
            if 'raw_data' not in fields_to_update and 'raw_data' in _dirty_fields:
                fields_to_update.append('raw_data')
            if fields_to_update:
                kwargs['update_fields'] = fields_to_update
        elif self.pk is not None and 'update_fields' in kwargs:
            if 'updated_at' not in kwargs['update_fields']:
                kwargs['update_fields'].append('updated_at')
            if 'raw_data' in _dirty_fields and 'raw_data' not in kwargs['update_fields']:
                kwargs['update_fields'].append('raw_data')
        r = super().save(*args, **kwargs)
        reset_state(sender=self.__class__, instance=self, update_fields=kwargs.get("update_fields",[]))
        return r

    class Meta:
        abstract = True