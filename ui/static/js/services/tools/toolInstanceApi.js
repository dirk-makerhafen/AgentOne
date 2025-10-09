// API functions for tools/instances/consumers/tool_instance.py
const toolInstanceApi = {
    create: function(name, endpoint_url) {
        sendRequest('toolinstance_create', { name, endpoint_url });
    },
    update: function(id, name, endpoint_url, enabled) {
        sendRequest('toolinstance_update', { id, name, endpoint_url, enabled });
    },
    delete: function(id) {
        sendRequest('toolinstance_delete', { id });
    },
    list: function() {
        sendRequest('toolinstance_list');
    },
    refreshTools: function(id) {
        sendRequest('toolinstance_tools_refresh', { id });
    },
    stop: function(tool_instance_pk) {
        sendRequest('toolinstance_stop', { tool_instance_pk });
    }
};
