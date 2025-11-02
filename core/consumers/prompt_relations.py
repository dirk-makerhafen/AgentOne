from agents.models.agent import Agent
import json
from core.models.prompt_relation import AgentPromptRelation
from ui.router import register_handler
import traceback

@register_handler('create_agent_prompt_relation')
def handle_create_agent_prompt_relation(consumer, agent_id, prompt_pk, role, insert_at, index):
    """
    Creates a new AgentPromptRelation.
    """
    try:
        agent = Agent.objects.get(pk=agent_id)
        relation = AgentPromptRelation(
            agent=agent,
            prompt_id=prompt_pk,
            role=role,
            insert_at=insert_at,
            index=index
        )
        relation.save()
        # After saving, send the updated list of relations to the client
        handle_agent_prompt_relation_list(consumer, agent.pk)
    except Agent.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Agent with pk {agent_id} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error creating AgentPromptRelation: {e} {traceback.format_exc()}'}))

@register_handler('update_agent_prompt_relation')
def handle_update_agent_prompt_relation(consumer, data):
    """
    Updates an existing AgentPromptRelation.
    """
    try:
        relation_id = data.pop('id')
        relation = AgentPromptRelation.objects.get(pk=relation_id)
        for key, value in data.items():
            if hasattr(relation, key) and key not in ['id', 'pk', 'agent_id', 'prompt_id']:
                setattr(relation, key, value)
        relation.save()
        relation.agent.send_object_to_clients()
    except AgentPromptRelation.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentPromptRelation with id {relation_id} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error updating AgentPromptRelation: {e} {traceback.format_exc()}'}))

@register_handler('delete_agent_prompt_relation')
def handle_delete_agent_prompt_relation(consumer, relation_id):
    """
    Deletes an AgentPromptRelation.
    """
    try:
        relation = AgentPromptRelation.objects.get(pk=relation_id)
        agent = relation.agent
        relation.delete()
        # After deleting, send the updated list of relations to the client
        handle_agent_prompt_relation_list(consumer, agent.pk)
    except AgentPromptRelation.DoesNotExist:
        pass # Deleting something that doesn't exist is a success
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error deleting AgentPromptRelation: {e} {traceback.format_exc()}'}))


@register_handler('agent_prompt_relation_list')
def handle_agent_prompt_relation_list(consumer, agent_id):
    """
    Fetches all AgentPromptRelations for a given agent.
    """
    try:
        relations = AgentPromptRelation.objects.filter(agent_id=agent_id).order_by('insert_at', 'index')

        relations_payload = [r.as_client_dict() for r in relations]

        response_data = {
            'object': 'AgentPromptRelationList',
            'agent_id': agent_id,
            'relations': relations_payload
        }
        consumer.send(text_data=json.dumps(response_data))

    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error fetching agent prompt relations: {e} {traceback.format_exc()}'}))
