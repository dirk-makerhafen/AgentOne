from django.contrib.auth.models import User
import json
from core.models.prompt_string import PromptString
from ui.router import register_handler
import traceback

@register_handler('prompt_create')
def handle_prompt_create(consumer, original_prompt_pk):
    if not original_prompt_pk:
        consumer.send(text_data=json.dumps({'type': 'error', 'message': 'Missing original_prompt_pk for create_custom_prompt_version.'}))
        return 

    try:
        user = User.objects.get(pk=consumer.user_pk)
        original_prompt = PromptString.objects.get(pk=original_prompt_pk)
        if original_prompt.owner is not None:
            consumer.send(text_data=json.dumps({
                'object': 'error',
                'message': 'Only system-owned prompts can be copied to a custom version.'
            }))
            return
        new_prompt, created = PromptString.objects.get_or_create(
            owner=user,
            source=original_prompt.source,
            key=original_prompt.key,
            defaults={'value': original_prompt.value}
        )

        if created:
            message_text = f'Custom version of prompt "{new_prompt.key}" created successfully.'
        else:
            message_text = f'Custom version of prompt "{new_prompt.key}" already exists.'

        consumer.send(text_data=json.dumps({
            'object': 'info', # Changed from error to info
            'message': message_text
        }))

    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {consumer.user_pk} not found.'}))
    except PromptString.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message':  f'Original prompt with pk {original_prompt_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message':  f'Error creating custom prompt version: {e} {traceback.format_exc()}'}))

@register_handler('prompt_update')
def handle_prompt_update(consumer, prompt_pk, value):
    if prompt_pk is None or value is None:
        consumer.send(text_data=json.dumps({'type': 'error', 'message': 'Missing prompt_pk or value for update_prompt.'}))
        return 

    try:
        user = User.objects.get(pk=consumer.user_pk)
        prompt = PromptString.objects.get(pk=prompt_pk, owner=user)

        if prompt.value != value:
            prompt.value = value
            prompt.save()
            message_text = f'Prompt "{prompt.key}" updated successfully.'
        else:
            message_text = f'Prompt "{prompt.key}" content unchanged.'

        consumer.send(text_data=json.dumps({'object': 'info', 'message': message_text}))

    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message':  f'User with pk {consumer.user_pk} not found.'}))
    except PromptString.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Prompt with pk {prompt_pk} not found or permission denied.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error updating prompt: {e} {traceback.format_exc()}'}))

@register_handler('prompt_delete')
def handle_prompt_delete(consumer, prompt_pk):
    from core.tasks.send_websocket_update import celery_send_websocket_update

    if prompt_pk is None:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Missing prompt_pk for delete_prompt.'}))
        return

    try:
        user = User.objects.get(pk=consumer.user_pk)
        prompt_to_delete = PromptString.objects.get(pk=prompt_pk, owner=user)
        prompt_pk_to_broadcast = prompt_to_delete.pk
        prompt_to_delete.delete()

        # After successful deletion, broadcast the update to the user
        message_data = {
            'object': 'PromptDeleted',
            'prompt_pk': prompt_pk_to_broadcast
        }
        celery_send_websocket_update.delay(message_data, user_pk=user.pk)

    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {consumer.user_pk} not found.'}))
    except PromptString.DoesNotExist:
        # If it's already gone, we can still send a delete message to the client to ensure sync
        message_data = {
            'object': 'PromptDeleted',
            'prompt_pk': int(prompt_pk)
        }
        celery_send_websocket_update.delay(message_data, user_pk=consumer.user_pk)
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message':  f'Error deleting prompt: {e} {traceback.format_exc()}'}))

@register_handler('prompt_list')
def handle_prompt_list(consumer, **kwargs):
    all_prompts_data = []

    def get_latest_prompts_with_version_counts(**owner_filter):
        latest_versions_queryset = list(PromptString.objects.filter(**owner_filter, next_version__isnull=True))
        prompts_with_counts = []
        for latest_prompt in latest_versions_queryset:
            version_count = PromptString.objects.filter(owner=latest_prompt.owner, source=latest_prompt.source, key=latest_prompt.key).count()
            latest_prompt.version_count = version_count
            prompts_with_counts.append(latest_prompt)
        return prompts_with_counts

    try:
        user = User.objects.get(pk=consumer.user_pk)
        all_prompts_data.extend(get_latest_prompts_with_version_counts(owner=user))
        all_prompts_data.extend(get_latest_prompts_with_version_counts(owner=None))
    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {consumer.user_pk} not found.'}))
        return
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error fetching prompt list: {e} {traceback.format_exc()}'}))
        return

    all_prompts_data.sort(key=lambda p: (p.owner_id, p.source, p.key) if p.owner_id else (-1, p.source, p.key) )
    client_payload = []
    for prompt in all_prompts_data:
        client_dict = prompt.as_client_dict()
        client_dict['version_count'] = prompt.version_count
        client_payload.append(client_dict)

    consumer.send(text_data=json.dumps({'type': 'prompt_list', 'object': 'PromptList', 'payload': client_payload}))
