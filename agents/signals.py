from django.db.models.signals import post_init
from django.dispatch import receiver
from .models.agent import AgentInstance

@receiver(post_init, sender=AgentInstance)
def agent_instance_post_init(sender, instance, **kwargs):
    """
    Signal handler to set up tools for an AgentInstance after it has been initialized from the database.
    This ensures that the `tool_instances` and `toolname_to_definition` are populated.
    """
    instance._setup_tools() # Always setup tools; _setup_tools handles cases where agent/system might be null.
