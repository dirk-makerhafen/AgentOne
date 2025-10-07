from celery import shared_task
import traceback

@shared_task
def celery_trigger_tool_lifecycle_task(agentinstance_pk):

    from agents.models.agent_instance import AgentInstance
    from tools.definitions.models.tool_installation import ToolInstallation
    from tools.definitions.tasks import install_tool
    from tools.instances.tasks import start_tool
    from tools.instances.tasks.tool_status import get_tool_status

    try:
        agent_instance = AgentInstance.objects.get(instance_pk=agentinstance_pk)
        if not agent_instance.agent or not agent_instance.system:
            print(f"AgentInstance {agent_instance.pk} has no agent or system assigned. Skipping tool lifecycle trigger.")
            return

        # Iterate through tools available to the Agent (defined on the Agent aimodel)
        for tool_def in agent_instance.agent.available_tools.filter(is_builtin=False):
            # Check for existing installation on the assigned system
            installation, created = ToolInstallation.objects.get_or_create(
                tool_definition=tool_def,
                system=agent_instance.system,
                defaults={'status': ToolInstallation.Status.NOT_INSTALLED}
            )

            current_status = get_tool_status.delay(installation) # Get real-time status from system
            if current_status != ToolInstallation.Status.RUNNING: # If not running, attempt to install/start
                print(f"Tool '{tool_def.name}' is not running (current status: {current_status}) on system '{agent_instance.system.name}'. Triggering lifecycle action.")
                if current_status == ToolInstallation.Status.NOT_INSTALLED:
                    install_tool.delay(installation.pk)
                elif current_status == ToolInstallation.Status.STOPPED or current_status == ToolInstallation.Status.ERROR or current_status == ToolInstallation.Status.INSTALLED:
                    start_tool.delay(installation.pk)
            else:
                print(f"Tool '{tool_def.name}' is already {current_status} on system '{agent_instance.system.name}'.")


    except AgentInstance.DoesNotExist:
        print(f"AgentInstance with pk {agentinstance_pk} not found for tool lifecycle trigger.")
    except Exception as e:
        print(f"Error in celery_trigger_tool_lifecycle_task for AgentInstance {agentinstance_pk}: {e}")
        traceback.print_exc()


