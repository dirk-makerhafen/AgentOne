import json
from dashboard.tasks import send_object_to_clients
from providers.models import ApiProvider, Model


def handle_provider_model_create(consumer, payload):
    if not  payload.get('provider_pk') or not payload.get('model_name'):
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Provider PK and model name are required.'}))
        return

    try:
        provider = ApiProvider.objects.get(pk= payload.get('provider_pk'))
        llmmodel = Model(apiProvider=provider, name=payload.get('model_name'), free_limit_per_day=0 )
        llmmodel.save()
        send_object_to_clients(provider)
    except ApiProvider.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Provider with PK { payload.get('provider_pk')} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error creating provider model: {str(e)}'}))


def handle_provider_model_delete(consumer, payload):
    provider_pk = payload.get('provider_pk')
    model_pk = payload.get('model_pk')

    if not model_pk or not provider_pk:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Model PK and Provider PK are required.'}))
        return

    try:
        model = Model.objects.get(pk=model_pk)
        provider = ApiProvider.objects.get(pk=provider_pk)
        if model.apiProvider != provider:
             consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Model does not belong to the specified provider.'}))
             return
        model.delete()
        send_object_to_clients(provider)

    except Model.DoesNotExist:
        try:
            provider = ApiProvider.objects.get(pk=provider_pk)
            send_object_to_clients(provider)
        except ApiProvider.DoesNotExist:
            consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Provider with PK {provider_pk} not found.'}))
    except ApiProvider.DoesNotExist:
         consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Provider with PK {provider_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error deleting provider model: {str(e)}'}))
