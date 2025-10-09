// API functions for tools/builtin_filesystem/consumers/filesystem.py
const filesystemApi = {
    list: function(instance_pk) {
        sendRequest('filesystem_list', { instance_pk });
    },
    getContent: function(instance_pk, log_entry_pk) {
        sendRequest('filesystem_get_filecontent', { instance_pk, log_entry_pk });
    },
    togglePin: function(instance_pk, path) {
        sendRequest('filesystem_update_ispinned', { instance_pk, path });
    },
    undo: function(instance_pk, log_entry_pk, comment = '') {
        sendRequest('filesystem_undo', { instance_pk, log_entry_pk, comment });
    },
    undoAll: function(instance_pk, log_entry_pk, comment = '') {
        sendRequest('filesystem_undo_all', { instance_pk, log_entry_pk, comment });
    }
};
