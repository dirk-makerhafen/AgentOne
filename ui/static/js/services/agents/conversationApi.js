// API functions for agents/consumers/conversation.py
const conversationApi = {
    addMessage: function(instance_pk, message) {
        sendRequest('conversationmessage_add', { instance_pk, message });
    },
    listMessages: function(instance_pk, max_id = null, limit = 20) {
        sendRequest('conversationmessage_list', { instance_pk, max_id, limit });
    },
    updateMessageFlags: function(instance_pk, message_id, pin_to_context, hide_from_context) {
        sendRequest('conversationmessage_update_flag', { instance_pk, message_id, pin_to_context, hide_from_context });
    }
};
