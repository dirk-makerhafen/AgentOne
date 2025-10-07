// This file manages the rendering and interaction for a single agent instance in the sidebar.

function renderAgentInstance(payload) {
    const agentInstanceTemplate = getTemplate('SidebarInstancesListItemTemplate'); // Corrected template ID
    const instanceContainer = document.getElementById(`agent-instances-${payload.agent_id}`);
    if (!instanceContainer) return;

    const existingInstance = document.getElementById(`agent_instance_${payload.id}`);
    
    // Ensure payload has necessary fields for rendering
    const dataForTemplate = {
        id: payload.id,
        agent_id: payload.agent_id,
        name: payload.name || `Instance ${payload.id}`,
        status: payload.status,
        status_display: payload.status_display,
        model_name: payload.model_name,
        system_name: payload.system_name || 'Unassigned',
        isSelected: (window.currentAgentInstancePk === payload.id)
    };

    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = agentInstanceTemplate(dataForTemplate);
    const newElement = tempDiv.firstElementChild;

    if (existingInstance) {
        existingInstance.replaceWith(newElement);
    } else {
        instanceContainer.appendChild(newElement);
    }

    // Update status bar in the main tab content if the tab is open
    updateAgentInstanceStatusBar(payload.id, payload);
}

/**
 * Handles the click event on an agent instance in the sidebar.
 * This function acts as a dispatcher, calling the main tab logic function.
 * @param {Event} event The click event.
 * @param {number} instancePk The primary key of the agent instance.
 * @param {string} instanceName The name of the agent instance.
 */
function selectAgentInstance(event, instancePk, instanceName) {
    event.stopPropagation();
    event.preventDefault();
    
    // Call the core logic function located in TabInstance.js
    selectAgentInstanceTab(instancePk, instanceName);
}
