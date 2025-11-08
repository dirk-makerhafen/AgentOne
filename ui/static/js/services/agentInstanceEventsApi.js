// API for interacting with Agent Instance Events (Receivers and Assignments)

const instanceEventsApi = {
    listReceivers(instancePk) {
        sendRequest('agentinstance_events_receiver_list', { instance_pk: instancePk });
    },

    createReceiver(instancePk, data) {
        sendRequest('agentinstance_events_receiver_create', { instance_pk: instancePk, ...data });
    },

    updateReceiver(receiverId, data) {
        sendRequest('agentinstance_events_receiver_update', { receiver_id: receiverId, ...data });
    },

    deleteReceiver(receiverId) {
        sendRequest('agentinstance_events_receiver_delete', { receiver_id: receiverId });
    },

    listAssignments(instancePk) {
        sendRequest('agentinstance_events_assignment_list', { instance_pk: instancePk });
    },

    createAssignment(instancePk, data) {
        sendRequest('agentinstance_events_assignment_create', { instance_pk: instancePk, ...data });
    },

    updateAssignment(assignmentId, data) {
        sendRequest('agentinstance_events_assignment_update', { assignment_id: assignmentId, ...data });
    },

    deleteAssignment(assignmentId) {
        sendRequest('agentinstance_events_assignment_delete', { assignment_id: assignmentId });
    },

    listPublicReceivers() {
        // This can reuse the existing agent-level public receiver list
        sendRequest('agentevents_public_receiver_list');
    }
};
