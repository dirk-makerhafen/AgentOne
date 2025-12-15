from importlib.machinery import SourceFileLoader
import inspect
from django.db import models
from django.contrib.auth.models import User

from core.models.base_model import BaseModel
from tools.definitions.models.tool_definition import ToolDefinition

'''
class MyAgent(AgentOne):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default='')
    defaults = {
        'available_tools'
        'aimodel'
        'limit_max_conversation_messages'
        'limit_max_new_conversation_messages'
        'limit_max_memory_items'
        'limit_max_automated_steps'
        'task_arguments_schema'
        'task_result_schema'
    }

    variants = [
        [{"aimodel": m } for m in models]
    ]


class AgentVariant():
    data = models.JSONField(default=dict, blank=True)
    pavariants = "ref to self"
    

class AgentSession():
    pass
'''


class Agent(BaseModel):
    agent_pk = models.AutoField(primary_key=True)
    owners = models.ManyToManyField(User, related_name='owned_agents', blank=True)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default='')
    aimodel = models.ForeignKey("providers.AiModel", default=None, on_delete=models.CASCADE, related_name='agents', null=True, blank=True)
    available_tools = models.ManyToManyField(ToolDefinition, blank=True, related_name='agents')

    # Default limits for instances of this agent
    limit_max_conversation_messages = models.IntegerField(default=20, null=True, blank=True, help_text="Default maximum number of messages in an agent's conversation history.")
    limit_max_new_conversation_messages = models.IntegerField(default=None, null=True, blank=True, help_text="Default maximum number of new messages in conversation history send in llm requests. If larger than limit_max_conversation_messages messages can be skipped")
    limit_max_memory_items = models.IntegerField(default=0, null=True, blank=True, help_text="Default maximum number of items in an agent's memory.")
    limit_max_automated_steps = models.IntegerField(default=0, null=True, blank=True, help_text="Default maximum number of automated steps an agent can take.")
    parent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, default=None, null=True, blank=True,related_name ='children')

    task_arguments_schema = models.JSONField(default=list, blank=True)
    task_result_schema = models.JSONField(default=dict, blank=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            super().save(*args, **kwargs)
            try:
                admin_user = User.objects.get(username='admin')
                self.owners.add(admin_user)
            except User.DoesNotExist:
                print("Warning: 'admin' user not found when saving YourAgentModel instance.")
                pass
            except Exception as e:
                print(f"An error occurred while adding admin user: {e}")
        else:
            # For existing objects, just perform a normal save
            super().save(*args, **kwargs)



    def __str__(self):
        return f'Agent: {self.name}'

    def as_client_dict(self):
        return {
            'object': 'Agent', 
            'id': self.agent_pk, 
            'created_at': self.created_at.isoformat(), 
            'updated_at': self.updated_at.isoformat(),
            'name': self.name, 
            'description': self.description,
            'available_tools':  [tool.pk for tool in self.available_tools.all()],
            'limit_max_conversation_messages': self.limit_max_conversation_messages,
            'limit_max_memory_items': self.limit_max_memory_items,
            'limit_max_automated_steps': self.limit_max_automated_steps,
        }
    
    def get_delete_broadcast_payload(self):
        return {
            'object': 'AgentDeleted',
            'agent_pk': self.agent_pk
        }

    def update_or_create_instance(self, instance_name, workingdir, system=None, parent_instance=None, **kwargs):
        from agents.models.agent_instance import AgentInstance
        defaults={
            "workingdir": workingdir, 
        }
        if system:
            defaults["system"] = system

        defaults.update(kwargs)
        instance, created = AgentInstance.objects.update_or_create(
            agent = self, 
            name = instance_name,
            parent = parent_instance,
            defaults = defaults)
        return instance
    