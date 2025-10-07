import json
from ui.router import register_handler
from providers.models.ai_model import AiModel
from providers.models.api_provider import ApiProvider

@register_handler('aimodel_create')
def handle_aimodel_create(consumer, user_pk, payload):
    if not payload.get('provider_pk') or not payload.get('model_name'):
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Provider PK and model name are required.'}))
        return

    try:
        provider = ApiProvider.objects.get(pk=payload.get('provider_pk'))
        model = AiModel(apiProvider=provider, name=payload.get('model_name'), free_limit_per_day=0)
        model.save()
    except ApiProvider.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Provider with PK {payload.get("provider_pk")} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error creating provider model: {str(e)}'}))

@register_handler('aimodel_delete')
def handle_aimodel_delete(consumer, user_pk, payload):
    provider_pk = payload.get('provider_pk')
    model_pk = payload.get('model_pk')

    if not model_pk or not provider_pk:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Model PK and Provider PK are required.'}))
        return

    try:
        model = AiModel.objects.get(pk=model_pk)
        provider = ApiProvider.objects.get(pk=provider_pk)
        if model.apiProvider != provider:
             consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Model does not belong to the specified provider.'}))
             return
        model.delete()
    except AiModel.DoesNotExist:
        pass # If model is already gone, that's fine
    except ApiProvider.DoesNotExist:
         consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Provider with PK {provider_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error deleting provider model: {str(e)}'}))
