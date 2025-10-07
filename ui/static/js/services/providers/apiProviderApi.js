// API functions for providers/consumers/api_provider.py
const apiProviderApi = {
    create: function(name, url) {
        sendRequest('provider_create', { name, url });
    },
    update: function(provider_pk, name, url) {
        sendRequest('provider_update', { provider_pk, name, url });
    },
    delete: function(provider_pk) {
        sendRequest('provider_delete', { provider_pk });
    },
    list: function() {
        sendRequest('provider_list');
    }
};
