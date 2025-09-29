import json
from django.contrib.auth.models import User
from agent.models.agent import Agent
from asgiref.sync import async_to_sync
import json
from agent.models.agent import Agent
from django.contrib.auth.models import User
import json
from django.contrib.auth.models import User
from providers.models import Model
from systems.models import System


def handle_agent_create(consumer, user_pk, payload):
    try:
        user = User.objects.get(pk=user_pk)
    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {user_pk} not found when trying to create agent.'}))
        return

    try:
        agent_name = payload.get('name', 'New Agent')
        new_agent = Agent()
        new_agent.name = agent_name
        new_agent.save(send_to_client=False)
        new_agent.owners.add(user)
        new_agent.save(send_to_client=True)
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to create agent: {e}'}))


def handle_agent_delete(consumer, user_pk, payload):
    agent_pk = payload.get('agent_pk')
    if not agent_pk:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'agent_pk is required.'}))
        return

    try:
        user = User.objects.get(pk=user_pk)
        agent = Agent.objects.get(pk=agent_pk, owners=user)
        deleted_agent_pk = agent.pk
        agent.delete()
        async_to_sync(consumer.channel_layer.group_send)(
            consumer.group_name,
            {
                'type': 'agent_message',
                'payload': {
                    'object': 'AgentDeleted',
                    'agent_pk': deleted_agent_pk
                }
            }
        )
    except Agent.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Agent with pk {agent_pk} not found or permission denied.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'An error occurred: {e}'}))


def handle_agent_list(consumer, user_pk):
    try:
        user = User.objects.get(pk=user_pk)
    except User.DoesNotExist:
        error_message = f'User with pk {user_pk} not found.'
        print(f'Error: {error_message}', flush=True)
        consumer.send(text_data=json.dumps({'object': 'error', 'message': error_message}))
        return
    agents = user.owned_agents.all().order_by('-updated_at')
    agent_list = []
    instance_list = []
    for agent in agents:
        agent_list.append(agent.as_client_dict())
        for instance in agent.instances.all().order_by('-updated_at'):
            instance_list.append(instance.as_client_dict())
    consumer.send(text_data=json.dumps({'object': 'AgentList', 'agents': agent_list}))
    consumer.send(text_data=json.dumps({'object': 'AgentInstanceList', 'instances': instance_list}))
    models = Model.objects.all().order_by('name')
    model_list = [{'id': model.pk, 'name': model.name} for model in models]
    consumer.send(text_data=json.dumps({'object': 'ModelList', 'models': model_list}))
    systems = System.objects.all().order_by('name')
    system_list = [system.as_client_dict() for system in systems]
    consumer.send(text_data=json.dumps({'object': 'SystemList', 'systems': system_list}))

