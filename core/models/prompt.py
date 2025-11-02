from django.db import models
from core.models.base_model import BaseModel
import random

from core.models.prompt_variant import PromptVariant
from django.contrib.auth.models import User
from core.models.prompt_relation import AgentPromptRelation

class Prompt(BaseModel):
    """
    Represents the abstract concept of a prompt, identified by a source and key.
    For example, source='agents', key='System'. This model does not hold the content.
    """
    source = models.CharField(max_length=200)
    key = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='', help_text="A description of what this prompt is for.")
    data_lambda = models.TextField(blank=True, default='', help_text="A lambda function that return the data to render")
    owner = models.ForeignKey(User, related_name='owned_prompts', default=None, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        #unique_together = ('source', 'key')
        ordering = ['source', 'key']

    def __str__(self):
        return f"{self.source} / {self.key}"

    def as_client_dict(self):
        return {
            'object': 'Prompt',
            'id': self.pk,
            'owner_id': self.owner_id,
            'source': self.source,
            'key': self.key,
            'description': self.description,
            'data_lambda': self.data_lambda,
            'nr_of_variants': self.variants.filter(next_version=None).count(),  
        }

    @staticmethod
    def get_or_create_template(owner, source, key, value, agent=None):
        try:
            return Prompt.get_template(agentInstance=None, source=source, key=key)
        except:
            pass

        p, _ = Prompt.objects.get_or_create(source=source, key=key)
        current_version, created = PromptVariant.objects.get_or_create(
            prompt_id = p.pk,
            owner_id =  owner.pk if owner else None,
            agent_id= agent.pk if agent else None,
            next_version=None
        )
        if created:
            current_version.value = value
            current_version.save()
        elif value != current_version.value:
            new_version = PromptVariant.objects.create(
                prompt_id = p.pk,
                owner_id =  owner.pk if owner else None,
                agent_id= agent.pk if agent else None,
                value=value
            )
            current_version.next_version=new_version
            current_version.save()
            return new_version

        return current_version

    @staticmethod
    def get_template(agentInstance, source, key):
        try:
            prompt = Prompt.objects.get(source=source, key=key)
            print(prompt)
            # 1. Look for an active, agent-specific variant for the current user
            if agentInstance.agent.owners.exists():
                user_owner = agentInstance.agent.owners.first() # Assuming one owner for simplicity
                agent_variants = PromptVariant.objects.filter(
                    prompt=prompt,
                    agent=agentInstance.agent,
                    owner=user_owner,
                    is_enabled=True,
                    next_version__isnull=True
                )
                if agent_variants:
                    return random.choice(list(agent_variants))

            # 1. Look for an active, global variant for the current user
            if agentInstance.agent.owners.exists():
                user_owner = agentInstance.agent.owners.first() # Assuming one owner for simplicity
                agent_variants = PromptVariant.objects.filter(
                    prompt=prompt,
                    agent__isnull=True,
                    owner=user_owner,
                    is_enabled=True,
                    next_version__isnull=True
                )
                if agent_variants:
                    return random.choice(list(agent_variants))

            # 2. Fallback to global, system-owned, active variant
            system_variants = PromptVariant.objects.filter(
                prompt=prompt,
                agent__isnull=True,
                owner__isnull=True, # System prompts
                is_enabled=True,
                next_version__isnull=True
            )
            
            if system_variants:
                return random.choice(list(system_variants))
            
            raise PromptVariant.DoesNotExist(f"No active variant found for prompt '{source}/{key}'")
        except Prompt.DoesNotExist:
            raise Prompt.DoesNotExist(f"Prompt with source='{source}' and key='{key}' does not exist.")


