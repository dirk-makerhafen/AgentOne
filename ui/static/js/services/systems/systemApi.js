// API functions for systems/consumers/system.py
const systemApi = {
    create: function(name) {
        sendRequest('system_create', { name });
    },
    update: function(system_pk, data) {
        sendRequest('system_update', { system_pk, data });
    },
    list: function() {
        sendRequest('system_list');
    }
};
