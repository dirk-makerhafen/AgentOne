import json
from ui.router import register_handler
from providers.models.ai_model import AiModel
from providers.models.api_provider import ApiProvider

@register_handler('aimodel_create')
def handle_aimodel_create(consumer, provider_pk, model_name):
    if not provider_pk or not model_name:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Provider PK and model name are required.'}))
        return

    try:
        provider = ApiProvider.objects.get(pk=provider_pk)
        # Use .create() for simplicity, which calls save() internally
        AiModel.objects.create(apiProvider=provider, name=model_name, free_limit_per_day=0)
        # Explicitly send the provider update *after* the model has been created.
        provider.send_object_to_clients()
    except ApiProvider.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Provider with PK {provider_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error creating provider model: {str(e)}'}))

@register_handler('aimodel_delete')
def handle_aimodel_delete(consumer, provider_pk, model_pk):
    if not model_pk or not provider_pk:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Model PK and Provider PK are required.'}))
        return

    try:
        provider = ApiProvider.objects.get(pk=provider_pk)
        try:
            # Ensure we only try to delete a model that belongs to the provider
            model = AiModel.objects.get(pk=model_pk, apiProvider=provider)
            model.delete()
        except AiModel.DoesNotExist:
            # If the model is already gone, that's fine. We'll still send the
            # provider update to ensure the client UI is synchronized.
            pass

        # Always send the parent provider object to the client after a change.
        provider.send_object_to_clients()

    except ApiProvider.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Provider with PK {provider_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error deleting provider model: {str(e)}'}))
