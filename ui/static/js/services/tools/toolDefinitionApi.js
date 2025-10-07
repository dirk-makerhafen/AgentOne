// API functions for tools/definitions/consumers/tool_definition.py
const toolDefinitionApi = {
    create: function(data) {
        sendRequest('tooldefinition_create', data);
    },
    update: function(tool_definition_id, updates) {
        sendRequest('tooldefinition_update', { tool_definition_id, updates });
    },
    delete: function(tool_definition_id) {
        sendRequest('tooldefinition_delete', { tool_definition_id });
    },
    list: function() {
        sendRequest('tooldefinition_list');
    },
    refreshManifest: function(tool_definition_id) {
        sendRequest('tooldefinition_manifest_refresh', { tool_definition_id });
    },
    assignSystem: function(tool_definition_id, system_id) {
        sendRequest('tooldefinition_system_assign', { tool_definition_id, system_id });
    },
    unassignSystem: function(tool_definition_id, system_id) {
        sendRequest('tooldefinition_system_unassign', { tool_definition_id, system_id });
    }
};
