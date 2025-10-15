// API functions for agents/consumers/agent.py
const agentApi = {
    create: function(name, description, available_tool_ids, limit_max_conversation_messages, limit_max_memory_items, limit_max_automated_steps) {
        sendRequest('agent_create', { name, description, available_tool_ids, limit_max_conversation_messages, limit_max_memory_items, limit_max_automated_steps });
    },
    update: function(agent_pk, name, description, available_tool_ids, limit_max_conversation_messages, limit_max_memory_items, limit_max_automated_steps) {
        sendRequest('agent_update', { agent_pk, name, description, available_tool_ids, limit_max_conversation_messages, limit_max_memory_items, limit_max_automated_steps });
    },
    delete: function(agent_pk) {
        sendRequest('agent_delete', { agent_pk });
    },
    list: function() {
        sendRequest('agent_list');
    }
};
