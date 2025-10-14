from django.db.models.signals import post_save
from django.dispatch import receiver
from .models.tool_instance import ToolInstance
from tools.instances.tasks.tool_fetch_details import fetch_mcp_tool_details

@receiver(post_save, sender=ToolInstance)
def trigger_mcp_details_fetch(sender, instance, created, **kwargs):
    if instance.status != ToolInstance.ToolInstanceStatusChoices.RUNNING:
        return
    if instance.data:
        return
    tool_definition = instance.tool_installation.tool_definition
    if tool_definition.is_builtin:
        return
    fetch_mcp_tool_details.delay(instance.pk)
