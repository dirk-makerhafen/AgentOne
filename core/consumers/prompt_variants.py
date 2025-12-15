from django.contrib.auth.models import User
from agents.models.agent import Agent
import json
from core.models.prompt_variant import PromptVariant
from ui.router import register_handler
import traceback
from django.db.models import Q

@register_handler('prompt_variant_list')
def handle_prompt_variant_list(consumer, prompt_pk):
    """
    Handles fetching all variants for a specific abstract prompt,
    separated into system and user-owned lists.
    """
    try:
        user = User.objects.get(pk=consumer.user_pk)

        # Get all user-owned variants for this prompt
        user_variants = PromptVariant.objects.filter(
            prompt_id=prompt_pk, 
            owner=user,
            next_version__isnull=True,

        ).order_by('-version_nr')

        # Get all system-owned variants for this prompt
        system_variants = PromptVariant.objects.filter(
            prompt_id=prompt_pk,
            owner__isnull=True,
            next_version__isnull=True,
        ).order_by('-version_nr')

        user_variants_payload = [pv.as_client_dict() for pv in user_variants]
        system_variants_payload = [pv.as_client_dict() for pv in system_variants]

        response_data = {
            'object': 'PromptVariantList',
            'prompt_pk': prompt_pk,
            'variants': system_variants_payload + user_variants_payload,
        }
        consumer.send(text_data=json.dumps(response_data))

    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {consumer.user_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error fetching prompt variants: {e} {traceback.format_exc()}'}))

@register_handler('prompt_variant_update')
def handle_prompt_variant_update(consumer, prompt_variant_pk, value=None, is_enabled=None):
    from core.models.prompt_variant import PromptVariant

    if prompt_variant_pk is None:
        consumer.send(text_data=json.dumps({'type': 'error', 'message': 'Missing prompt_variant_pk for prompt_variant_update.'}))
        return

    try:
        user = User.objects.get(pk=consumer.user_pk)
        prompt_variant = PromptVariant.objects.get(pk=prompt_variant_pk, owner=user, next_version__isnull=True)

        new_version = None
        if value is not None and prompt_variant.value != value:
            new_version = prompt_variant.update_value(value)

        target_variant = new_version if new_version else prompt_variant

        updated = False
        if is_enabled is not None and target_variant.is_enabled != is_enabled:
            target_variant.is_enabled = is_enabled
            target_variant.save()
            updated = True

        if new_version:
            message_text = f'Prompt "{target_variant.prompt.key}" updated to new version {target_variant.version_nr}.'
            consumer.send(text_data=json.dumps({'object': 'info', 'message': message_text}))
        elif updated:
            message_text = f'PromptVariant "{prompt_variant_pk}" updated successfully.'
            consumer.send(text_data=json.dumps({'object': 'info', 'message': message_text}))
        else:
            message_text = f'Prompt "{prompt_variant.prompt.key}" content unchanged.'
            consumer.send(text_data=json.dumps({'object': 'info', 'message': message_text}))

    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message':  f'User with pk {consumer.user_pk} not found.'}))
    except PromptVariant.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'PromptVariant with pk {prompt_variant_pk} not found, or not owned by user, or not the latest version.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error updating PromptVariant: {e} {traceback.format_exc()}'}))


@register_handler('prompt_variant_delete')
def handle_prompt_delete(consumer, prompt_variant_pk):
    from core.tasks.send_websocket_update import celery_send_websocket_update
    from core.models.prompt import PromptVariant

    if prompt_variant_pk is None:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Missing prompt_variant_pk for delete_prompt.'}))
        return

    try:
        user = User.objects.get(pk=consumer.user_pk)
        # Only allow deleting user-owned variants that are the latest version
        prompt_variant_to_delete = PromptVariant.objects.get(pk=prompt_variant_pk, owner=user, next_version__isnull=True)
        
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
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Prompt variant with pk {prompt_variant_pk} not found, not owned by user, or not the latest version.'}))
        # If it's already gone or inaccessible, we can still send a delete message to the client to ensure sync
        message_data = {
            'object': 'PromptDeleted',
            'prompt_pk': int(prompt_variant_pk)
        }
        celery_send_websocket_update.delay(message_data, user_pk=consumer.user_pk)
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message':  f'Error deleting prompt: {e} {traceback.format_exc()}'}))
