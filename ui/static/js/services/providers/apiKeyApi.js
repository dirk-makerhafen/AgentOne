// API functions for providers/consumers/api_key.py
const apiKeyApi = {
    create: function(provider_pk, key, comment) {
        sendRequest('apikey_create', { provider_pk, key, comment });
    },
    delete: function(provider_pk, apikey_pk) {
        sendRequest('apikey_delete', { provider_pk, apikey_pk });
    }
};
