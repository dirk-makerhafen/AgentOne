// This file manages the rendering and interactions for the list of agents in the sidebar.

window.agentCache = window.agentCache || {}; // Global cache for agents
let agentListTemplate; // Handlebars template for agent list item
let addAgentFormTemplate; // Handlebars template for the add agent form


function initializeAgentListTemplates() {
    agentListTemplate = getTemplate('SidebarAgentsListItemTemplate');
    addAgentFormTemplate = getTemplate('SidebarAgentsAddAgentTemplate');
}

function renderAgent(agentData) {
    if (!agentListTemplate) {
        initializeAgentListTemplates();
    }
    const agentsListBody = document.getElementById('agents-list-body');
    if (!agentsListBody) return;

    const existingAgentElement = document.getElementById(`agent_${agentData.id}`);
    const newAgentElementHtml = agentListTemplate(agentData);

    if (existingAgentElement) {
        // Replace existing element to update all its content
        existingAgentElement.outerHTML = newAgentElementHtml;
    } else {
        // Append new element after the add-agent-form-container
        const addFormContainer = document.getElementById('add-agent-form-container');
        if (addFormContainer) {
            addFormContainer.insertAdjacentHTML('afterend', newAgentElementHtml);
        } else {
            agentsListBody.innerHTML += newAgentElementHtml; // Fallback if container is missing
        }
    }
    window.agentCache[agentData.id] = agentData; // Update cache
}



function toggleAgentMenu(event, menuId) {
    event.preventDefault();
    event.stopPropagation();
    const menu = document.getElementById(menuId);
    if (menu) {
        menu.style.display = (menu.style.display === 'block') ? 'none' : 'block';
    }
}

function closeAgentMenu(event, menuId) {
    event.preventDefault();
    event.stopPropagation();
    const menu = document.getElementById(menuId);
    if (menu) {
        menu.style.display = 'none';
    }
}

function toggleAgentInstances(event, agentId) {
    event.preventDefault();
    event.stopPropagation();
    const agentElement = document.getElementById(`agent_${agentId}`);
    if (agentElement) {
        const instancesContainer = agentElement.querySelector('.sidebar-instance-list');
        const toggleLink = agentElement.querySelector('.sidebar-agent-name a'); // Assuming the link itself handles the toggle
        const toggleIcon = toggleLink ? toggleLink.querySelector('i') : null; // If an icon is desired
        if (instancesContainer && toggleLink) {
            const isHidden = instancesContainer.style.display === 'none' || instancesContainer.style.display === '';
            instancesContainer.style.display = isHidden ? 'block' : 'none';
            if (toggleIcon) {
                toggleIcon.className = isHidden ? 'fa fa-chevron-up' : 'fa fa-chevron-down'; // Update icon if it exists
            }
        }
    }
}

function showAddAgentForm(event) {
    event.preventDefault();
    event.stopPropagation();
    if (!addAgentFormTemplate) {
        initializeAgentListTemplates();
    }
    const addFormContainer = document.getElementById('add-agent-form-container');
    if (!addFormContainer) {
        console.error("Add agent form container not found.");
        return;
    }
    
    // Clear previous content and render the form
    addFormContainer.innerHTML = addAgentFormTemplate({ tools: Object.values(window.allToolDefinitions || {}) });
    addFormContainer.style.display = 'block';

    // Get the add agent button from the main sidebar and hide it
    const addAgentBtn = document.getElementById('add-agent-btn');
    if (addAgentBtn) {
        addAgentBtn.style.display = 'none';
    }
    addToClientLog(`Client: Showing add agent form.`, 'info');
}

function hideAddAgentForm(event) {
    event.preventDefault();
    event.stopPropagation();
    const addFormContainer = document.getElementById('add-agent-form-container');
    if (addFormContainer) {
        addFormContainer.style.display = 'none';
    }

    // Show the add agent button again
    const addAgentBtn = document.getElementById('add-agent-btn');
    if (addAgentBtn) {
        addAgentBtn.style.display = 'block';
    }
    addToClientLog(`Client: Hiding add agent form.`, 'info');
}

function createAgentFromForm(event) {
    event.preventDefault();
    event.stopPropagation();
    const addFormContainer = document.getElementById('add-agent-form-container');
    const nameInput = addFormContainer.querySelector('#new-agent-name');
    const descriptionInput = addFormContainer.querySelector('#new-agent-description');
    const toolCheckboxes = addFormContainer.querySelectorAll('input[name="available_tools"]:checked');

    const name = nameInput.value.trim();
    const description = descriptionInput.value.trim();
    const availableToolIds = Array.from(toolCheckboxes).map(cb => parseInt(cb.value));

    if (!name) {
        alert('Agent name is required.');
        addToClientLog('Agent name is required.', 'warning');
        return;
    }

    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'create_agent',
            payload: {
                name: name,
                description: description,
                available_tool_ids: availableToolIds
            }
        }));
        hideAddAgentForm(); // Hide form on successful send
        addToClientLog(`Client: Requesting creation of new agent "${name}".`, 'info');
    } else {
        addToClientLog("WebSocket not connected. Cannot create agent.", 'error');
    }
}


function createAgentInstance(event, agentId) {
    event.preventDefault();
    event.stopPropagation();
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: 'create_agent_instance', payload: { agent_pk: parseInt(agentId) } }));
        addToClientLog(`Client: Requesting creation of agent instance for agent ${agentId}.`, 'info');
    } else {
        addToClientLog("WebSocket not connected. Cannot create agent instance.", 'error');
    }
}

function requestAgentDeletion(event, agentId, agentName) {
    event.preventDefault();
    event.stopPropagation();
    if (confirm(`Are you sure you want to delete agent "${agentName}" and all its instances?`)) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({ type: 'delete_agent', payload: { agent_pk: parseInt(agentId) } }));
            addToClientLog(`Client: Requesting deletion of agent ${agentId} ("${agentName}").`, 'info');
        } else {
            addToClientLog("WebSocket not connected. Cannot delete agent.", 'error');
        }
    } else {
        addToClientLog(`Client: Deletion of agent ${agentId} cancelled.`, 'info');
    }
}

function openAgentEditTab(event, agentId) {
    event.preventDefault();
    event.stopPropagation();
    const tabAgentTemplate = getTemplate('TabAgentTemplate');
    const agent = window.allAgents[agentId];
    if (!agent) {
        console.error(`Agent with ID ${agentId} not found in cache.`);
        return;
    }

    // Prepare tool data with selection status
    const allTools = Object.values(window.allToolDefinitions || {});
    const selectedToolIds = new Set(agent.available_tools || []);
    const toolsForTemplate = allTools.map(tool => ({
        ...tool,
        isSelected: selectedToolIds.has(tool.id)
    }));

    const context = {
        agent: {
            ...agent,
            updated_at_formatted: new Date(agent.updated_at).toLocaleString()
        },
        tools: toolsForTemplate
    };

    const tabContentHtml = tabAgentTemplate(context);
    const tabId = `tabContent_edit_agent_${agentId}`;
    const tabName = `Edit: ${agent.name}`;
    
    // This function will need to be created in a central place, for now it's assumed to exist
    openMainTab(null, tabId, 'mainTabPanel', tabName, tabContentHtml);

}




function requestAgentList() {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: 'request_agent_list', payload: {} }));
        addToClientLog("Client: Requesting agent list.", 'info');
    } else {
        addToClientLog("WebSocket not connected. Cannot request agent list.", 'error');
    }
}



// Expose globally for use by other scripts, e.g., websocket.js and ui.html
window.initializeAgentListTemplates = initializeAgentListTemplates;
window.renderAgent = renderAgent;
window.requestAgentList = requestAgentList;
window.toggleAgentMenu = toggleAgentMenu;
window.closeAgentMenu = closeAgentMenu;
window.createAgentFromForm = createAgentFromForm; // Expose for the form's onclick
window.hideAddAgentForm = hideAddAgentForm; // Expose for the form's onclick