import json
from dashboard.tasks import send_object_to_clients
from providers.models import ApiProvider, ApiKey

def handle_provider_apikey_create(consumer, payload):
    if not payload.get('provider_pk') or not payload.get('key'):
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Provider PK and key are required.'}))
        return

    try:
        provider = ApiProvider.objects.get(pk=payload.get('provider_pk'))
        ApiKey.objects.create(apiProvider=provider, key=payload.get('key'), comment= payload.get('comment'))
        send_object_to_clients(provider)
    except ApiProvider.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Provider with PK {payload.get('provider_pk')} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error creating provider API key: {str(e)}'}))

def handle_provider_apikey_delete(consumer, payload):
    if not payload.get('apikey_pk') or not  payload.get('provider_pk'):
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'API Key PK and Provider PK are required.'}))
        return
    try:
        provider = ApiProvider.objects.get(pk= payload.get('provider_pk'))        
        apikey = ApiKey.objects.get(pk=payload.get('apikey_pk'))
        apikey.delete()
        send_object_to_clients(provider)
    except ApiKey.DoesNotExist:
        send_object_to_clients(provider)
    except ApiProvider.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Provider with PK { payload.get('provider_pk')} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message':  f'Error deleting provider API key: {str(e)}'}))
