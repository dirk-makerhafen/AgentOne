// API functions for tools/calls/consumers/direct_tool_call.py
const directToolCallApi = {
    call: function(instance_pk, tool_calls) {
        sendRequest('toolcall_direct', { instance_pk, tool_calls });
    }
};
