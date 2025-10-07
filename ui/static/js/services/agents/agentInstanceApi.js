// API functions for agents/consumers/agent_instance.py
const agentInstanceApi = {
    create: function(agent_pk) {
        sendRequest('agentinstance_create', { agent_pk });
    },
    get: function(instance_pk) {
        sendRequest('agentinstance_get', { instance_pk });
    },
    getVars: function(instance_pk) {
        sendRequest('agentinstance_get_vars', { instance_pk });
    },
    update: function(instance_pk, data) {
        sendRequest('agentinstance_update', { instance_pk, data });
    },
    delete: function(instance_pk) {
        sendRequest('agentinstance_delete', { instance_pk });
    }
};
