let mcpServerListTemplate;

function initializeMcpTemplates() {
    if (Handlebars.templates && Handlebars.templates['mcp-server-list-template']) {
        mcpServerListTemplate = Handlebars.templates['mcp-server-list-template'];
    } else {
        const templateElement = document.getElementById('mcp-server-list-template');
        if (templateElement) {
            mcpServerListTemplate = Handlebars.compile(templateElement.innerHTML);
            if (!Handlebars.templates) {
                Handlebars.templates = {};
            }
            Handlebars.templates['mcp-server-list-template'] = mcpServerListTemplate;
        } else {
            console.error("MCP Server List Handlebars template not found.");
        }
    }
}

function renderMcpList(mcpServers) {
    if (!mcpServerListTemplate) {
        initializeMcpTemplates();
    }
    const mcpListBody = document.getElementById('mcp-list-body');
    if (mcpListBody && mcpServerListTemplate) {
        mcpListBody.innerHTML = mcpServerListTemplate(mcpServers);
        attachMcpEventListeners();
    }
}

function attachMcpEventListeners() {
    // Add Server Button
    const addMcpServerBtn = document.getElementById('add-mcp-server-btn');
    if (addMcpServerBtn) {
        addMcpServerBtn.onclick = openMcpServerModalForCreate;
    }

    // Toggle Tools
    document.querySelectorAll('.toggle-tools-btn').forEach(button => {
        button.onclick = function() {
            const detailsDiv = this.closest('.mcp-server-item').querySelector('.mcp-server-tools');
            if (detailsDiv) {
                if (detailsDiv.style.display === 'none') {
                    detailsDiv.style.display = 'block';
                    this.innerHTML = '<i class="fa fa-chevron-up"></i>';
                } else {
                    detailsDiv.style.display = 'none';
                    this.innerHTML = '<i class="fa fa-chevron-down"></i>';
                }
            }
        };
    });

    // Edit Server Button
    document.querySelectorAll('.edit-mcp-server-btn').forEach(button => {
        button.onclick = function() {
            const serverItem = this.closest('.mcp-server-item');
            const serverId = serverItem.dataset.id;
            // Fetch the current server data (e.g., from a global store or re-request from backend)
            // For now, we'll try to extract from DOM or assume list is recent
            const serverName = serverItem.querySelector('.mcp-server-name').textContent;
            const endpointUrl = serverItem.querySelector('.endpoint-url').textContent;
            // Assuming 'enabled' state is not easily visible from item HTML,
            // for full fidelity, a list of servers should be maintained in JS or re-fetched.
            // For now, we'll assume default or fetch on edit.
            openMcpServerModalForEdit(serverId, serverName, endpointUrl);
        };
    });

    // Delete Server Button
    document.querySelectorAll('.delete-mcp-server-btn').forEach(button => {
        button.onclick = function() {
            const serverId = this.closest('.mcp-server-item').dataset.id;
            if (confirm('Are you sure you want to delete this MCP server configuration?')) {
                sendWebSocketMessage('delete_mcp_server', { id: parseInt(serverId) });
            }
        };
    });

    // Refresh Tools Button
    document.querySelectorAll('.refresh-mcp-server-btn').forEach(button => {
        button.onclick = function() {
            const serverId = this.closest('.mcp-server-item').dataset.id;
            sendWebSocketMessage('refresh_mcp_server_tools', { id: parseInt(serverId) });
        };
    });
}

// Modal functions
function openMcpServerModalForCreate() {
    const modal = document.getElementById('mcpServerModal');
    document.getElementById('mcpServerModalTitle').textContent = 'Add MCP Server';
    document.getElementById('mcpServerId').value = '';
    document.getElementById('mcpServerName').value = '';
    document.getElementById('mcpServerEndpoint').value = '';
    document.getElementById('mcpServerEnabled').checked = true; // Default to enabled
    document.getElementById('saveMcpServerBtn').onclick = saveMcpServer;
    modal.style.display = 'block';
}

function openMcpServerModalForEdit(id, name, endpoint) {
    const modal = document.getElementById('mcpServerModal');
    document.getElementById('mcpServerModalTitle').textContent = 'Edit MCP Server';
    document.getElementById('mcpServerId').value = id;
    document.getElementById('mcpServerName').value = name;
    document.getElementById('mcpServerEndpoint').value = endpoint;
    // For 'enabled' state, if we don't have it, we'd ideally fetch it.
    // For now, assume it remains as is unless explicitly toggled in future UI.
    // Or, more robustly, fetch entire object for edit.
    document.getElementById('saveMcpServerBtn').onclick = saveMcpServer;
    modal.style.display = 'block';
}

function closeMcpServerModal() {
    document.getElementById('mcpServerModal').style.display = 'none';
}

function saveMcpServer() {
    const serverId = document.getElementById('mcpServerId').value;
    const name = document.getElementById('mcpServerName').value;
    const endpoint_url = document.getElementById('mcpServerEndpoint').value;
    const enabled = document.getElementById('mcpServerEnabled').checked;

    if (!name || !endpoint_url) {
        alert('Server Name and Endpoint URL are required.');
        return;
    }

    const payload = {
        name: name,
        endpoint_url: endpoint_url,
        enabled: enabled
    };

    if (serverId) {
        // Update existing server
        payload.id = parseInt(serverId);
        sendWebSocketMessage('update_mcp_server', payload);
    } else {
        // Create new server
        sendWebSocketMessage('create_mcp_server', payload);
    }
    closeMcpServerModal();
}

function sendWebSocketMessage(type, payload) {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: type, payload: payload }));
    } else {
        console.error("WebSocket is not connected.");
        addToConsoleArea("WebSocket is not connected. Please refresh the page.", 'error');
    }
}

// This function will be called by openMainTab when 'MCP' tab is opened
function requestMcpList() {
    sendWebSocketMessage('list_mcp_servers', {});
}


function renderSingleMcpServer(serverData) {
    if (!mcpServerListTemplate) {
        initializeMcpTemplates();
        if (!mcpServerListTemplate) {
            console.error("MCP Server template not available for single render.");
            return;
        }
    }

    const mcpListBody = document.getElementById('mcp-list-body');
    if (!mcpListBody) return;

    // Render the single item using the existing template by wrapping it in an array
    const newItemHtml = mcpServerListTemplate([serverData]);

    const existingItem = mcpListBody.querySelector(`.mcp-server-item[data-id="${serverData.id}"]`);

    if (existingItem) {
        // Item exists, replace it to reflect updates
        existingItem.outerHTML = newItemHtml;
    } else {
        // Item is new, append it
        mcpListBody.insertAdjacentHTML('beforeend', newItemHtml);
    }
    
    // Re-attach listeners for the new/updated element
    const newItemElement = mcpListBody.querySelector(`.mcp-server-item[data-id="${serverData.id}"]`);
    if (newItemElement) {
        // Attach listener for Toggle Tools
        const toggleBtn = newItemElement.querySelector('.toggle-tools-btn');
        if (toggleBtn) {
            toggleBtn.onclick = function() {
                const detailsDiv = this.closest('.mcp-server-item').querySelector('.mcp-server-tools');
                if (detailsDiv) {
                    detailsDiv.style.display = detailsDiv.style.display === 'none' ? 'block' : 'none';
                    this.innerHTML = detailsDiv.style.display === 'none' ? '<i class="fa fa-chevron-down"></i>' : '<i class="fa fa-chevron-up"></i>';
                }
            };
        }
        // Attach listener for Edit
        const editBtn = newItemElement.querySelector('.edit-mcp-server-btn');
        if (editBtn) {
            editBtn.onclick = function() {
                const serverItem = this.closest('.mcp-server-item');
                openMcpServerModalForEdit(serverItem.dataset.id, serverItem.querySelector('.mcp-server-name').textContent, serverItem.querySelector('.endpoint-url').textContent);
            };
        }
        // Attach listener for Delete
        const deleteBtn = newItemElement.querySelector('.delete-mcp-server-btn');
        if (deleteBtn) {
            deleteBtn.onclick = function() {
                const serverId = this.closest('.mcp-server-item').dataset.id;
                if (confirm('Are you sure you want to delete this MCP server configuration?')) {
                    sendWebSocketMessage('delete_mcp_server', { id: parseInt(serverId) });
                }
            };
        }
        // Attach listener for Refresh
        const refreshBtn = newItemElement.querySelector('.refresh-mcp-server-btn');
        if (refreshBtn) {
            refreshBtn.onclick = function() {
                const serverId = this.closest('.mcp-server-item').dataset.id;
                sendWebSocketMessage('refresh_mcp_server_tools', { id: parseInt(serverId) });
            };
        }
    }
}
