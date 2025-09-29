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

    const html = agentTemplate(agentData);
    const existingElement = document.getElementById(`agent_${agentData.id}`);
    if (existingElement) {
        existingElement.outerHTML = html;
    } else {
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
    closeAgentMenu(agentId);

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
    event.stopPropagation(); // Prevent the click from propagating to parent elements, which might close the menu immediately
    const menu = document.getElementById(menuId);
    if (menu) {
        // Toggle display of the specific menu
        if (menu.style.display === 'block') {
            menu.style.display = 'none';
        } else {
            // Close all other open menus first, regardless of which parent they belong to
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
    closeAgentMenu(agentId);
    
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

function createAgent(event){
    event.preventDefault();
    const agentName = prompt("Please enter a name for the new agent:");
    if (agentName && agentName.trim() !== '') {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'create_agent',
                payload: {
                    name: agentName.trim()
                }
            }));
        } else {
            alert("Cannot create agent. WebSocket is not connected.");
        }
    }
}
