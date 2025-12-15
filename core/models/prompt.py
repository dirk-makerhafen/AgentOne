from django.db import models
from core.models.base_model import BaseModel
import random

from core.models.prompt_variant import PromptVariant
from django.contrib.auth.models import User
from core.models.prompt_relation import AgentPromptRelation
from django.db.models import Q

class Prompt(BaseModel):
    """
    Represents the abstract concept of a prompt, identified by a source and key.
    For example, source='agents', key='System'. This model does not hold the content.
    """
    source = models.CharField(max_length=200)
    key = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='', help_text="A description of what this prompt is for.")
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
            'data_lambda': "TODO",
            'nr_of_variants': self.variants.filter(next_version=None).count(),  
        }

    @staticmethod
    def get_or_create_template(owner, source, key, value, agent=None, agentInstance=None, data_lambda=""):
        print("get_or_create_template",  source, key)
        p, _ = Prompt.objects.get_or_create(source=source, key=key)
       
        f=list(PromptVariant.objects.all())
        print("PromptVariant", f)

        current_version, created = PromptVariant.objects.get_or_create(
            prompt_id = p.pk,
            owner_id =  owner.pk if owner else None,
            agent= agent if agent else None,
            agentInstance_id= agentInstance.pk if agentInstance else None,
            next_version=None,
        )
        if created:
            current_version.value = value
            current_version.data_lambda=data_lambda
            current_version.save()
        elif value != current_version.value or current_version.data_lambda != data_lambda:
            new_version = PromptVariant.objects.create(
                prompt_id = p.pk,
                owner_id =  owner.pk if owner else None,
                agent_id = agent.pk if agent else None,
                agentInstance_id = agentInstance.pk if agentInstance else None,
                value = value,
                data_lambda = data_lambda,
            )
            current_version.next_version=new_version
            current_version.save()
            return new_version

        return current_version

    @staticmethod
    def get_template(source, key, agent = None, agentInstance=None, owner=None):
        try:
            prompt = Prompt.objects.get(source=source, key=key)
            
            # 1. Look for agentInstance specific variant  for the current user
            if agentInstance:
                user_owner = agentInstance.agent.owners.first() # Assuming one owner for simplicity
                agentInstance_variants = PromptVariant.objects.filter(
                    prompt=prompt,
                    agent__isnull=True,
                    agentInstance=agentInstance,
                    owner=user_owner,
                    is_enabled=True,
                    next_version__isnull=True
                )
                if agentInstance_variants:
                    return random.choice(list(agentInstance_variants))
                
            # 2. Look for agent specific variant  for the current user 
            if agent:
                user_owner = agent.owners.first() # Assuming one owner for simplicity
                agent_variants = PromptVariant.objects.filter(
                    prompt=prompt,
                    agent=agent,
                    agentInstance__isnull=True,
                    owner=user_owner,
                    is_enabled=True,
                    next_version__isnull=True
                )
                if agent_variants:
                    return random.choice(list(agent_variants))

            # 3. Look for variant for the user 
            if owner:
                owner_variants = PromptVariant.objects.filter(
                    prompt=prompt,
                    agent__isnull=True,
                    agentInstance__isnull=True,
                    owner=owner,
                    is_enabled=True,
                    next_version__isnull=True
                )
                if owner_variants:
                    return random.choice(list(owner_variants))

            # 4. Look for global variant of none user
            system_variants = PromptVariant.objects.filter(
                prompt=prompt,
                agent__isnull=True,
                agentInstance__isnull=True,
                owner__isnull=True, # System prompts
                is_enabled=True,
                next_version__isnull=True
            )
            if system_variants:
                return random.choice(list(system_variants))
            
            raise PromptVariant.DoesNotExist(f"No active variant found for prompt '{source}/{key}  Agent:{agent}  Instance:{agentInstance}'")
        except Prompt.DoesNotExist:
            raise Prompt.DoesNotExist(f"Prompt with source='{source}' and key='{key}' does not exist.")


