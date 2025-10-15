import json
from ui.router import register_handler
from providers.models.ai_model import AiModel
from providers.models.api_provider import ApiProvider
import traceback

@register_handler('aimodel_create')
def handle_aimodel_create(consumer, provider_pk, model_name):
    if not provider_pk or not model_name:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Provider PK and model name are required.'}))
        return
    try:
        AiModel.objects.create(apiProvider_id=provider_pk, name=model_name)
    except ApiProvider.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Provider with PK {provider_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error creating provider model: {str(e)} {traceback.format_exc()}'}))

@register_handler('aimodel_delete')
def handle_aimodel_delete(consumer, provider_pk, model_pk):
    if not model_pk or not provider_pk:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Model PK and Provider PK are required.'}))
        return

    try:
        try:
            # Ensure we only try to delete a model that belongs to the provider
            model = AiModel.objects.get(pk=model_pk, apiProvider_id=provider_pk)
            model.delete()
        except AiModel.DoesNotExist:
            pass

    except ApiProvider.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Provider with PK {provider_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error deleting provider model: {str(e)} {traceback.format_exc()}'}))
