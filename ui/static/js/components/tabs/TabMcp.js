// This file manages the rendering and interactions for the MCP Server list tab.

let mcpServerListTemplate;
let mcpServerModalTemplate; // Template for the MCP Server modal

function initializeMcpTemplates() {
    mcpServerListTemplate = getTemplate('mcp-server-list-template'); // Assuming this template is still correct
    mcpServerModalTemplate = getTemplate('TabMcpServerModal'); // Get the modal template
}

function renderMcpList(mcpServers, containerElement) {
    if (!containerElement) {
        console.error("renderMcpList: containerElement is required.");
        return;
    }

    if (!mcpServerListTemplate) {
        initializeMcpTemplates();
    }
    const mcpListBody = containerElement.querySelector('#mcp-list-body');
    if (mcpListBody && mcpServerListTemplate) {
        // Handlebars expects an array for #each, even if it's just one server for rendering
        mcpListBody.innerHTML = mcpServerListTemplate({mcp_servers: mcpServers});
        attachMcpEventListeners(containerElement); // Pass the container for scoped event listening
    }
}

function attachMcpEventListeners(container) {
    // Ensure all event listeners are attached to elements *within* the provided container
    // Remove previous listeners to prevent duplicates
    container.removeEventListener('click', handleMcpClick);
    container.addEventListener('click', handleMcpClick);

    // Attach specific listeners for modal buttons
    const mcpServerModal = container.querySelector('#mcpServerModal');
    if (mcpServerModal) {
        mcpServerModal.querySelector('.close-button').onclick = () => closeMcpServerModal(container);
        mcpServerModal.querySelector('.btn-secondary').onclick = () => closeMcpServerModal(container);
        mcpServerModal.querySelector('#saveMcpServerBtn').onclick = () => saveMcpServer(container);
    }
}

function handleMcpClick(event) {
    const target = event.target;
    const mcpServerItem = target.closest('.mcp-server-item');
    const mainContainer = target.closest('#tabContent_mcp'); // The main tab container

    let serverId = null;
    if (mcpServerItem) {
        serverId = mcpServerItem.dataset.id;
    }

    // Add Server Button (in the header of the tab)
    if (target.closest('#add-mcp-server-btn')) {
        openMcpServerModalForCreate(mainContainer);
        return;
    }

    // Toggle Tools
    if (target.closest('.toggle-tools-btn')) {
        const detailsDiv = target.closest('.mcp-server-item').querySelector('.mcp-server-tools');
        if (detailsDiv) {
            if (detailsDiv.style.display === 'none') {
                detailsDiv.style.display = 'block';
                target.closest('.toggle-tools-btn').innerHTML = '<i class="fa fa-chevron-up"></i>';
            } else {
                detailsDiv.style.display = 'none';
                target.closest('.toggle-tools-btn').innerHTML = '<i class="fa fa-chevron-down"></i>';
            }
        }
        return;
    }

    // Edit Server Button
    if (target.closest('.edit-mcp-server-btn') && serverId) {
        // Fetch the current server data (e.g., from a global store or re-request from backend)
        // For now, we'll try to extract from DOM or assume list is recent
        const serverName = mcpServerItem.querySelector('.mcp-server-name').textContent;
        const endpointUrl = mcpServerItem.querySelector('.endpoint-url').textContent;
        openMcpServerModalForEdit(serverId, serverName, endpointUrl, mainContainer);
        return;
    }

    // Delete Server Button
    if (target.closest('.delete-mcp-server-btn') && serverId) {
        if (confirm('Are you sure you want to delete this MCP server configuration?')) {
            sendWebSocketMessage('delete_mcp_server', { id: parseInt(serverId) });
        }
        return;
    }

    // Refresh Tools Button
    if (target.closest('.refresh-mcp-server-btn') && serverId) {
        sendWebSocketMessage('refresh_mcp_server_tools', { id: parseInt(serverId) });
        return;
    }
}


// Modal functions, now accepting containerElement for scoped access
function openMcpServerModalForCreate(containerElement) {
    const modal = containerElement.querySelector('#mcpServerModal');
    if (!modal) { addToClientLog("MCP Server Modal not found within container.", 'error'); return; }
    
    modal.querySelector('#mcpServerModalTitle').textContent = 'Add MCP Server';
    modal.querySelector('#mcpServerId').value = '';
    modal.querySelector('#mcpServerName').value = '';
    modal.querySelector('#mcpServerEndpoint').value = '';
    modal.querySelector('#mcpServerEnabled').checked = true; // Default to enabled
    modal.style.display = 'block';
}

function openMcpServerModalForEdit(id, name, endpoint, containerElement) {
    const modal = containerElement.querySelector('#mcpServerModal');
    if (!modal) { addToClientLog("MCP Server Modal not found within container.", 'error'); return; }

    modal.querySelector('#mcpServerModalTitle').textContent = 'Edit MCP Server';
    modal.querySelector('#mcpServerId').value = id;
    modal.querySelector('#mcpServerName').value = name;
    modal.querySelector('#mcpServerEndpoint').value = endpoint;
    // For 'enabled' state, if we don't have it, we'd ideally fetch it.
    // For now, assume it remains as is unless explicitly toggled in future UI.
    // Or, more robustly, fetch entire object for edit.
    modal.style.display = 'block';
}

function closeMcpServerModal(containerElement) {
    const modal = containerElement.querySelector('#mcpServerModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function saveMcpServer(containerElement) {
    const modal = containerElement.querySelector('#mcpServerModal');
    const serverId = modal.querySelector('#mcpServerId').value;
    const name = modal.querySelector('#mcpServerName').value;
    const endpoint_url = modal.querySelector('#mcpServerEndpoint').value;
    const enabled = modal.querySelector('#mcpServerEnabled').checked;

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
    closeMcpServerModal(containerElement);
}

function sendWebSocketMessage(type, payload) {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: type, payload: payload }));
    } else {
        console.error("WebSocket is not connected.");
        addToClientLog("WebSocket is not connected. Please refresh the page.", 'error');
    }
}

// This function will be called by openMainTab when 'MCP' tab is opened
function requestMcpList() {
    sendWebSocketMessage('list_mcp_servers', {});
}


function renderSingleMcpServer(serverData, containerElement) {
    if (!mcpServerListTemplate) {
        initializeMcpTemplates();
        if (!mcpServerListTemplate) {
            addToClientLog("MCP Server template not available for single render.", 'error');
            return;
        }
    }

    const mcpListBody = containerElement.querySelector('#mcp-list-body');
    if (!mcpListBody) return;

    // Render the single item using the existing template by wrapping it in an array for #each
    const newItemHtml = mcpServerListTemplate({mcp_servers: [serverData]});

    const existingItem = mcpListBody.querySelector(`.mcp-server-item[data-id="${serverData.id}"]`);

    if (existingItem) {
        // Item exists, replace it to reflect updates
        existingItem.outerHTML = newItemHtml;
    } else {
        // Item is new, append it
        mcpListBody.insertAdjacentHTML('beforeend', newItemHtml);
    }
    
    // Re-attach listeners for the new/updated element
    // This is crucial because outerHTML replacement removes event listeners
    attachMcpEventListeners(containerElement); // Re-attach all listeners, but specifically target the updated element if possible
}

// Entry point for opening the MCP tab
function openMcpTab(targetPanelId = 'mainTabPanel') {
    const tabContentId = `tabContent_mcp`;
    const tabButtonId = `tabButton_mcp`;
    let existingTabButton = document.getElementById(tabButtonId);
    let existingTabContent = document.getElementById(tabContentId);

    // If tab content already exists, just activate it
    if (existingTabContent) {
        // Ensure its button exists, if not, recreate it (e.g., after a drag-drop to another panel)
        if (!existingTabButton) {
            const targetPanel = document.getElementById(targetPanelId);
            const targetTabBar = targetPanel ? targetPanel.querySelector('.tab-bar') : null;
            if (targetTabBar) {
                existingTabButton = document.createElement('button');
                existingTabButton.id = tabButtonId;
                existingTabButton.className = 'tab-button';
                existingTabButton.dataset.tabId = tabButtonId;
                existingTabButton.dataset.tabContentId = tabContentId;
                existingTabButton.setAttribute('draggable', 'true');
                existingTabButton.ondragstart = (event) => dragTab(event, tabButtonId, tabContentId);
                existingTabButton.innerHTML = `
                    <span>MCP</span>
                    <i class="fa fa-times close-tab-btn" onclick="event.stopPropagation(); closeMainTab('${tabContentId}')"></i>
                `;
                existingTabButton.setAttribute('onclick', `openMainTab(event, '${tabContentId}', '${targetPanelId}')`);
                const splitControlsContainer = targetTabBar.querySelector('.split-controls-container');
                if (splitControlsContainer) {
                    targetTabBar.insertBefore(existingTabButton, splitControlsContainer);
                } else {
                    targetTabBar.appendChild(existingTabButton);
                }
            }
        }
        openMainTab(null, tabContentId, targetPanelId);
        return;
    }

    const targetPanel = document.getElementById(targetPanelId);
    if (!targetPanel) {
        addToClientLog(`Target panel ${targetPanelId} not found for creating MCP tab.`, 'error');
        return;
    }

    const tabMcpTemplate = getTemplate('TabMcpTemplate'); // Main tab template
    const tabContentHtml = tabMcpTemplate({}); 

    // 1. Create tab button (only if it doesn't exist, which it shouldn't at this point)
    const newTabButton = document.createElement('button');
    newTabButton.id = tabButtonId;
    newTabButton.className = 'tab-button';
    newTabButton.dataset.tabId = tabButtonId;
    newTabButton.dataset.tabContentId = tabContentId;
    newTabButton.setAttribute('draggable', 'true');
    newTabButton.ondragstart = (event) => dragTab(event, tabButtonId, tabContentId);
    newTabButton.innerHTML = `
        <span>MCP</span>
        <i class="fa fa-times close-tab-btn" onclick="event.stopPropagation(); closeMainTab('${tabContentId}')"></i>
    `;
    newTabButton.setAttribute('onclick', `openMainTab(event, '${tabContentId}', '${targetPanelId}')`);

    // 2. Append tab button to target panel's tab bar
    const targetTabBar = targetPanel.querySelector('.tab-bar');
    const splitControlsContainer = targetTabBar ? targetTabBar.querySelector('.split-controls-container') : null;
    if (targetTabBar && splitControlsContainer) {
        targetTabBar.insertBefore(newTabButton, splitControlsContainer);
    } else if (targetTabBar) {
        targetTabBar.appendChild(newTabButton);
    }

    // 3. Create and append main tab content
    targetPanel.insertAdjacentHTML('beforeend', tabContentHtml);

    // After creating the main tab content, append the modal HTML to it
    const newTabContentElement = document.getElementById(tabContentId);
    if (newTabContentElement) {
        if (!mcpServerModalTemplate) { initializeMcpTemplates(); } // Ensure modal template is loaded
        newTabContentElement.insertAdjacentHTML('beforeend', mcpServerModalTemplate({}));
    }

    // 4. Activate the newly created tab
    openMainTab(null, tabContentId, targetPanelId);

    // Re-attach all event listeners for the newly rendered tab, including modals
    attachMcpEventListeners(newTabContentElement);

    // 5. Request MCP list data (initial load)
    requestMcpList();

    addToClientLog(`Client: Opened MCP tab.`, 'info');
}