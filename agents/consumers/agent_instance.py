import json
from agents.models.agent import Agent
from agents.models.agent_instance import AgentInstance
from agents.tasks.clone_agentinstance import celery_clone_agentinstance
from tools.builtin_python.models.python_tool_var import PythonToolVar
from providers.models.ai_model import AiModel
from systems.models.system import System
from ui.router import register_handler
import traceback

@register_handler('agentinstance_create')
def handle_agentinstance_create(consumer, agent_pk):
    try:
        agent = Agent.objects.get(pk=agent_pk)
        new_instance = AgentInstance()
        new_instance.agent = agent
        new_instance.name = f'New Instance for {agent.name}'

        new_instance.save()
    except Agent.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Agent with pk {agent_pk} not found.'}))

@register_handler('agentinstance_get')
def handle_agentinstance_get(consumer, instance_pk):
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=instance_pk)
        agent_instance.send_object_to_clients()
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {instance_pk} not found.'}))

@register_handler('agentinstance_get_vars')
def handle_agentinstance_get_vars(consumer, instance_pk):
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=instance_pk)
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {instance_pk} not found.'}))
        return
    latest_vars = PythonToolVar.objects.filter(agentInstance=agent_instance, next_version=None).order_by('key')
    vars_items = [item.as_client_dict() for item in latest_vars]
    consumer.send(text_data=json.dumps({'object': 'InitialVarsState', 'items': vars_items, 'agentInstance_id': agent_instance.instance_pk}))

@register_handler('agentinstance_update')
def handle_agentinstance_update(consumer, instance_pk, data=None):
    if data is None:
        data = {}
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=instance_pk)
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {instance_pk} not found.'}))
        return

    if 'name' in data:
        agent_instance.name = data['name']
    if 'description_text' in data:
        agent_instance.description_text = data['description_text']
    if 'workingdir' in data:
        agent_instance.workingdir = data['workingdir']
    if 'description' in data:
        agent_instance.description = data['description']
    if 'limit_max_conversation_messages' in data:
        agent_instance.limit_max_conversation_messages = int(data['limit_max_conversation_messages'])
    if 'limit_max_memory_items' in data:
        agent_instance.limit_max_memory_items = int(data['limit_max_memory_items'])
    if 'limit_max_automated_steps' in data:
        agent_instance.limit_max_automated_steps = int(data['limit_max_automated_steps'])
    if 'workingdir_write_allowed' in data:
        agent_instance.workingdir_write_allowed = bool(data['workingdir_write_allowed'])
    if 'access_rules' in data:
        agent_instance.access_rules = data['access_rules']
    if 'model_id' in data:
        try:
            model_id = int(data['model_id'])
            new_model = AiModel.objects.get(pk=model_id)
            agent_instance.aimodel = new_model
        except Exception as e:
            consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Model with pk {data["model_id"]} not found.'}))
            return
    if 'system_id' in data:
        try:
            system_id = int(data['system_id'])
            if system_id:
                agent_instance.system = System.objects.get(pk=system_id)
            else:
                agent_instance.system = None
        except Exception as e:
            consumer.send(text_data=json.dumps({'object': 'error', 'message': f'System with pk {data["system_id"]} not found.'}))
            return
    agent_instance.save()

@register_handler('agentinstance_delete')
def handle_agentinstance_delete(consumer, instance_pk):
    if not instance_pk:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': "Agent instance PK not provided for deletion." }))
        return

    try:
        instance = AgentInstance.objects.get(instance_pk=instance_pk)
        instance.delete()
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f"Agent instance with PK {instance_pk} not found."}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f"Error deleting agent instance {instance_pk}: {str(e)} {traceback.format_exc()}"}))

@register_handler('agentinstance_fork')
def handle_agentinstance_fork(consumer, instance_pk):
    try:
        celery_clone_agentinstance.delay(instance_pk)
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {instance_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to fork agent instance: {e} {traceback.format_exc()}'}))
