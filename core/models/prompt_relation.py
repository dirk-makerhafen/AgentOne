from django.db import models
from core.models.base_model import BaseModel

class AgentPromptRelation(BaseModel):
    class AgentPromptRelationInsertAtChoices(models.TextChoices):
        TOP = 'TOP', 'Top most'
        POST_TOP = 'POST_TOP', 'Below Top most'
        PRE_CHAT = 'PRE_CHAT', 'Right before chat messages'
        POST_CHAT = 'POST_CHAT', 'Right after chat messages'

    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name ='agent_prompt_relations')
    prompt = models.ForeignKey("core.Prompt", on_delete=models.CASCADE, related_name ='agent_prompt_relations')
    role = models.CharField(max_length=32, default='user')
    insert_at = models.CharField(max_length=30, choices=AgentPromptRelationInsertAtChoices.choices, default=AgentPromptRelationInsertAtChoices.TOP)
    index = models.IntegerField(default=0, help_text="Ordering inside the insert_at point")

    def as_client_dict(self):
        return {
            'object': 'AgentPromptRelation', 
            "id": self.id,  
            "agent_id": self.agent_id,  
            "prompt_id": self.prompt_id, 
            "prompt_source": self.prompt.source,
            "prompt_key": self.prompt.key,
            'created_at': self.created_at.isoformat(), 
            'role': self.role,
            'insert_at': self.insert_at,
            'insert_at_display': self.get_insert_at_display(),
            'index': self.index,
        }