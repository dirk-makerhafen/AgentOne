// API functions for tools/builtin_a2a/consumers/permissions.py
const a2aPermissionsApi = {
    set: function(instance_pk, target_instance_pk, can_send, can_receive) {
        sendRequest('a2a_permission_set', { instance_pk, target_instance_pk, can_send, can_receive });
    },
    list: function(instance_pk) {
        sendRequest('a2a_permission_list', { instance_pk });
    }
};
