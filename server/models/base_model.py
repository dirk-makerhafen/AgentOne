from server.models.content import GenericContent
from dirtyfields import DirtyFieldsMixin
from dirtyfields.dirtyfields import reset_state
from django.db import models
import json
from django.utils import timezone
import traceback
from django.apps import apps

def load_model_references(data, model_instances=None):
    if model_instances is None:
        model_instances = set()
    if isinstance(data, dict):
        if "_type" in data and "pk" in data:
            try:
                if data.get("_type") == "GenericContent":
                    mi = GenericContent.objects.get(pk=data["pk"])
                else:
                    mi = apps.get_model('server', data["_type"]).objects.get(pk=data["pk"])
                model_instances.add(mi)
            except:
                return data, model_instances   
            return mi, model_instances
        return {k: load_model_references(v, model_instances)[0] for k, v in data.items()}, model_instances
    elif isinstance(data, list):
        return [load_model_references(item, model_instances)[0] for item in data], model_instances
    return data, model_instances

def load_results_data(data, timeout=None):
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.tasks.agent_task_run import AgentTaskRun

    print("_load_results_data", data)
    if isinstance(data, dict):
        d = {k: load_results_data(v, timeout) for k, v in data.items()}
        print("return d", d)
        return d
    elif isinstance(data, list):
        l = [load_results_data(item, timeout) for item in data]
        print("reutnr l ,", l, data)
        return l
    elif isinstance(data, AgentTaskCall):
        r= data.results.get(timeout=0)
        r1, model_refs = load_model_references(r)
        r2 = load_results_data(r1, timeout)
        r3, model_refs = load_model_references(r2)
        print("return r2 r3", r2,r3, data)
        return r3
    elif isinstance(data, AgentTaskRun):
        r= data.result_json
        r1, model_refs = load_model_references(r)
        r2 = load_results_data(r1, timeout)
        r3, model_refs = load_model_references(r2)
        print("return r2 r3", r2, r3, data)
        return r3
    print("return ", data)
    return data


class BaseModel(DirtyFieldsMixin, models.Model):
    created_at = models.DateTimeField(db_index=True, editable=False)
    updated_at = models.DateTimeField(editable=False)
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

