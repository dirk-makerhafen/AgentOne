// This file manages the interaction of the "Edit Agent" tab.

let agentUpdateTimers = {};

function agentUpdate(agentId) {
    clearTimeout(agentUpdateTimers[agentId]);
    agentUpdateTimers[agentId] = setTimeout(() => {
        const form = document.getElementById(`edit-agent-form-${agentId}`);
        if (!form) return;
        const name = form.querySelector(`#agent-name-${agentId}`).value;
        const description = form.querySelector(`#agent-description-${agentId}`).value;
        const available_tool_ids = Array.from(form.querySelectorAll('input[name="available_tools"]:checked')).map(cb => cb.value);
        agentApi.update(agentId, name, description, available_tool_ids);
    }, 500);
}

function agentCreateFromTab(event) {
    event.preventDefault();
    event.stopPropagation();
    const form = document.getElementById('add-agent-form-tab');
    if (!form) return;

    const name = form.querySelector('#agent-name-new').value.trim();
    const description = form.querySelector('#agent-description-new').value.trim();
    const availableToolIds = Array.from(form.querySelectorAll('input[name="available_tools"]:checked')).map(cb => parseInt(cb.value));

    if (!name) { 
        alert('Agent name is required.'); 
        return; 
    }
    
    agentApi.create(name, description, availableToolIds);
    closeMainTab('tabContent_add_agent');
}


/**
 * Updates the content of an open "Edit Agent" tab with new agent data.
 * @param {object} updatedAgent The updated agent object from the WebSocket payload.
 */
function updateAgentEditTab(updatedAgent) {
    const agentId = updatedAgent.id;
    const activeTabContent = document.querySelector(`.tab-content.active`);

    // Only update if the tab is currently active and matches the agent ID.
    if (activeTabContent && activeTabContent.id === `tabContent_edit_agent_${agentId}`) {
        // Update timestamp
        const timestampElement = activeTabContent.querySelector(`#last-updated-${agentId}`);
        if (timestampElement) {
            const formattedTimestamp = new Date(updatedAgent.updated_at).toLocaleString();
            timestampElement.textContent = `Last updated: ${formattedTimestamp}`;
        }

        // Update tab button name
        const tabButton = document.querySelector(`#tabButton_edit_agent_${agentId}`);
        if (tabButton) {
            for (let node of tabButton.childNodes) {
                if (node.nodeType === Node.TEXT_NODE) {
                    node.textContent = `Edit: ${updatedAgent.name} `;
                    break;
                }
            }
        }
    }
}