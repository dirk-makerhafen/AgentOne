// Renders and manages the "Events" tab on the Agent edit page.

function renderAgentEvents(agentPk, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const template = getTemplate('TabAgent_EventsTemplate');
    container.innerHTML = template({ agent: { pk: agentPk } });

    // Initial data fetch
    agentEventsApi.listReceivers(agentPk);
    agentEventsApi.listAssignments(agentPk);
}

function renderAgentEventReceiversList(agentPk, receivers) {
    const container = document.getElementById(`agent-event-receivers-list_${agentPk}`);
    if (!container) return;
    const template = getTemplate('TabAgent_EventReceiverTemplate');
    container.innerHTML = template({ receivers: receivers, agent_pk: agentPk });
}

function renderAgentEventSubscriptionsList(agentPk, assignments) {
    const container = document.getElementById(`agent-event-assignments-list_${agentPk}`);
    if (!container) return;
    const template = getTemplate('TabAgent_EventSubscriptionTemplate');
    container.innerHTML = template({ assignments: assignments, agent_pk: agentPk });
}


function renderAgentEventReceiverForm(agentPk, receiver = {}) {
    const container = document.getElementById(`agent-event-receiver-form-container_${agentPk}`);
    if (!container) return;
    
    const template = getTemplate('TabAgent_EventReceiverFormTemplate');
    container.innerHTML = template({ agent_pk: agentPk, receiver: receiver });
    container.style.display = 'block';

    const formContainer = container.querySelector(`#event-receiver-form-${agentPk}`);
    const saveBtn = formContainer.querySelector(`#save-receiver-btn-${agentPk}`);
    
    saveBtn.onclick = (event) => {
        event.preventDefault();

        const data = {
            id: formContainer.querySelector('input[name="id"]').value,
            name: formContainer.querySelector('input[name="name"]').value,
            description: formContainer.querySelector('textarea[name="description"]').value,
            event: formContainer.querySelector('select[name="event"]').value,
            source: formContainer.querySelector('textarea[name="source"]').value,
            is_public: formContainer.querySelector('input[name="is_public"]').checked,
            enabled: formContainer.querySelector('input[name="enabled"]').checked
        };

        if (data.id) {
            agentEventsApi.updateReceiver(data.id, data);
        } else {
            agentEventsApi.createReceiver(agentPk, data);
        }
        closeAgentEventReceiverForm(agentPk);
    };
}

function closeAgentEventReceiverForm(agentPk) {
    const container = document.getElementById(`agent-event-receiver-form-container_${agentPk}`);
    if (container) {
        container.innerHTML = '';
        container.style.display = 'none';
    }
}

function renderAgentEventSubscriptionForm(agentPk, assignment = {}, publicReceivers = []) {
    const container = document.getElementById(`agent-event-assignment-form-container_${agentPk}`);
    if (!container) return;

    const template = getTemplate('TabAgent_EventSubscriptionFormTemplate');
    container.innerHTML = template({ agent_pk: agentPk, assignment: assignment, publicReceivers: publicReceivers });
    container.style.display = 'block';

    const formContainer = container.querySelector(`#event-assignment-form-${agentPk}`);
    const saveBtn = formContainer.querySelector(`#save-assignment-btn-${agentPk}`);

    saveBtn.onclick = (event) => {
        event.preventDefault();
        
        const data = {
            id: formContainer.querySelector('input[name="id"]').value,
            description: formContainer.querySelector('textarea[name="description"]').value,
            eventHandler_id: formContainer.querySelector('select[name="eventHandler_id"]').value
        };
        
        if (data.id) {
            agentEventsApi.updateAssignment(data.id, data);
        } else {
            agentEventsApi.createAssignment(agentPk, data);
        }
        closeAgentEventSubscriptionForm(agentPk);
    };

    if (!assignment.id) {
        agentEventsApi.listPublicReceivers(); // Fetch public receivers for the dropdown
    }
}

function closeAgentEventSubscriptionForm(agentPk) {
    const container = document.getElementById(`agent-event-assignment-form-container_${agentPk}`);
    if (container) {
        container.innerHTML = '';
        container.style.display = 'none';
    }
}

// Handler for when we receive a single receiver (e.g., for editing)
function handleAgentEventReceiver(receiver) {
    renderAgentEventReceiverForm(receiver.agent.pk, receiver);
}

// Handler for when we receive a single assignment (e.g., for editing)
function handleAgentEventSubscription(assignment, publicReceivers = []) {
     renderAgentEventSubscriptionForm(assignment.agent.pk, assignment, publicReceivers);
}

// Handler for the list of public receivers for the assignment form dropdown
function handlePublicEventReceiverList(receivers) {
    const formContainer = document.querySelector('[id^="agent-event-assignment-form-container_"]');
    if (formContainer) {
        const agentPk = formContainer.id.split('_').pop();
        const select = formContainer.querySelector('select[name="eventHandler_id"]');
        if (select) {
            select.innerHTML = receivers.map(r => `<option value="${r.id}">${r.name} (by ${r.agent ? r.agent.name : 'instance'})</option>`).join('');
        }
    }
}
