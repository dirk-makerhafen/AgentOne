// Renders and manages the "Events" sidebar tab for an Agent Instance.

function renderInstanceEvents(instancePk) {
    const container = document.getElementById(`sidebar-tab-events_${instancePk}`);
    if (!container) return;

    const template = getTemplate('SidebarInstance_EventsTemplate');
    container.innerHTML = template({ instancePk: instancePk });

    // Initial data fetch
    instanceEventsApi.listReceivers(instancePk);
    instanceEventsApi.listAssignments(instancePk);
}

function renderInstanceEventReceiversList(instancePk, receivers) {
    const container = document.getElementById(`instance-event-receivers-list_${instancePk}`);
    if (!container) return;
    const template = getTemplate('SidebarInstance_EventReceiverTemplate');
    container.innerHTML = template({ receivers: receivers, instance_pk: instancePk });
}

function renderInstanceEventSubscriptionsList(instancePk, assignments) {
    const container = document.getElementById(`instance-event-assignments-list_${instancePk}`);
    if (!container) return;
    const template = getTemplate('SidebarInstance_EventSubscriptionTemplate');
    container.innerHTML = template({ assignments: assignments, instance_pk: instancePk });
}

function renderInstanceEventReceiverForm(instancePk, receiver = {}) {
    const container = document.getElementById(`instance-event-receiver-form-container_${instancePk}`);
    if (!container) return;
    
    const template = getTemplate('SidebarInstance_EventReceiverFormTemplate');
    container.innerHTML = template({ instance_pk: instancePk, receiver: receiver });
    container.style.display = 'block';

    const formContainer = container.querySelector(`#instance-event-receiver-form-${instancePk}`);
    const saveBtn = formContainer.querySelector(`#save-instance-receiver-btn-${instancePk}`);
    
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
            instanceEventsApi.updateReceiver(data.id, data);
        } else {
            instanceEventsApi.createReceiver(instancePk, data);
        }
        closeInstanceEventReceiverForm(instancePk);
    };
}

function closeInstanceEventReceiverForm(instancePk) {
    const container = document.getElementById(`instance-event-receiver-form-container_${instancePk}`);
    if (container) {
        container.innerHTML = '';
        container.style.display = 'none';
    }
}

function renderInstanceEventSubscriptionForm(instancePk, assignment = {}, publicReceivers = []) {
    const container = document.getElementById(`instance-event-assignment-form-container_${instancePk}`);
    if (!container) return;

    const template = getTemplate('SidebarInstance_EventSubscriptionFormTemplate');
    container.innerHTML = template({ instance_pk: instancePk, assignment: assignment, publicReceivers: publicReceivers });
    container.style.display = 'block';

    const formContainer = container.querySelector(`#instance-event-assignment-form-${instancePk}`);
    const saveBtn = formContainer.querySelector(`#save-instance-assignment-btn-${instancePk}`);

    saveBtn.onclick = (event) => {
        event.preventDefault();
        const data = {
            id: formContainer.querySelector('input[name="id"]').value,
            description: formContainer.querySelector('textarea[name="description"]').value,
            eventHandler_id: formContainer.querySelector('select[name="eventHandler_id"]').value
        };
        
        if (data.id) {
            instanceEventsApi.updateAssignment(data.id, data);
        } else {
            instanceEventsApi.createAssignment(instancePk, data);
        }
        closeInstanceEventSubscriptionForm(instancePk);
    };

    if (!assignment.id) {
        instanceEventsApi.listPublicReceivers();
    }
}

function closeInstanceEventSubscriptionForm(instancePk) {
    const container = document.getElementById(`instance-event-assignment-form-container_${instancePk}`);
    if (container) {
        container.innerHTML = '';
        container.style.display = 'none';
    }
}

// Handler for the list of public receivers for the assignment form dropdown
function handlePublicEventReceiverListForInstance(receivers) {
    // This function is slightly more complex as the form could be in any instance tab.
    const formContainer = document.querySelector('[id^="instance-event-assignment-form-container_"]:not(:empty)');
    if (formContainer) {
        const select = formContainer.querySelector('select[name="eventHandler_id"]');
        if (select) {
            select.innerHTML = receivers.map(r => `<option value="${r.id}">${r.name} (by ${r.agent ? r.agent.name : 'instance'})</option>`).join('');
        }
    }
}
