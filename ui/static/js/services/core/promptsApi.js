// API functions for core/consumers/prompts.py
const promptsApi = {
    create: function(original_prompt_pk) {
        sendRequest('prompt_create', { original_prompt_pk });
    },
    update: function(prompt_pk, value) {
        sendRequest('prompt_update', { prompt_pk, value });
    },
    delete: function(prompt_pk) {
        sendRequest('prompt_delete', { prompt_pk });
    },
    list: function() {
        sendRequest('prompt_list');
    }
};
