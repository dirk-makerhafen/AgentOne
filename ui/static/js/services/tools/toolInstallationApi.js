// API functions for tools/definitions/consumers/tool_installation.py
const toolInstallationApi = {
    create: function(tool_definition_pk, system_pk) {
        sendRequest('toolinstallation_create', { tool_definition_pk, system_pk });
    },
    getLogs: function(installation_id) {
        sendRequest('toolinstallation_get_logs', { installation_id });
    },
    delete: function(installation_pk) {
        sendRequest('toolinstallation_delete', { installation_pk });
    },
    list: function(system_pk = null) {
        sendRequest('toolinstallation_list', { system_pk });
    },
    start: function(installation_pk) {
        sendRequest('toolinstallation_start', { installation_pk });
    },
    stop: function(installation_pk) {
        sendRequest('toolinstallation_stop', { installation_pk });
    }
};
