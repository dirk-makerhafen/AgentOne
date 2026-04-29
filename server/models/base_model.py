from server.models.content import GenericContent
from dirtyfields import DirtyFieldsMixin
from dirtyfields.dirtyfields import reset_state
from django.db import models
import json
from django.utils import timezone
import traceback
from django.apps import apps


class BaseModel(DirtyFieldsMixin, models.Model):
    created_at = models.DateTimeField(db_index=True, editable=False, auto_now_add=True)
    updated_at = models.DateTimeField(editable=False, auto_now=True)
    raw_data = models.TextField(max_length=100 * 1024 * 1024, default='', blank=True)

    # Forking and Data Deduplication fields
    fork_of = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, default=None, related_name='forks')
    raw_data_reference = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, default=None, related_name='data_references')

    class Meta:
        abstract = True

    @property
    def data(self):
        if not hasattr(self, '_data') or self._data is None:
            source_raw_data = self.raw_data
            if self.raw_data_reference:
                source_raw_data = self.raw_data_reference.raw_data
            try:
                self._data = json.loads(source_raw_data) if source_raw_data else {}
            except Exception as e:
                self._data = {'__error': f'Failed to load data for {self}: {e} {traceback.format_exc()}'}
        return self._data

    @data.setter
    def data(self, new_data):
        # This is the copy-on-write logic. Setting new data breaks the reference.
        if self.raw_data_reference is not None:
            self.raw_data_reference = None
        self._data = new_data
    
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
        return r

