import json
from ui.router import register_handler
from providers.models.api_provider import ApiProvider
import traceback
@register_handler('provider_create')
def handle_provider_create(consumer, name, url=None):
    try:
        if not name:
            consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Provider name is required.'}))
            return
        provider = ApiProvider(name=name, url=url)
        provider.save()
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error creating API Provider: {str(e)}'}))

@register_handler('provider_update')
def handle_provider_update(consumer, provider_pk, name, url=None):
    try:
        if not provider_pk or not name:
            consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Provider PK and name are required.'}))
            return

        provider = ApiProvider.objects.get(pk=provider_pk)
        provider.name = name
        provider.url = url
        provider.save()
    except ApiProvider.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Provider with PK {provider_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error updating API Provider: {str(e)}{traceback.format_exc()}'}))

@register_handler('provider_delete')
def handle_provider_delete(consumer, provider_pk):
    from django.contrib.auth.models import User
    from core.tasks.send_websocket_update import celery_send_websocket_update

    if not provider_pk:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Provider PK is required for deletion.'}))
        return

    try:
        provider = ApiProvider.objects.get(pk=provider_pk)
        provider_pk_to_broadcast = provider.pk  # Store the pk before deletion
        provider.delete()

        # After successful deletion, broadcast the update to all users
        message_data = {
            'object': 'ProviderDeleted',
            'provider_pk': provider_pk_to_broadcast
        }
        all_user_pks = User.objects.values_list('pk', flat=True)
        for pk in all_user_pks:
            celery_send_websocket_update.delay(message_data, user_pk=pk)

    except ApiProvider.DoesNotExist:
        # If it doesn't exist, it's already gone. We can still send a delete
        # message to ensure clients are in sync, in case they missed it.
        message_data = {
            'object': 'ProviderDeleted',
            'provider_pk': int(provider_pk)
        }
        all_user_pks = User.objects.values_list('pk', flat=True)
        for pk in all_user_pks:
            celery_send_websocket_update.delay(message_data, user_pk=pk)

    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error deleting API Provider: {str(e)}{traceback.format_exc()}'}))

@register_handler('provider_list')
def handle_provider_list(consumer, **kwargs):
    try:
        providers = ApiProvider.objects.all().order_by('name')
        provider_list = [p.as_client_dict() for p in providers]
        consumer.send(text_data=json.dumps({'object': 'ApiProviderList', 'providers': provider_list}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error fetching API Providers: {str(e)}{traceback.format_exc()}'}))
