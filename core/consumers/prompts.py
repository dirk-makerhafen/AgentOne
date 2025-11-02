from django.contrib.auth.models import User
import json
from core.models.prompt import Prompt
from ui.router import register_handler
import traceback
from django.db.models import Q

@register_handler('prompt_list')
def handle_prompt_list(consumer):
    """
    Handles fetching the list of all abstract Prompt definitions for the global Prompts tab.
    """
    try:
        # We fetch all prompts that have at least one variant that is the newest version.
        # This prevents showing empty, abstract prompts that have no active variants.
        prompts = Prompt.objects.filter(variants__next_version__isnull=True).distinct()

        response_payload = [p.as_client_dict() for p in prompts]

        response_data = {
            'object': 'PromptDefinitionList',
            'payload': response_payload
        }
        consumer.send(text_data=json.dumps(response_data))

    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error fetching prompt list: {e} {traceback.format_exc()}'}))

@register_handler('prompt_create')
def handle_prompt_create(consumer, source, key, value, description, data_lambda=None):
    """
    Handles creation of a new Prompt and its first user-owned PromptVariant.
    """
    from core.models.prompt import Prompt
    from core.models.prompt_variant import PromptVariant
    try:
        user = User.objects.get(pk=consumer.user_pk)

        if not all([source, key, value]):
            consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Source, key, and value are required.'}))
            return

        # Get or create the abstract prompt definition
        prompt, created = Prompt.objects.get_or_create(
            source=source,
            key=key,
            defaults={'description': description, 'data_lambda': data_lambda or ''}
        )
        if not created: # Update description/lambda if provided for an existing prompt
            if description:
                prompt.description = description
            if data_lambda:
                prompt.data_lambda = data_lambda
            prompt.save()

        # Create the first user-owned variant for this prompt
        PromptVariant.objects.create(
            prompt=prompt,
            owner=user,
            value=value,
            is_enabled=True,
            version_nr=1
        )

        # After creation, trigger a refresh of the prompt list for the user
        handle_prompt_list(consumer)

    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {consumer.user_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error creating prompt: {e} {traceback.format_exc()}'}))

@register_handler('prompt_delete')
def handle_prompt_delete(consumer, prompt_pk):
    from core.tasks.send_websocket_update import celery_send_websocket_update
    from core.models.prompt import PromptVariant

    if prompt_pk is None:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Missing prompt_pk for delete_prompt.'}))
        return

    try:
        user = User.objects.get(pk=consumer.user_pk)
        # Only allow deleting user-owned variants that are the latest version
        
        prompt_to_delete = Prompt.objects.get(Q(owner=user) | Q(owner=None) | Q(user.is_superuser), pk=prompt_pk)
        prompt_to_delete.delete()
        # After successful deletion, broadcast the update to the user
        message_data = {
            'object': 'PromptDeleted',
            'prompt_pk': prompt_pk
        }        
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


@register_handler('prompt_update')
def handle_prompt_update(consumer, prompt_pk, description=None, data_lambda=None):
    """
    Handles updates to the abstract Prompt definition itself.
    """
    try:
        user = User.objects.get(pk=consumer.user_pk)
        # Allow editing if user is owner, superuser, or if prompt is unowned (system)
        prompt = Prompt.objects.get(Q(owner=user) | Q(owner=None) | Q(user__is_superuser=True), pk=prompt_pk)

        updated = False
        if description is not None and prompt.description != description:
            prompt.description = description
            updated = True
        
        if data_lambda is not None and prompt.data_lambda != data_lambda:
            prompt.data_lambda = data_lambda
            updated = True

        if updated:
            prompt.save()
            # No broadcast needed here, as the save signal on Prompt will trigger an update.
            consumer.send(text_data=json.dumps({'object': 'info', 'message': f'Prompt "{prompt.key}" definition updated.'}))
        else:
            consumer.send(text_data=json.dumps({'object': 'info', 'message': 'No changes detected for prompt definition.'}))


    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {consumer.user_pk} not found.'}))
    except Prompt.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Prompt with pk {prompt_pk} not found or permission denied.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error updating prompt definition: {e} {traceback.format_exc()}'}))
