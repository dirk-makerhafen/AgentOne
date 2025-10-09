import json
from ui.router import register_handler
from providers.models.api_provider import ApiProvider
from providers.models.api_key import ApiKey

@register_handler('apikey_create')
def handle_apikey_create(consumer, provider_pk, key, comment=None):
    if not provider_pk or not key:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Provider PK and key are required.'}))
        return

    try:
        provider = ApiProvider.objects.get(pk=provider_pk)
        ApiKey.objects.create(apiProvider=provider, key=key, comment=comment)
        provider.send_object_to_clients()
    except ApiProvider.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Provider with PK {provider_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error creating provider API key: {str(e)}'}))

@register_handler('apikey_delete')
def handle_apikey_delete(consumer, provider_pk, apikey_pk):
    if not apikey_pk or not provider_pk:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'API Key PK and Provider PK are required.'}))
        return
    try:
        provider = ApiProvider.objects.get(pk=provider_pk)        
        apikey = ApiKey.objects.get(pk=apikey_pk)
        apikey.delete()
        provider.send_object_to_clients()
    except ApiKey.DoesNotExist:
        provider.send_object_to_clients()
    except ApiProvider.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Provider with PK {provider_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message':  f'Error deleting provider API key: {str(e)}'}))
