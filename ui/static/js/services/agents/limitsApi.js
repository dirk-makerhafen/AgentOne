// API functions for agents/consumers/limits.py
const limitsApi = {
    reset: function(instance_pk, rule_name) {
        sendRequest('historylimit_reset', { instance_pk, rule_name });
    },
    update: function(instance_pk, rule_name, limits) {
        sendRequest('historylimit_update', { instance_pk, rule_name, limits });
    }
};
