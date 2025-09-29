import json
from providers.models import ApiProvider

def handle_provider_create(consumer, payload):
    try:
        name = payload.get('name')
        url = payload.get('url')
        if not name:
            consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Provider name is required.'}))
            return
        provider = ApiProvider(name=name, url=url)
        provider.save()
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error creating API Provider: {str(e)}'}))


def handle_provider_delete(consumer, payload):
    try:
        provider_pk = payload.get('provider_pk')
        if not provider_pk:
            consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Provider PK is required for deletion.'}))
            return
        provider = ApiProvider.objects.get(pk=provider_pk)
        provider.delete()
        consumer.send(text_data=json.dumps({'object': 'ProviderDeleted', 'provider_pk': provider_pk}))
    except ApiProvider.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Provider with PK {provider_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error deleting API Provider: {str(e)}'}))


def handle_provider_list(consumer):
    """
    Fetches all ApiProvider objects and sends them to the client.
    """
    try:
        providers = ApiProvider.objects.all().order_by('name')
        provider_list = []
        for provider in providers:
            provider_list.append(provider.as_client_dict())
        consumer.send(text_data=json.dumps({'object': 'ApiProviderList', 'providers': provider_list}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error fetching API Providers: {str(e)}'}))


def handle_provider_update(consumer, payload):
    """
    Updates an existing ApiProvider instance and broadcasts the update.
    """
    try:
        provider_pk = payload.get('provider_pk')
        name = payload.get('name')
        url = payload.get('url')

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
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error updating API Provider: {str(e)}'}))

