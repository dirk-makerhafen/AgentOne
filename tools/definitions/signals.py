from django.db.models.signals import post_save, pre_delete, m2m_changed
from django.dispatch import receiver
from celery import chain

from core.logging import log_to_clients
from systems.models.system import System
from tools.definitions.models.tool_definition import ToolDefinition
from tools.definitions.models.tool_installation import ToolInstallation
from tools.definitions.tasks.install_tool import install_tool
from tools.definitions.tasks.uninstall_tool import uninstall_tool
from tools.instances.tasks.start_tool import start_tool

@receiver(post_save, sender=ToolDefinition)
def handle_tool_definition_update(sender, instance, created, **kwargs):
    if created:
        return

    if instance.status != ToolDefinition.ToolDefinitionStatusChoices.UPDATING:
        return

    log_to_clients(f"LIFECYCLE: ToolDefinition '{instance.name}' updated. Triggering re-installation for all existing installations.", level='info')
    all_installations = ToolInstallation.objects.filter(tool_definition=instance)

    for installation in all_installations:
        log_to_clients(f"  - Queueing update for installation {installation.pk} on system {installation.system.name}.", level='info')
        workflow = chain(
            uninstall_tool.s(tool_installation_id=installation.pk, delete_record=False),
            install_tool.s(tool_installation_id=installation.pk),
            start_tool.s(tool_installation_id=installation.pk)
        )
        workflow.delay()

@receiver(pre_delete, sender=ToolDefinition)
def handle_tool_definition_deletion(sender, instance, **kwargs):
    log_to_clients(f"LIFECYCLE: ToolDefinition '{instance.name}' is being deleted. Uninstalling all associated installations.", level='info')
    installations_to_remove = ToolInstallation.objects.filter(tool_definition=instance)
    for installation in installations_to_remove:
        log_to_clients(f"  - Queueing uninstallation for Installation PK: {installation.pk} due to ToolDefinition deletion.", level='info')
        uninstall_tool.delay(installation.pk)

@receiver(m2m_changed, sender=ToolDefinition.available_on_systems.through)
def handle_system_assignment_change(sender, instance, action, reverse, model, pk_set, **kwargs):
    if not isinstance(instance, ToolDefinition):
        return

    if instance.execution_mode != ToolDefinition.ExecutionMode.SHARED:
        return

    if action == "post_add":
        log_to_clients(f"LIFECYCLE: ToolDefinition '{instance.name}' added to systems. PKs: {pk_set}. Triggering installations.", level='info')
        for system_pk in pk_set:
            if not ToolInstallation.objects.filter(
                tool_definition=instance, system_id=system_pk, agent_instance__isnull=True
            ).exists():
                system = System.objects.get(pk=system_pk)
                log_to_clients(f"  - Creating new shared ToolInstallation for Tool '{instance.name}' on System '{system.name}'.", level='info')
                new_installation = ToolInstallation.objects.create(
                    tool_definition=instance, system_id=system_pk, status=ToolInstallation.ToolInstallationStatusChoices.INSTALLING
                )
                install_tool.delay(new_installation.pk)

    elif action == "post_remove":
        log_to_clients(f"LIFECYCLE: ToolDefinition '{instance.name}' removed from systems. PKs: {pk_set}. Triggering uninstallations.", level='info')
        for system_pk in pk_set:
            installations_to_remove = ToolInstallation.objects.filter(
                tool_definition=instance, system_id=system_pk, agent_instance__isnull=True
            )
            system = System.objects.get(pk=system_pk)
            for installation in installations_to_remove:
                log_to_clients(f"  - Queueing uninstallation for shared Tool '{instance.name}' (Installation PK: {installation.pk}) on System '{system.name}'.", level='info')
                uninstall_tool.delay(installation.pk)
