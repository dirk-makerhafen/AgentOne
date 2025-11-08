// API client for Agent Event Receivers and Assignments

const agentEventsApi = {
    listReceivers(agentPk) {
        sendRequest('agentevents_receiver_list', { agent_pk: agentPk });
    },
    getReceiver(receiverId) {
        sendRequest('agentevents_receiver_get', { receiver_id: receiverId });
    },
    createReceiver(agentPk, data) {
        sendRequest('agentevents_receiver_create', { agent_pk: agentPk, data: data });
    },
    updateReceiver(receiverId, data) {
        sendRequest('agentevents_receiver_update', { receiver_id: receiverId, data: data });
    },
    deleteReceiver(receiverId) {
        if (confirm('Are you sure you want to delete this event receiver?')) {
            sendRequest('agentevents_receiver_delete', { receiver_id: receiverId });
        }
    },
    listAssignments(agentPk) {
        sendRequest('agentevents_assignment_list', { agent_pk: agentPk });
    },
    getAssignment(assignmentId) {
        sendRequest('agentevents_assignment_get', { assignment_id: assignmentId });
    },
    createAssignment(agentPk, data) {
        sendRequest('agentevents_assignment_create', { agent_pk: agentPk, data: data });
    },
    updateAssignment(assignmentId, data) {
        sendRequest('agentevents_assignment_update', { assignment_id: assignmentId, data: data });
    },
    deleteAssignment(assignmentId) {
        if (confirm('Are you sure you want to delete this event assignment?')) {
            sendRequest('agentevents_assignment_delete', { assignment_id: assignmentId });
        }
    },
    listPublicReceivers() {
        sendRequest('agentevents_receiver_list_public', {});
    }
};
