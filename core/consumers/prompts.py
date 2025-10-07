from django.contrib.auth.models import User
import json
from core.models.prompt_string import PromptString
from ui.router import register_handler

@register_handler('prompt_create')
def handle_prompt_create(consumer, user_pk, payload):
    original_prompt_pk = payload.get('original_prompt_pk')            
    if not original_prompt_pk:
        consumer.send(text_data=json.dumps({'type': 'error', 'message': 'Missing original_prompt_pk for create_custom_prompt_version.'}))
        return 
    
    try:
        user = User.objects.get(pk=user_pk)
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
        handle_prompt_list(consumer, user_pk, payload={}) # Pass empty payload

    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {user_pk} not found.'}))
    except PromptString.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message':  f'Original prompt with pk {original_prompt_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message':  f'Error creating custom prompt version: {e}'}))

@register_handler('prompt_update')
def handle_prompt_update(consumer, user_pk, payload):
    prompt_pk = payload.get('prompt_pk')
    new_value = payload.get('value')
    if prompt_pk is None or new_value is None:
        consumer.send(text_data=json.dumps({'type': 'error', 'message': 'Missing prompt_pk or value for update_prompt.'}))
        return 
    
    try:
        user = User.objects.get(pk=user_pk)
        prompt = PromptString.objects.get(pk=prompt_pk, owner=user)
        
        if prompt.value != new_value:
            prompt.value = new_value
            prompt.save()
            message_text = f'Prompt "{prompt.key}" updated successfully.'
        else:
            message_text = f'Prompt "{prompt.key}" content unchanged.'

        consumer.send(text_data=json.dumps({'object': 'info', 'message': message_text}))
    
    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message':  f'User with pk {user_pk} not found.'}))
    except PromptString.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Prompt with pk {prompt_pk} not found or permission denied.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error updating prompt: {e}'}))

@register_handler('prompt_delete')
def handle_prompt_delete(consumer, user_pk, payload):
    prompt_pk = payload.get('prompt_pk')
    if prompt_pk is None:
        consumer.send(text_data=json.dumps({'type': 'error', 'message': 'Missing prompt_pk for delete_prompt.'}))
        return

    try:
        user = User.objects.get(pk=user_pk)
        prompt_to_delete = PromptString.objects.get(pk=prompt_pk, owner=user)
        
        # The delete signal on the model will handle sending the update
        prompt_to_delete.delete()

        consumer.send(text_data=json.dumps({'type': 'info', 'message': f'Prompt deleted successfully.'}))

    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {user_pk} not found.'}))
    except PromptString.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Prompt with pk {prompt_pk} not found or permission denied.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message':  f'Error deleting prompt: {e}'}))

@register_handler('prompt_list')
def handle_prompt_list(consumer, user_pk, payload):
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
        user = User.objects.get(pk=user_pk)
        all_prompts_data.extend(get_latest_prompts_with_version_counts(owner=user))
        all_prompts_data.extend(get_latest_prompts_with_version_counts(owner=None))
    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {user_pk} not found.'}))
        return
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error fetching prompt list: {e}'}))
        return

    all_prompts_data.sort(key=lambda p: (p.owner_id, p.source, p.key) if p.owner_id else (-1, p.source, p.key) )
    client_payload = []
    for prompt in all_prompts_data:
        client_dict = prompt.as_client_dict()
        client_dict['version_count'] = prompt.version_count
        client_payload.append(client_dict)

    consumer.send(text_data=json.dumps({'type': 'prompt_list', 'object': 'PromptList', 'payload': client_payload}))
