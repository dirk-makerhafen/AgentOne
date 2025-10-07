// API functions for agents/consumers/agent.py
const agentApi = {
    create: function(name, description, available_tool_ids) {
        sendRequest('agent_create', { name, description, available_tool_ids });
    },
    update: function(agent_pk, name, description, available_tool_ids) {
        sendRequest('agent_update', { agent_pk, name, description, available_tool_ids });
    },
    delete: function(agent_pk) {
        sendRequest('agent_delete', { agent_pk });
    },
    list: function() {
        sendRequest('agent_list');
    }
};
