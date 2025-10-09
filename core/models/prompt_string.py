from django.db import models
from django.contrib.auth.models import User

from core.models.base_model import BaseModel

class PromptStringManager(models.Manager):
    def get_or_create(self, **kwargs):
        owner = kwargs.get('owner', kwargs.get("defaults",{}).get("owner"))
        source = kwargs.get('source', kwargs.get("defaults",{}).get("source"))
        key = kwargs.get('key', kwargs.get("defaults",{}).get("key"))
        value = kwargs.get('value', kwargs.get("defaults",{}).get("value"))

        # Try to find the latest version of an existing prompt
        try:
            latest_prompt = self.filter(owner=owner, source=source, key=key, next_version__isnull=True).order_by("-pk").first()
            if not latest_prompt or latest_prompt.value != value:
                new_prompt = self.create(
                    owner=owner,
                    source=source,
                    key=key,
                    value=value,
                    **{k: v for k, v in kwargs.items() if k not in ['owner','source','key','value', 'defaults']} # Apply other defaults
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

class PromptString(BaseModel):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(User, related_name='owned_templates', default=None, null=True, on_delete=models.SET_DEFAULT)
    source = models.CharField(max_length=200, default='')
    key = models.CharField(max_length=200, default='')
    value = models.TextField(max_length=1 * 1024 * 1024, default='')
    next_version = models.OneToOneField('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='prev_version')
    
    objects = PromptStringManager()

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
            'system_parent_id': self.system_parent_pk,
            'prev_version_id':  self.prev_version.pk if hasattr(self, "prev_version") else None
        }
    
    @property
    def system_parent_pk(self):
        system_prompt =  PromptString.objects.filter(owner=None, source=self.source, key=self.key, next_version__isnull=True).order_by("-pk").first()
        return system_prompt.pk if system_prompt else None

    @staticmethod
    def get_template(agentInstance, source, key):
        return PromptString.objects.filter(owner=None, source=source, key=key, next_version=None).order_by("-pk").first()
