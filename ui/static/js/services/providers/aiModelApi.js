// API functions for providers/consumers/ai_model.py
const aiModelApi = {
    create: function(provider_pk, model_name) {
        sendRequest('aimodel_create', { provider_pk, model_name });
    },
    delete: function(provider_pk, model_pk) {
        sendRequest('aimodel_delete', { provider_pk, model_pk });
    }
};
