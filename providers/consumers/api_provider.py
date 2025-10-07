import json
from ui.router import register_handler
from providers.models.api_provider import ApiProvider

@register_handler('provider_create')
def handle_provider_create(consumer, user_pk, payload):
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

@register_handler('provider_update')
def handle_provider_update(consumer, user_pk, payload):
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

@register_handler('provider_delete')
def handle_provider_delete(consumer, user_pk, payload):
    try:
        provider_pk = payload.get('provider_pk')
        if not provider_pk:
            consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Provider PK is required for deletion.'}))
            return
        provider = ApiProvider.objects.get(pk=provider_pk)
        provider.delete()
    except ApiProvider.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Provider with PK {provider_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error deleting API Provider: {str(e)}'}))

@register_handler('provider_list')
def handle_provider_list(consumer, user_pk, payload):
    try:
        providers = ApiProvider.objects.all().order_by('name')
        provider_list = [p.as_client_dict() for p in providers]
        consumer.send(text_data=json.dumps({'object': 'ApiProviderList', 'providers': provider_list}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error fetching API Providers: {str(e)}'}))
