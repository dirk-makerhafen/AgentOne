// This file manages the rendering and interactions for the list of agents in the sidebar.

window.allAgents = window.allAgents || {}; // Initialize or use existing global cache

/**
 * Renders the complete agent tree view.
 * This function rebuilds the entire tree from the global caches, preserving expanded node state.
 */
function renderAgentTreeView() {
    const agentViewButton = document.getElementById('view-by-agent-btn');
    if (!agentViewButton || !agentViewButton.classList.contains('active')) {
        return; // Only render if the agent view is active
    }

    const agentsListBody = document.getElementById('agents-list-body');
    if (!agentsListBody) return;

    // --- State Preservation: Start ---
    const expandedAgentIds = new Set();
    // Find all list items (li) that contain a visible children container
    agentsListBody.querySelectorAll('li').forEach(item => {
        const childrenContainer = item.querySelector('.tree-node-children');
        if (childrenContainer && childrenContainer.style.display === 'block') {
            // Find the agent menu within this list item to get the ID
            const agentMenu = item.querySelector('[id^="agent-menu-"]');
            if (agentMenu) {
                const agentId = agentMenu.id.replace('agent-menu-', '');
                expandedAgentIds.add(agentId);
            }
        }
    });
    // --- State Preservation: End ---

    const agents = Object.values(window.allAgents).sort((a, b) => a.name.localeCompare(b.name));
    const instances = Object.values(window.allAgentInstances);

    const nodes = agents.map(agent => {
        const children = instances
            .filter(inst => inst.agent_id === agent.id)
            .map(inst => ({...inst, isSelected: window.currentAgentInstancePk === inst.id}))
            .sort((a, b) => a.name.localeCompare(b.name));
        return {
            agent: agent,
            children: children
        };
    });
    
    const agentTreeTemplate = getTemplate('SidebarAgentsTreeViewNodeTemplate');
    agentsListBody.innerHTML = agentTreeTemplate({ nodes });

    // --- State Restoration: Start ---
    expandedAgentIds.forEach(agentId => {
        const agentMenu = agentsListBody.querySelector(`#agent-menu-${agentId}`);
        if (agentMenu) {
            const agentNode = agentMenu.closest('li'); // Find the parent <li>
            if(agentNode) {
                const childrenContainer = agentNode.querySelector('.tree-node-children');
                const icon = agentNode.querySelector('.tree-node-header .tree-node-icon');
                if (childrenContainer) {
                    childrenContainer.style.display = 'block';
                }
                if (icon) {
                    icon.classList.remove('fa-folder');
                    icon.classList.add('fa-folder-open');
                }
            }
        }
    });
    // --- State Restoration: End ---

    // After rendering, re-apply selection status to the new elements
    if (window.currentAgentInstancePk) {
        const selectedInstance = document.getElementById(`agent_instance_${window.currentAgentInstancePk}`);
        if (selectedInstance) {
            selectedInstance.classList.add('selected-instance');
        }
    }
}


/**
 * Adds or updates an agent in the global cache and re-renders the entire tree view.
 * @param {object} agentData The agent object from the WebSocket payload.
 */
function addOrUpdateAgentInSidebar(agentData) {
    window.allAgents[agentData.id] = agentData;
    renderAgentTreeView(); // Re-render the whole tree on any update
}

/**
 * Removes an agent from the global cache and its sidebar entry.
 * @param {number} agentPk The primary key of the agent to remove.
 */
function removeAgentFromSidebar(agentPk) {
    delete window.allAgents[agentPk]; // Remove from global cache
    renderAgentTreeView(); // Re-render the whole tree
}

function showAgentMenu(event, menuId) {
    event.preventDefault();
    event.stopPropagation();
    // Hide all other menus first
    document.querySelectorAll('.agent-menu-dropdown').forEach(menu => {
        if (menu.id !== menuId) {
            menu.style.display = 'none';
        }
    });
    const menu = document.getElementById(menuId);
    if (menu) menu.style.display = 'block';
}

function hideAgentMenu(event, menuId) {
    event.preventDefault();
    event.stopPropagation();
    const menu = document.getElementById(menuId);
    if (menu) menu.style.display = 'none';
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
    const agent = window.allAgents[agentId];
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
