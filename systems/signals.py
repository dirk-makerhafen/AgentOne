from django.db.models.signals import pre_delete
from django.dispatch import receiver

from core.logging import log_to_clients
from systems.models.system import System
from tools.definitions.tasks.uninstall_tool import uninstall_tool

@receiver(pre_delete, sender=System)
def handle_system_deletion(sender, instance, **kwargs):
    """
    When a System is deleted, trigger the uninstallation of all tool
    installations (both shared and dedicated) that reside on it.
    """
    log_to_clients(f"LIFECYCLE: System '{instance.name}' is being deleted. Uninstalling all associated tool installations.", level='info')
    
    installations_to_remove = instance.tool_installations.all()
    
    for installation in installations_to_remove:
        log_to_clients(f"  - Queueing uninstallation for Tool '{installation.tool_definition.name}' (Installation PK: {installation.pk}) from deleting system.", level='info')
        uninstall_tool.delay(installation.pk)
