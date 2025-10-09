// This file manages the rendering and interactions for the list of agents in the sidebar.

window.allAgents = window.allAgents || {}; // Initialize or use existing global cache
let agentListTemplate;
let addAgentFormTemplate;

function initializeAgentListTemplates() {
    agentListTemplate = getTemplate('SidebarAgentsListItemTemplate');
    addAgentFormTemplate = getTemplate('SidebarAgentsAddAgentTemplate');
}

/**
 * Adds or updates an agent in the global cache and re-renders its sidebar entry.
 * @param {object} agentData The agent object from the WebSocket payload.
 */
/**
 * Renders or updates an agent's entry in the sidebar and updates the global cache.
 * @param {object} agentData The agent object.
 */
/**
 * Renders or updates an agent's entry in the sidebar and updates the global cache.
 * @param {object} agentData The agent object.
 */
function addOrUpdateAgentInSidebar(agentData) {
    if (!agentListTemplate) initializeAgentListTemplates();
    const agentsListBody = document.getElementById('agents-list-body');
    if (!agentsListBody) return;

    window.allAgents[agentData.id] = agentData; // Update global cache

    // Calculate instance counts for this agent
    const instancesForAgent = Object.values(window.allAgentInstances).filter(
        instance => instance.agent_id === agentData.id
    );
    const totalInstances = instancesForAgent.length;
    const runningInstances = instancesForAgent.filter(
        instance => ['running', 'starting'].includes(instance.status.toLowerCase())
    ).length;

    // Determine initial chevron icon state
    const existingAgentElement = document.getElementById(`agent_${agentData.id}`);
    let chevronIcon = 'right'; // Default to collapsed
    if (existingAgentElement) {
        const instancesContainer = existingAgentElement.querySelector('.sidebar-instance-list');
        if (instancesContainer && instancesContainer.style.display === 'block') {
            chevronIcon = 'down'; // If already expanded, keep it expanded
        }
    }

    const context = {
        ...agentData,
        total_instances: totalInstances,
        running_instances: runningInstances,
        chevron_icon: chevronIcon
    };

    const newAgentElementHtml = agentListTemplate(context);

    if (existingAgentElement) {
        // Create a temporary element to parse the new HTML
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = newAgentElementHtml;
        const newHeader = tempDiv.querySelector('.sidebar-agent-header');
        const newInstanceListContainer = tempDiv.querySelector('.sidebar-instance-list'); // This is the empty container from template

        const existingHeader = existingAgentElement.querySelector('.sidebar-agent-header');
        const existingInstanceListContainer = existingAgentElement.querySelector('.sidebar-instance-list');

        if (existingHeader) {
            // Replace the header content, but keep the existing instance list container
            existingHeader.replaceWith(newHeader);
        } else {
            // If header is missing, something is very wrong, but try to append.
            existingAgentElement.prepend(newHeader);
        }
        
        // Critically, DO NOT replace existingInstanceListContainer.
        // Its children (the actual instances) are managed by renderAgentInstance.
        // We only ensure the main agent element's data attributes and id are correct.
        existingAgentElement.id = `agent_${agentData.id}`;
        existingAgentElement.dataset.agentId = agentData.id;

    } else {
        const addFormContainer = document.getElementById('add-agent-form-container');
        if (addFormContainer) {
            addFormContainer.insertAdjacentHTML('afterend', newAgentElementHtml);
        } else {
            agentsListBody.innerHTML += newAgentElementHtml;
        }
    }
}

/**
 * Removes an agent from the global cache and its sidebar entry.
 * @param {number} agentPk The primary key of the agent to remove.
 */
function removeAgentFromSidebar(agentPk) {
    const agentElement = document.getElementById(`agent_${agentPk}`);
    if (agentElement) agentElement.remove();
    delete window.allAgents[agentPk]; // Remove from global cache
}


function showAgentMenu(event, menuId) {
    event.preventDefault();
    event.stopPropagation();
    const menu = document.getElementById(menuId);
    if (menu) menu.style.display = 'block';
}
function hideAgentMenu(event, menuId) {
    event.preventDefault();
    event.stopPropagation();
    const menu = document.getElementById(menuId);
    if (menu) menu.style.display = 'none'
}


function toggleAgentInstances(event, agentId) {
    event.preventDefault();
    event.stopPropagation();
    const instancesContainer = document.querySelector(`#agent_${agentId} .sidebar-instance-list`);
    const toggleIcon = document.querySelector(`#agent_${agentId} .toggle-instances-icon`);

    if (instancesContainer) {
        const isHidden = instancesContainer.style.display === 'none' || instancesContainer.style.display === '';
        instancesContainer.style.display = isHidden ? 'block' : 'none';

        if (toggleIcon) {
            toggleIcon.classList.toggle('fa-chevron-right', !isHidden);
            toggleIcon.classList.toggle('fa-chevron-down', isHidden);
        }
    }
}

function showAddAgentForm(event) {
    event.preventDefault();
    event.stopPropagation();
    const tabAgentTemplate = getTemplate('TabAgentTemplate');
    
    const allTools = Object.values(window.allToolDefinitions || {});
    // For a new agent, no tools are selected by default.
    const toolsForTemplate = allTools.map(tool => ({ ...tool, isSelected: false }));

    const context = {
        agent: { is_new: true, name: '', description: '' },
        tools: toolsForTemplate
    };

    const tabContentHtml = tabAgentTemplate(context);
    const tabId = 'tabContent_add_agent';
    const tabName = 'Create Agent';
    openMainTab(null, tabId, 'mainTabPanel', tabName, tabContentHtml);
}

function createAgentInstance(event, agentId) {
    event.preventDefault();
    event.stopPropagation();
    agentInstanceApi.create(agentId);
}

function requestAgentDeletion(event, agentId, agentName) {
    event.preventDefault();
    event.stopPropagation();
    if (confirm(`Are you sure you want to delete agent "${agentName}" and all its instances?`)) {
        agentApi.delete(agentId);
    }
}

function openAgentEditTab(event, agentId) {
    event?.preventDefault();
    event?.stopPropagation();
    const tabAgentTemplate = getTemplate('TabAgentTemplate');
    const agent = window.allAgents[agentId]; // Now correctly pulls from the updated global cache
    if (!agent) { 
        console.error(`Agent with ID ${agentId} not found in cache.`);
        return;
    }

    const allTools = Object.values(window.allToolDefinitions || {});
    const selectedToolIds = new Set(agent.available_tools || []);
    const toolsForTemplate = allTools.map(tool => ({ ...tool, isSelected: selectedToolIds.has(tool.id) }));

    const context = { agent: { ...agent, updated_at_formatted: new Date(agent.updated_at).toLocaleString() }, tools: toolsForTemplate };
    const tabContentHtml = tabAgentTemplate(context);
    const tabId = `tabContent_edit_agent_${agentId}`;
    const tabName = `Edit: ${agent.name}`;
    openMainTab(null, tabId, 'mainTabPanel', tabName, tabContentHtml);
}
