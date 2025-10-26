from django.contrib.auth.models import User
from agents.models.agent import Agent
import json
from core.models.prompt_string import Prompt
from ui.router import register_handler
import traceback

@register_handler('prompt_variant_create')
def handle_promptvariant_create(consumer, base_variant_pk, agent_id=None):
    from core.models.prompt_string import Prompt, PromptVariant

    if not base_variant_pk:
        consumer.send(text_data=json.dumps({'type': 'error', 'message': 'Missing base_variant_pk for create_custom_prompt_version.'}))
        return

    try:
        user = User.objects.get(pk=consumer.user_pk)
        base_variant = PromptVariant.objects.get(pk=base_variant_pk)
        if base_variant.owner and base_variant.owner != user:
            consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Permission denied: You can only create new versions from your own variants or system variants.'}))
            return
        if base_variant.owner == user and base_variant.next_version:
            consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Cannot create a new version from an old version of your own variant. Please use the latest version.'}))
            return
        agent = None
        if agent_id:
            try:
                agent = Agent.objects.get(pk=agent_id, owners=user)
            except Agent.DoesNotExist:
                consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Agent with pk {agent_id} not found or permission denied.'}))
                return
        new_variant = PromptVariant.objects.create(
            prompt=base_variant.prompt,  # Link to the same Prompt Definition
            owner=user,                  # Owned by the current user
            agent=agent,                 # Agent-specific if agent_id provided
            value=base_variant.value,    # Copy content from the base variant
            is_enabled=True              # New versions are enabled by default
        )
       
        consumer.send(text_data=json.dumps({
            'object': 'info',
            'message': f'New version for prompt "{base_variant.prompt.key}" created successfully.'
        }))

    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {consumer.user_pk} not found.'}))
    except PromptVariant.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Base prompt variant with pk {base_variant_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error creating new prompt version: {e} {traceback.format_exc()}'}))

@register_handler('prompt_update')
def handle_prompt_update(consumer, prompt_pk, value=None, is_enabled=None):
    from core.models.prompt_string import Prompt, PromptVariant

    if prompt_pk is None:
        consumer.send(text_data=json.dumps({'type': 'error', 'message': 'Missing prompt_pk for update_prompt.'}))
        return 

    try:
        user = User.objects.get(pk=consumer.user_pk)
        # Ensure we are updating the latest version owned by the user
        prompt_variant = PromptVariant.objects.get(pk=prompt_pk, owner=user, next_version__isnull=True)

        updated = False
        if value is not None and prompt_variant.value != value:
            prompt_variant.value = value
            updated = True

        if is_enabled is not None and prompt_variant.is_enabled != is_enabled:
            # Prevent disabling the only active custom variant for a given prompt definition
            if not is_enabled:
                query_filters = {
                    'prompt': prompt_variant.prompt,
                    'owner': user,
                    'is_enabled': True,
                    'next_version__isnull': True
                }
                if prompt_variant.agent:
                    query_filters['agent'] = prompt_variant.agent
                else:
                    query_filters['agent__isnull'] = True

                other_active_variants = PromptVariant.objects.filter(**query_filters).exclude(pk=prompt_variant.pk)
                
                if not other_active_variants.exists():
                    consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Cannot disable the only active custom version of prompt "{prompt_variant.prompt.key}". Create another active version first.'}))
                    return
            
            prompt_variant.is_enabled = is_enabled
            updated = True

        if updated:
            prompt_variant.save()
            # prompt_variant.save() already triggers send_object_to_clients with object: 'PromptVariant'
            # So we only need to send the info message separately
            message_text = f'Prompt "{prompt_variant.prompt.key}" updated successfully.'
            consumer.send(text_data=json.dumps({
                'object': 'info',
                'message': message_text
            }))
        else:
            message_text = f'Prompt "{prompt_variant.prompt.key}" content unchanged.'
            consumer.send(text_data=json.dumps({'object': 'info', 'message': message_text}))

    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message':  f'User with pk {consumer.user_pk} not found.'}))
    except PromptVariant.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Prompt variant with pk {prompt_pk} not found, or not owned by user, or not the latest version.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error updating prompt: {e} {traceback.format_exc()}'}))


@register_handler('prompt_delete')
def handle_prompt_delete(consumer, prompt_pk):
    from core.tasks.send_websocket_update import celery_send_websocket_update
    from core.models.prompt_string import PromptVariant

    if prompt_pk is None:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Missing prompt_pk for delete_prompt.'}))
        return

    try:
        user = User.objects.get(pk=consumer.user_pk)
        # Only allow deleting user-owned variants that are the latest version
        prompt_variant_to_delete = PromptVariant.objects.get(pk=prompt_pk, owner=user, next_version__isnull=True)
        
        # If this variant was linked as a next_version, clear that link
        if hasattr(prompt_variant_to_delete, 'prev_version'):
            prev_variant = prompt_variant_to_delete.prev_version
            prev_variant.next_version = None
            prev_variant.save()

        # Store agent_id before deletion for broadcast
        agent_id_to_broadcast = prompt_variant_to_delete.agent_id
        prompt_pk_to_broadcast = prompt_variant_to_delete.pk

        prompt_variant_to_delete.delete()

        # After successful deletion, broadcast the update to the user
        message_data = {
            'object': 'PromptDeleted',
            'prompt_pk': prompt_pk_to_broadcast
        }
        if agent_id_to_broadcast:
            message_data['agent_id'] = agent_id_to_broadcast
        
        celery_send_websocket_update.delay(message_data, user_pk=user.pk)

    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {consumer.user_pk} not found.'}))
    except PromptVariant.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Prompt variant with pk {prompt_pk} not found, not owned by user, or not the latest version.'}))
        # If it's already gone or inaccessible, we can still send a delete message to the client to ensure sync
        message_data = {
            'object': 'PromptDeleted',
            'prompt_pk': int(prompt_pk)
        }
        celery_send_websocket_update.delay(message_data, user_pk=consumer.user_pk)
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message':  f'Error deleting prompt: {e} {traceback.format_exc()}'}))

@register_handler('prompt_list')
def handle_prompt_list(consumer, agent_id=None, **kwargs):
    from django.db.models import Count, Q
    from core.models.prompt_string import Prompt, PromptVariant
    
    # This handler sends a list of Prompt Definitions, annotated with variant counts.
    # The frontend will then request variants on-demand when a definition is expanded.

    try:
        user = User.objects.get(pk=consumer.user_pk)
        
        # If an agent_id is provided, this is for the Agent Edit tab.
        if agent_id:
            # This logic can be refined later if needed, but for now, we'll send agent-specific variants.
            # For simplicity, we can fetch all variants for the agent and let the frontend filter.
            agent_variants = PromptVariant.objects.filter(agent_id=agent_id, owner=user, next_version__isnull=True).select_related('prompt', 'owner')
            response_payload = [pv.as_client_dict() for pv in agent_variants]
            response_object = 'PromptList'
            
            response_data = {
                'type': 'prompt_list',
                'object': response_object,
                'agent_id': agent_id,
                'payload': response_payload
            }
            consumer.send(text_data=json.dumps(response_data))
            return

        # This is for the global Prompts tab.
        all_prompts = Prompt.objects.all().annotate(
            user_variants_count=Count(
                'variants',
                filter=Q(variants__owner=user, variants__agent__isnull=True, variants__next_version__isnull=True, variants__is_enabled=True),
                distinct=True
            ),
            system_variants_count=Count(
                'variants',
                filter=Q(variants__owner__isnull=True, variants__agent__isnull=True), # Removed next_version__isnull=True to count all system variants
                distinct=True
            )
        ).filter(system_variants_count__gt=0) # Only show prompts with at least one system variant.

        client_payload = []
        for prompt in all_prompts:
            prompt_dict = prompt.as_client_dict()
            prompt_dict['user_variants_count'] = prompt.user_variants_count
            prompt_dict['system_variants_count'] = prompt.system_variants_count
            client_payload.append(prompt_dict)

        client_payload.sort(key=lambda p: (p['source'], p['key']))

        response_data = {
            'type': 'prompt_list',
            'object': 'PromptDefinitionList',
            'payload': client_payload
        }
        consumer.send(text_data=json.dumps(response_data))

    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {consumer.user_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error fetching prompt list: {e} {traceback.format_exc()}'}))


@register_handler('prompt_get_variants')
def handle_prompt_get_variants(consumer, prompt_pk, **kwargs):
    from core.models.prompt_string import Prompt, PromptVariant
    try:
        user = User.objects.get(pk=consumer.user_pk)
        prompt = Prompt.objects.get(pk=prompt_pk)

        latest_user_variants = list(prompt.variants.filter(
            owner=user, agent__isnull=True, next_version__isnull=True, is_enabled=True
        ).order_by('-created_at'))

        from django.db.models import Q

        latest_system_variants = list(prompt.variants.filter(
            Q(owner__isnull=True, agent__isnull=True) &
            (Q(next_version__isnull=True) | Q(next_version__owner__isnull=False))
        ).order_by('-created_at').distinct())
        
        response_data = {
            'type': 'prompt_variants',
            'object': 'PromptVariantList',
            'prompt_pk': prompt_pk,
            'user_variants': [v.as_client_dict() for v in latest_user_variants],
            'system_variants': [v.as_client_dict() for v in latest_system_variants]
        }
        consumer.send(text_data=json.dumps(response_data))

    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {consumer.user_pk} not found.'}))
    except Prompt.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Prompt with pk {prompt_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error fetching prompt variants: {e} {traceback.format_exc()}'}))

