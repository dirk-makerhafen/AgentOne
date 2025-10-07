const agentTemplate = Handlebars.compile(`
<div id="agent_{{id}}" class="sidebar-agent-item">
    <div class="sidebar-agent-header">
        <h5 class="sidebar-agent-name">
            <a href="#" onclick="event.preventDefault(); toggleAgentInstances('{{id}}')">{{name}} (ID: {{id}})</a>
        </h5>
        <div class="agent-header-controls">
            <div class="agent-actions-menu" onmouseleave="closeAgentMenu('agent-menu-{{id}}')">
                <button class="btn btn-xs btn-default" onclick="toggleAgentMenu(event, 'agent-menu-{{id}}')" title="Agent Actions">
                    <i class="fa fa-bars"></i>
                </button>
                <div id="agent-menu-{{id}}" class="agent-menu-dropdown" style="display: none;">
                    <a href="#" onclick="event.preventDefault(); createAgentInstance(event, '{{id}}')">Add Instance</a>
                    <a href="#" onclick="event.preventDefault(); openAgentEditTab({{id}})">Edit Agent</a>
                    <a href="#" onclick="event.preventDefault(); requestAgentDeletion(event, '{{id}}', '{{name}}')">Delete Agent</a>
                </div>
            </div>
        </div>
    </div>
    <div id="agent-instances-{{id}}" class="sidebar-instance-list" style="display: none;">
        <!-- Instances will be dynamically added here -->
    </div>
</div>`);

function renderAgent(agentData) {
    const container = document.getElementById('agents-list-body');
    if (!container) {
        console.error("Could not find agents-list-body container to render agent into.");
        return;
    }

    const existingAgentItem = document.getElementById(`agent_${agentData.id}`);

    if (existingAgentItem) {
        // Update existing agent item in-place to preserve child elements like instance list
        const agentNameElement = existingAgentItem.querySelector('.sidebar-agent-name a');
        if (agentNameElement) {
            agentNameElement.textContent = `${agentData.name} (ID: ${agentData.id})`;
        }
        // If needed, update the menu button's onclick to ensure event handlers are fresh.
        // For now, the current setup of toggleAgentMenu and closeAgentMenu uses IDs directly
        // so re-binding isn't strictly necessary if the menu structure/IDs don't change.
        // If the agent name is part of the menu button's innerHTML, it would also need updating here.
    } else {
        // If agent doesn't exist, append the new item as before
        const html = agentTemplate(agentData);
        container.insertAdjacentHTML('beforeend', html);
    }
}

function toggleAgentInstances(agentId) {
    const instancesDiv = document.getElementById(`agent-instances-${agentId}`);
    if (instancesDiv) {
        instancesDiv.style.display = instancesDiv.style.display === 'none' ? 'block' : 'none';
    }
}

function createAgentInstance(event, agentId) {
    event.stopPropagation();
    closeAgentMenu(`agent-menu-${agentId}`); // Pass the correct menu ID

    if (websocket && websocket.readyState === WebSocket.OPEN) {
        // Find the instance list and expand it so the user sees the new instance appear.
        const instancesDiv = document.getElementById(`agent-instances-${agentId}`);
        if (instancesDiv && instancesDiv.style.display === 'none') {
            instancesDiv.style.display = 'block';
        }
        
        websocket.send(JSON.stringify({
            type: 'create_agent_instance',
            payload: {
                agent_pk: agentId
            }
        }));
    } else {
        alert("Cannot create instance. WebSocket is not connected.");
    }
}

function toggleAgentMenu(event, menuId) {
    event.stopPropagation();
    const menu = document.getElementById(menuId);
    if (menu) {
        if (menu.style.display === 'block') {
            menu.style.display = 'none';
        } else {
            document.querySelectorAll('.agent-menu-dropdown').forEach(openMenu => {
                if (openMenu.id !== menuId) {
                    openMenu.style.display = 'none';
                }
            });
            menu.style.display = 'block';
        }
    }
}

function closeAgentMenu(menuId) {
    const menu = document.getElementById(menuId);
    if (menu) {
        menu.style.display = 'none';
    }
}

function requestAgentDeletion(event, agentId, agentName) {
    event.stopPropagation();
    closeAgentMenu(`agent-menu-${agentId}`); // Pass the correct menu ID
    
    if (confirm(`Are you sure you want to permanently delete the agent "${agentName}" (ID: ${agentId}) and all of its instances? This action cannot be undone.`)) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'delete_agent',
                payload: {
                    agent_pk: agentId
                }
            }));
        } else {
            alert("Cannot delete agent. WebSocket is not connected.");
        }
    }
}

// New functions for Agent Modal
function openAddAgentModal() {
    $('#agentModalTitle').text('Add New Agent');
    $('#agentId').val('');
    $('#agentName').val('');
    $('#agentDescription').val('');
    populateToolDefinitions([]); // No tools selected for new agent
    $('#saveAgentBtn').off('click').on('click', saveAgent); // Rebind to prevent multiple handlers
    $('#agentModal').show();
}

function openEditAgentModal(agentId) {
    const agent = websocket.object_cache['Agent'][agentId];
    if (!agent) {
        addToConsoleArea('Agent not found in cache for editing: ' + agentId, 'error');
        return;
    }

    $('#agentModalTitle').text('Edit Agent');
    $('#agentId').val(agent.id);
    $('#agentName').val(agent.name);
    $('#agentDescription').val(agent.description);
    populateToolDefinitions(agent.available_tools || []); // Populate with current tools
    $('#saveAgentBtn').off('click').on('click', saveAgent); // Rebind
    $('#agentModal').show();
}

function closeAgentModal() {
    $('#agentModal').hide();
    $('#agentForm')[0].reset(); // Reset form fields
}

function populateToolDefinitions(selectedToolIds = []) {
    const toolSelect = $('#agentAvailableTools');
    toolSelect.empty(); // Clear existing options

    const toolDefinitions = window.allToolDefinitions || {};
    const sortedToolDefs = Object.values(toolDefinitions).sort((a, b) => a.name.localeCompare(b.name));

    sortedToolDefs.forEach(toolDef => {
        const option = $('<option></option>')
            .val(toolDef.id)
            .text(`${toolDef.name} (${toolDef.is_builtin ? 'Built-in' : 'External'})`);
        if (selectedToolIds.includes(toolDef.id)) {
            option.prop('selected', true);
        }
        toolSelect.append(option);
    });
}

function saveAgent() {
    const agentId = $('#agentId').val();
    const name = $('#agentName').val();
    const description = $('#agentDescription').val();
    const selectedToolIds = $('#agentAvailableTools').val() || []; // Array of selected tool IDs

    if (!name.trim()) {
        alert('Agent Name cannot be empty.');
        return;
    }

    const payload = {
        name: name.trim(),
        description: description,
        available_tool_ids: selectedToolIds
    };

    if (agentId) {
        // Update existing agent
        payload.agent_pk = agentId;
        websocket.send(JSON.stringify({
            type: 'update_agent',
            payload: payload
        }));
    } else {
        // Create new agent
        websocket.send(JSON.stringify({
            type: 'create_agent',
            payload: payload
        }));
    }
    closeAgentModal();
}

// Bind the "Add New Agent" button in dashboard.html to openAddAgentModal
$(document).ready(function() {
    $('#add-agent-btn').off('click').on('click', function(event) {
        event.preventDefault();
        openAddAgentModal();
    });
});
