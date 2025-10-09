from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from celery import chain

from agents.models.agent_instance import AgentInstance
from tools.definitions.models.tool_definition import ToolDefinition
from tools.definitions.models.tool_installation import ToolInstallation
from tools.definitions.tasks.install_tool import install_tool
from tools.definitions.tasks.uninstall_tool import uninstall_tool
from tools.instances.tasks.start_tool import start_tool

@receiver(post_save, sender=AgentInstance)
def manage_dedicated_tools_on_creation(sender, instance, created, **kwargs):
    """
    When a new AgentInstance is created, find all 'dedicated' tools assigned to its
    parent Agent and automatically install and start them.
    """
    
    if created:
        agent = instance.agent
        # We assume the agent instance runs on the same system it is configured for.
        # This might need to be more sophisticated if an instance can be scheduled on different systems.
        system = instance.system
        if not system:
            print(f"Warning: AgentInstance {instance.pk} was created without a System. Cannot manage dedicated tools.")
            return
        
        dedicated_tools = agent.available_tools.filter(execution_mode=ToolDefinition.ExecutionMode.DEDICATED)
        
        for tool_def in dedicated_tools:
            # Get or create the installation record, linking it to this specific agent instance.
            installation, created_installation = ToolInstallation.objects.get_or_create(
                tool_definition=tool_def,
                system=system,
                agent_instance=instance,
                defaults={'status': ToolInstallation.Status.INSTALLING}
            )

            if created_installation:
                print(f"Creating dedicated ToolInstallation for Tool '{tool_def.name}' on System '{system.name}' for AgentInstance '{instance.pk}'.")
                # Create a chain of tasks: install -> start
                workflow = chain(
                    install_tool.s(installation.pk),
                    start_tool.s(installation.pk)
                )
                workflow.delay()
            else:
                print(f"Dedicated ToolInstallation for Tool '{tool_def.name}' already exists for AgentInstance '{instance.pk}'. Ensuring it is started.")
                # If it exists but isn't running, start it.
                # This handles cases where a previous start might have failed.
                is_running = installation.instances.filter(status__in=['running', 'starting']).exists()
                if not is_running:
                    start_tool.delay(installation.pk)


@receiver(pre_delete, sender=AgentInstance)
def cleanup_dedicated_tools_on_deletion(sender, instance, **kwargs):
    """
    Before an AgentInstance is deleted, find all ToolInstallations dedicated to it
    and trigger their uninstallation.
    """
    dedicated_installations = ToolInstallation.objects.filter(agent_instance=instance)
    
    for installation in dedicated_installations:
        print(f"Queueing uninstallation for dedicated Tool '{installation.tool_definition.name}' for deleting AgentInstance '{instance.pk}'.")
        uninstall_tool.delay(installation.pk)
