import json
from django.contrib.auth.models import User
import traceback

from agents.models.agent import Agent
from providers.models.ai_model import AiModel
from systems.models.system import System
from tools.definitions.models.tool_definition import ToolDefinition
from ui.router import register_handler

@register_handler('agent_create')
def handle_agent_create(consumer, user_pk, payload):
    try:
        user = User.objects.get(pk=user_pk)
    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {user_pk} not found when trying to create agent.'}))
        return

    try:
        agent_name = payload.get('name', 'New Agent')
        description = payload.get('description', '')
        available_tool_ids = payload.get('available_tool_ids', [])

        new_agent = Agent()
        new_agent.name = agent_name
        new_agent.description = description
        new_agent.save(send_to_client=False)

        new_agent.owners.add(user)
        
        if available_tool_ids:
            tools = ToolDefinition.objects.filter(pk__in=available_tool_ids)
            new_agent.available_tools.set(tools)

        new_agent.save(send_to_client=True)
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to create agent: {e}'}))

@register_handler('agent_update')
def handle_agent_update(consumer, user_pk, payload):
    agent_pk = payload.get('agent_pk')
    if not agent_pk:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'agent_pk is required for update.'}))
        return

    try:
        user = User.objects.get(pk=user_pk)
        agent = Agent.objects.get(pk=agent_pk, owners=user)

        agent.name = payload.get('name', agent.name)
        agent.description = payload.get('description', agent.description)

        available_tool_ids = payload.get('available_tool_ids')
        if available_tool_ids is not None:
            tools = ToolDefinition.objects.filter(pk__in=available_tool_ids)
            agent.available_tools.set(tools)
        agent.save()

    except Agent.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Agent with pk {agent_pk} not found or permission denied.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to update agent: {e}{traceback.format_exc()}'}))
 
@register_handler('agent_delete')
def handle_agent_delete(consumer, user_pk, payload):
    agent_pk = payload.get('agent_pk')
    if not agent_pk:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'agent_pk is required.'}))
        return

    try:
        user = User.objects.get(pk=user_pk)
        agent = Agent.objects.get(pk=agent_pk, owners=user)
        # The delete signal handler will send the websocket message
        agent.delete()
    except Agent.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Agent with pk {agent_pk} not found or permission denied.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'An error occurred: {e}'}))

@register_handler('agent_list')
def handle_agent_list(consumer, user_pk, payload):
    try:
        user = User.objects.get(pk=user_pk)
    except User.DoesNotExist:
        error_message = f'User with pk {user_pk} not found.'
        consumer.send(text_data=json.dumps({'object': 'error', 'message': error_message}))
        return
    
    agents = user.owned_agents.all().order_by('-updated_at')
    agent_list = [agent.as_client_dict() for agent in agents]
    
    instance_list = []
    for agent in agents:
        for instance in agent.instances.all().order_by('-updated_at'):
            instance_list.append(instance.as_client_dict())

    consumer.send(text_data=json.dumps({'object': 'AgentList', 'agents': agent_list}))
    consumer.send(text_data=json.dumps({'object': 'AgentInstanceList', 'instances': instance_list}))
    
    models = AiModel.objects.all().order_by('name')
    model_list = [{'id': model.pk, 'name': model.name} for model in models]
    consumer.send(text_data=json.dumps({'object': 'ModelList', 'models': model_list}))
    
    systems = System.objects.all().order_by('name')
    system_list = [system.as_client_dict() for system in systems]
    consumer.send(text_data=json.dumps({'object': 'SystemList', 'systems': system_list}))
