// API functions for core/consumers/prompts.py
const promptsApi = {
    create: function(source, key, value, description, data_lambda) {
        const payload = { source, key, value, description, data_lambda };
        sendRequest('prompt_create', payload);
    },
    updateDefinition: function(prompt_pk, description, data_lambda) {
        const payload = { prompt_pk };
        if (description !== undefined) payload.description = description;
        if (data_lambda !== undefined) payload.data_lambda = data_lambda;
        sendRequest('prompt_update', payload);
    },
    createVariant: function(base_variant_pk) {
        const payload = { base_variant_pk };
        sendRequest('prompt_variant_create', payload);
    },
    update: function(prompt_variant_pk, value, is_enabled) {
        const payload = { prompt_variant_pk };
        if (value !== undefined) {
            payload.value = value;
        }
        if (is_enabled !== undefined) {
            payload.is_enabled = is_enabled;
        }
        sendRequest('prompt_variant_update', payload);
    },
    delete: function(prompt_pk) {
        sendRequest('prompt_delete', { prompt_pk });
    },
    deleteVariant: function(prompt_variant_pk) {
        sendRequest('prompt_variant_delete', { prompt_variant_pk });
    },
    list: function() {
        // Always request the global list of latest prompt variants.
        // The frontend will be responsible for any filtering.
        sendRequest('prompt_list', {});
    },
    getVariants: function(prompt_pk) {
        sendRequest('prompt_variant_list', { prompt_pk });
    },
    getRelations: function(agent_id) {
        sendRequest('agent_prompt_relation_list', { agent_id });
    }
};    