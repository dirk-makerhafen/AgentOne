// API functions for tools/builtin_memory/consumers/memory.py
const memoryApi = {
    update: function(instance_pk, track, layer, index, content) {
        sendRequest('memoryitem_update', { instance_pk, track, layer, index, content });
    },
    list: function(instance_pk) {
        sendRequest('memoryitem_list', { instance_pk });
    }
};
