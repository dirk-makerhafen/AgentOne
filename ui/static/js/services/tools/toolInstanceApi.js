// API functions for tools/instances/consumers/tool_instance.py
const toolInstanceApi = {
    create: function(name, endpoint_url) {
        sendRequest('mcpserver_create', { name, endpoint_url });
    },
    update: function(id, name, endpoint_url, enabled) {
        sendRequest('mcpserver_update', { id, name, endpoint_url, enabled });
    },
    delete: function(id) {
        sendRequest('mcpserver_delete', { id });
    },
    list: function() {
        sendRequest('mcpserver_list');
    },
    refreshTools: function(id) {
        sendRequest('mcpserver_tools_refresh', { id });
    }
};
