// This file manages the rendering and interaction for a single agent instance in the sidebar.

function renderAgentInstance(payload) {
    const existingInstance = document.getElementById(`agent_instance_${payload.id}`);

    if (existingInstance && existingInstance.classList.contains('tree-leaf-instance')) {
        // --- Context-Aware Update for Tree View ---
        // This is a minimal update to avoid replacing the whole node and breaking the tree structure.
        const statusElement = existingInstance.querySelector('.instance-status');
        if (statusElement) {
            // Remove old status classes
            statusElement.className = 'instance-status'; 
            statusElement.classList.add(`instance-status-${payload.status}`);
            statusElement.textContent = payload.status_display;
        }
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

function switchInstanceView(viewType) {
    // Deactivate all buttons
    document.getElementById('view-by-agent-btn').classList.remove('active');
    document.getElementById('view-by-dir-btn').classList.remove('active');
    document.getElementById('view-by-fork-btn').classList.remove('active');

    // Activate the selected button
    document.getElementById(`view-by-${viewType}-btn`).classList.add('active');

    // Clear the current list
    const agentListContainer = document.getElementById('agents-list-body');
    agentListContainer.innerHTML = '';

    // Call the appropriate API
    if (viewType === 'agent') {
        renderAgentTreeView();
    } else if (viewType === 'dir') {
        instanceViewApi.getByWorkingDirectory();
    } else if (viewType === 'fork') {
        instanceViewApi.getByFork();
    }
}


// Register the recursive templates as partials
const hierarchyTreeNodeTemplate = getTemplate('SidebarInstanceHierarchyTreeViewNodeTemplate');
Handlebars.registerPartial('SidebarInstanceHierarchyTreeViewNodeTemplate', hierarchyTreeNodeTemplate);
const directoryTreeNodeTemplate = getTemplate('SidebarInstanceDirectoryTreeViewNodeTemplate');
Handlebars.registerPartial('SidebarInstanceDirectoryTreeViewNodeTemplate', directoryTreeNodeTemplate);

function renderInstanceView(payload) {
    const agentListContainer = document.getElementById('agents-list-body');
    agentListContainer.innerHTML = ''; // Clear previous content

    let finalHtml = '';
    // If a common base path is provided for the directory view, display it.
    if (payload.common_base_path) {
        finalHtml += `<div class="common-base-path-container">
                        <span class="base-path-label">Base:</span>
                        <span class="base-path-value">${payload.common_base_path}</span>
                      </div>`;
    }

    let treeHtml;
    if (payload.view_type === 'fork') {
        const hierarchyTemplate = getTemplate('SidebarInstanceHierarchyTreeViewNodeTemplate');
        treeHtml = hierarchyTemplate({ nodes: payload.data });
    } else { // Default to directory view
        const directoryTemplate = getTemplate('SidebarInstanceDirectoryTreeViewNodeTemplate');
        treeHtml = directoryTemplate({ nodes: payload.data });
    }
    
    finalHtml += treeHtml;
    agentListContainer.innerHTML = finalHtml;

    // After rendering, update the selection status of any visible instances
    if (window.currentAgentInstancePk) {
        const selectedInstance = document.getElementById(`agent_instance_${window.currentAgentInstancePk}`);
        if (selectedInstance) {
            selectedInstance.classList.add('selected-instance');
        }
    }
}

function toggleTreeNode(event) {
    event.stopPropagation();
    const triggerElement = event.currentTarget;
    const childrenContainer = triggerElement.closest('li').querySelector('.tree-node-children');

    if (!childrenContainer) return;

    const isHidden = childrenContainer.style.display === 'none' || childrenContainer.style.display === '';
    childrenContainer.style.display = isHidden ? 'block' : 'none';

    // Handle icon changes
    let icon;
    if (triggerElement.classList.contains('tree-node-toggle')) {
        // Hierarchy view: trigger is the icon itself
        icon = triggerElement;
        icon.classList.toggle('fa-caret-right', !isHidden);
        icon.classList.toggle('fa-caret-down', isHidden);
    } else if (triggerElement.classList.contains('tree-node-header')) {
        // Directory view: trigger is the header, icon is inside
        icon = triggerElement.querySelector('.tree-node-icon');
        if (icon) {
            icon.classList.toggle('fa-folder', !isHidden);
            icon.classList.toggle('fa-folder-open', isHidden);
        }
    }
}


function deselectAgentInstance(instancePk) {
    const selected = document.getElementById(`agent_instance_${instancePk}`)
    if (selected) {
        selected.classList.remove('selected-instance');
    }
    window.currentAgentInstancePk = null;
}




function requestAgentInstanceDeletion(event, instanceId, instanceName) {
    event.preventDefault();
    event.stopPropagation();
    if (confirm(`Are you sure you want to delete instance "${instanceName}"?`)) {
        agentInstanceApi.delete(instanceId);
    }
}
