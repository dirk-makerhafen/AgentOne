// API functions for core/consumers/prompts.py
const promptsApi = {
    createVariant: function(base_variant_pk, agent_id = null) {
        const payload = { base_variant_pk };
        if (agent_id) {
            payload.agent_id = agent_id;
        }
        sendRequest('prompt_variant_create', payload);
    },
    update: function(prompt_pk, value, is_enabled) {
        const payload = { prompt_pk };
        if (value !== undefined) {
            payload.value = value;
        }
        if (is_enabled !== undefined) {
            payload.is_enabled = is_enabled;
        }
        sendRequest('prompt_update', payload);
    },
    delete: function(prompt_pk) {
        sendRequest('prompt_delete', { prompt_pk });
    },
    list: function(agent_id = null) {
        const payload = {};
        if (agent_id) {
            payload.agent_id = agent_id;
        }
        sendRequest('prompt_list', payload);
    },
    getVariants: function(prompt_pk) {
        sendRequest('prompt_get_variants', { prompt_pk });
    }
};