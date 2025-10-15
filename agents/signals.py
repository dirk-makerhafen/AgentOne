from django.db.models.signals import post_save, pre_delete, m2m_changed, pre_save
from django.dispatch import receiver
from celery import chain

from agents.models.agent import Agent
from agents.models.agent_instance import AgentInstance
from core.logging import log_to_clients
from systems.models.system import System
from tools.definitions.models.tool_definition import ToolDefinition
from tools.definitions.models.tool_installation import ToolInstallation
from tools.definitions.tasks.install_tool import install_tool
from tools.definitions.tasks.uninstall_tool import uninstall_tool
from tools.instances.models.tool_instance import ToolInstance
from tools.instances.tasks.start_tool import start_tool

@receiver(m2m_changed, sender=Agent.available_tools.through)
def handle_agent_tool_change(sender, instance, action, reverse, model, pk_set, **kwargs):
    if not isinstance(instance, Agent):
        return

    changed_tools = ToolDefinition.objects.filter(pk__in=pk_set)
    dedicated_tools = [tool for tool in changed_tools if tool.execution_mode == ToolDefinition.ExecutionMode.DEDICATED]
    if not dedicated_tools:
        return

    agent_owners = instance.owners.all()
    agent_instances = AgentInstance.objects.filter(agent=instance)

    for tool_def in dedicated_tools:
        if action == "post_add":
            log_to_clients(f"LIFECYCLE: Dedicated tool '{tool_def.name}' added to Agent '{instance.name}'. Installing on all instances.", users=agent_owners)
            for agent_instance in agent_instances:
                if not agent_instance.system:
                    continue
                installation, created = ToolInstallation.objects.get_or_create(
                    tool_definition=tool_def, system=agent_instance.system, agent_instance=agent_instance
                )
                if created:
                    log_to_clients(f"  - Creating and starting installation for instance {agent_instance.pk} on system {agent_instance.system.name}", level='info', users=agent_owners)
                    workflow = chain(install_tool.s(installation.pk), start_tool.s())
                    workflow.delay()
        elif action == "post_remove":
            log_to_clients(f"LIFECYCLE: Dedicated tool '{tool_def.name}' removed from Agent '{instance.name}'. Uninstalling from all instances.", level='info', users=agent_owners)
            for agent_instance in agent_instances:
                installations_to_remove = ToolInstallation.objects.filter(tool_definition=tool_def, agent_instance=agent_instance)
                for installation in installations_to_remove:
                    log_to_clients(f"  - Queueing uninstallation for instance {agent_instance.pk} (Installation PK: {installation.pk})", level='info', users=agent_owners)
                    uninstall_tool.delay(installation.pk)

@receiver(pre_save, sender=AgentInstance)
def store_old_system_on_instance(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = AgentInstance.objects.get(pk=instance.pk)
            instance._old_system_id = old_instance.system_id
        except AgentInstance.DoesNotExist:
            instance._old_system_id = None
    else:
        instance._old_system_id = None

@receiver(post_save, sender=AgentInstance)
def manage_dedicated_tools_on_save(sender, instance, created, **kwargs):
    agent_owners = instance.agent.owners.all()
    if created:
        agent = instance.agent
        system = instance.system
        if not system:
            log_to_clients(f"LIFECYCLE: AgentInstance {instance.pk} created without a System. Cannot manage dedicated tools.", level='warn', users=agent_owners)
            return
        
        dedicated_tools = agent.available_tools.filter(execution_mode=ToolDefinition.ExecutionMode.DEDICATED)
        for tool_def in dedicated_tools:
            installation, created_installation = ToolInstallation.objects.get_or_create(
                tool_definition=tool_def, system=system, agent_instance=instance,
                defaults={'status': ToolInstallation.ToolInstallationStatusChoices.INSTALLING}
            )
            if created_installation:
                log_to_clients(f"LIFECYCLE: Creating dedicated ToolInstallation for '{tool_def.name}' on System '{system.name}' for AgentInstance '{instance.pk}'.", level='info', users=agent_owners)
                workflow = chain(install_tool.s(installation.pk), start_tool.s(installation.pk))
                workflow.delay()
            else:
                is_running = installation.instances.filter(status__in=[ ToolInstance.ToolInstanceStatusChoices.RUNNING, ToolInstance.ToolInstanceStatusChoices.STARTING]).exists()
                if not is_running:
                    log_to_clients(f"LIFECYCLE: Dedicated ToolInstallation for '{tool_def.name}' already exists for AgentInstance '{instance.pk}'. Ensuring it is started.", level='info', users=agent_owners)
                    start_tool.delay(installation.pk)
    else:
        old_system_id = getattr(instance, '_old_system_id', None)
        new_system_id = instance.system_id
        if old_system_id != new_system_id:
            log_to_clients(f"LIFECYCLE: AgentInstance {instance.pk} system changed from {old_system_id} to {new_system_id}. Moving dedicated tools.", level='info', users=agent_owners)
            if old_system_id:
                old_installations = ToolInstallation.objects.filter(agent_instance=instance, system_id=old_system_id)
                for installation in old_installations:
                    log_to_clients(f"  - Queueing uninstall for installation {installation.pk} from old system {old_system_id}", level='info', users=agent_owners)
                    uninstall_tool.delay(installation.pk)
            if new_system_id:
                new_system = System.objects.get(pk=new_system_id)
                dedicated_tools = instance.agent.available_tools.filter(execution_mode=ToolDefinition.ExecutionMode.DEDICATED)
                for tool_def in dedicated_tools:
                    installation, created = ToolInstallation.objects.get_or_create(
                        tool_definition=tool_def, system=new_system, agent_instance=instance
                    )
                    log_to_clients(f"  - Queueing install and start for tool {tool_def.name} on new system {new_system_id}", level='info', users=agent_owners)
                    workflow = chain(install_tool.s(installation.pk), start_tool.s(installation.pk))
                    workflow.delay()

@receiver(pre_delete, sender=AgentInstance)
def cleanup_references(sender, instance, **kwargs):
    for fork in instance.forks_created.all():
        fork.delete()
    if hasattr(instance, "fork_origin"):
        instance.fork_origin.delete()
    agent_owners = instance.agent.owners.all()
    dedicated_installations = ToolInstallation.objects.filter(agent_instance=instance)
    for installation in dedicated_installations:
        log_to_clients(f"LIFECYCLE: Queueing uninstallation for dedicated Tool '{installation.tool_definition.name}' for deleting AgentInstance '{instance.pk}'.", level='info', users=agent_owners)
        uninstall_tool.delay(installation.pk)
