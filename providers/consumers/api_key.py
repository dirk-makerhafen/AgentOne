import json
from ui.router import register_handler
from providers.models.api_provider import ApiProvider
from providers.models.api_key import ApiKey

@register_handler('apikey_create')
def handle_apikey_create(consumer, user_pk, payload):
    if not payload.get('provider_pk') or not payload.get('key'):
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Provider PK and key are required.'}))
        return

    try:
        provider = ApiProvider.objects.get(pk=payload.get('provider_pk'))
        ApiKey.objects.create(apiProvider=provider, key=payload.get('key'), comment=payload.get('comment'))
        provider.send_object_to_clients(user_pk=user_pk)
    except ApiProvider.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Provider with PK {payload.get("provider_pk")} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error creating provider API key: {str(e)}'}))

@register_handler('apikey_delete')
def handle_apikey_delete(consumer, user_pk, payload):
    if not payload.get('apikey_pk') or not payload.get('provider_pk'):
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'API Key PK and Provider PK are required.'}))
        return
    try:
        provider = ApiProvider.objects.get(pk=payload.get('provider_pk'))        
        apikey = ApiKey.objects.get(pk=payload.get('apikey_pk'))
        apikey.delete()
        provider.send_object_to_clients(user_pk=user_pk)
    except ApiKey.DoesNotExist:
        provider.send_object_to_clients(user_pk=user_pk)
    except ApiProvider.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Provider with PK {payload.get("provider_pk")} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message':  f'Error deleting provider API key: {str(e)}'}))
