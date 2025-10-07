
const agentInstanceSidebarTemplate = Handlebars.compile(`
<div id="agent_instance_{{id}}" class="sidebar-instance {{#if isSelected}}selected-instance{{/if}}" 
     data-agent-id="{{agent_id}}" data-instance-id="{{id}}" onclick="event.preventDefault(); selectAgentInstance({{id}})">
    <div class="sidebar-instance-header" >
        <p><strong>{{name}}</strong> <span class="instance-status instance-status-{{status}}">{{status_display}}</span></p>
        <div class="agent-header-controls">
            <div class="agent-actions-menu" onmouseleave="closeAgentMenu(event, 'agent-instance-menu-{{id}}')">
                <button class="btn btn-xs btn-default burgerbtn" onclick="event.stopPropagation(); toggleAgentMenu(event, 'agent-instance-menu-{{id}}')" title="Agent Instance Actions">
                    <i class="fa fa-bars"></i>
                </button>
                <div id="agent-instance-menu-{{id}}" class="agent-menu-dropdown" style="display: none;">
                    <a href="#" onclick="event.stopPropagation(); requestAgentInstanceDeletion('{{id}}', '{{name}}')">Delete Instance</a>
                </div>
            </div>
        </div>
    </div>
    <p class="nomargin"><span style="font-weight:500">{{model_name}}</span> on <span style="font-weight:500">{{system_name}}</span></p>
    <p class="nomargin hidden">Status: <span class="instance-status instance-status-{{status}}">{{status_display}}</span></p>
</div>`);

function renderAgentInstance(payload) {
    const agentId = payload.agent_id;
    const instanceId = payload.id;

    renderAgentInstanceHeader(payload, payload.id);
    renderSidebarSettings(payload, payload.id);
    renderSidebarFilesystemHeader(payload); // Also update the FS header on instance updates.

    // --- Instance-Specific Agent Status Bar Logic ---
    const instanceTabContent = document.getElementById(`tabContent_agentInstance_${payload.id}`);
    if (instanceTabContent) {
        const statusBar = instanceTabContent.querySelector(`#agent-status-bar_${payload.id}`);
        const statusText = instanceTabContent.querySelector(`#agent-status-text_${payload.id}`);

        if (statusBar && statusText) {
            statusText.textContent = payload.status_display;
            const statusClasses = ['status-bg-THINKING', 'status-bg-EXECUTING_TOOLS', 'status-bg-AWAITING_USER_INPUT', 'status-bg-AWAITING_AGENT_MESSAGE', 'status-bg-IDLE', 'status-bg-COMPLETED', 'status-bg-FAILED', 'status-bg-READY'];
            statusBar.classList.remove(...statusClasses);
            statusBar.classList.add(`status-bg-${payload.status}`);
            statusBar.classList.remove('agent-status-bar-hidden');
        }
    }



    // --- Sidebar Rendering Logic ---
    const parentContainerId = `agent-instances-${agentId}`;
    const parentContainer = document.getElementById(parentContainerId);

    if (!parentContainer) {
        console.warn(`Parent container ${parentContainerId} not found for instance ${instanceId}. Agent might not be rendered yet.`);
        return;
    }

    let instanceElement = document.getElementById(`agent_instance_${instanceId}`);

    const newInstanceElement = document.createElement('div');
    newInstanceElement.innerHTML = agentInstanceSidebarTemplate({
        id: instanceId,
        agent_id: agentId,
        name: payload.name || `Instance ${instanceId}`,
        status: payload.status,
        status_display: payload.status_display,
        model_name: payload.model_name,
        system_name: payload.system_name || 'Unassigned',
        isSelected: (currentAgentInstancePk == instanceId)
    }).trim();

    if (instanceElement) {
        instanceElement.replaceWith(newInstanceElement.firstChild);
    } else {
        parentContainer.appendChild(newInstanceElement.firstChild);
    }

    // Update the corresponding tab button's name if the tab is currently open
    const tabButton = document.getElementById(`tabButton_agentInstance_${instanceId}`);
    if (tabButton) {
        const spanElement = tabButton.querySelector('span');
        if (spanElement) {
            spanElement.textContent = payload.name || `Instance ${instanceId}`;
        }
    }
}

// Overwrite the globally available selectAgentInstance function
function selectAgentInstance(instancePk, targetPanelId = null) {
    // Determine the target panel for the new tab.
    if (!targetPanelId) {
        targetPanelId = 'mainTabPanel'; // Default to main panel
    }
    const targetPanel = document.getElementById(targetPanelId);
    if (!targetPanel) {
        console.error('Target panel ' + targetPanelId + ' not found.');
        return;
    }

    const tabButtonId = 'tabButton_agentInstance_' + instancePk;
    const tabContentId = 'tabContent_agentInstance_' + instancePk;

    let existingTabButton = document.getElementById(tabButtonId);
    let tabAlreadyExists = !!existingTabButton;

    // This variable now ONLY tracks the visually active tab for UI purposes (e.g., highlighting).
    // It is NOT used for data routing.
    window.currentAgentInstancePk = instancePk;

    // Update the 'selected-instance' class on the sidebar for visual feedback
    document.querySelectorAll('.sidebar-instance').forEach(el => el.classList.remove('selected-instance'));
    const sidebarItem = document.getElementById(`agent_instance_${instancePk}`);
    if (sidebarItem) {
        sidebarItem.classList.add('selected-instance');
    }

    if (tabAlreadyExists) {
        // If tab exists, just activate it. Find its current parent panel to activate it in place.
        const existingParentPanelId = existingTabButton.closest('.resizable-panel.flex-column').id;
        openMainTab(null, tabContentId, existingParentPanelId);
    } else {
        // If tab does not exist, create it, subscribe, and load its history.
        //console.log('Creating new tab for instance ' + instancePk + ' in panel ' + targetPanelId);

        // 1. Create tab button
        const newTabButton = document.createElement('button');
        newTabButton.id = tabButtonId;
        newTabButton.className = 'tab-button';
        newTabButton.setAttribute('data-tab-id', tabButtonId);
        newTabButton.setAttribute('data-tab-content-id', tabContentId);
        newTabButton.setAttribute('draggable', 'true');
        newTabButton.setAttribute('ondragstart', `dragTab(event, '${tabButtonId}', '${tabContentId}')`);
        // The onclick now also updates the global currentAgentInstancePk for UI focus
        newTabButton.setAttribute('onclick', `openMainTab(event, '${tabContentId}', '${targetPanelId}'); window.currentAgentInstancePk = ${instancePk};`);
        const instanceNameElement = sidebarItem ? sidebarItem.querySelector('p strong') : null;
        const instanceName = instanceNameElement ? instanceNameElement.textContent : `Instance ${instancePk}`;
        newTabButton.innerHTML = `<span>${instanceName}</span><i class="fa fa-times close-tab-btn" onclick="event.stopPropagation(); closeMainTab('${tabContentId}');"></i>`;

        // 2. Append tab button to target panel's tab bar
        const targetTabBar = targetPanel.querySelector('.tab-bar');
        const splitControlsContainer = targetTabBar ? targetTabBar.querySelector('.split-controls-container') : null;
        if (targetTabBar && splitControlsContainer) {
            targetTabBar.insertBefore(newTabButton, splitControlsContainer);
        } else if (targetTabBar) {
            targetTabBar.appendChild(newTabButton);
        }

        // 3. Create and append tab content
        renderAgentInstanceTabContent(instancePk, targetPanelId);

        // 4. Activate the newly created tab
        openMainTab(null, tabContentId, targetPanelId);

        // 5. Initialize instance-specific components & state
        initializeLogFilterControlsForInstance(instancePk);
        attachInstanceEventListeners(instancePk);
        const instanceLogState = getInstanceLogState(instancePk);
        instanceLogState.hasMoreHistory = true;
        instanceLogState.isLoadingHistory = false;

        // 6. Subscribe and load initial data *ONLY ON CREATION*
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            // Subscribe to live updates
            websocket.send(JSON.stringify({ type: 'subscribe', payload: { instance_pk: instancePk } }));
            addToConsoleArea(`Client: Sent "subscribe" for instance ${instancePk}`, 'client-status');
            
            // Load initial history
            websocket.send(JSON.stringify({ type: 'load_history', payload: { instance_pk: instancePk, limit: 20 } }));
            addToConsoleArea(`Client: Sent "load_history" for instance ${instancePk}`, 'info');

            // Request full details for headers, settings, etc.
            websocket.send(JSON.stringify({ type: 'request_instance_details', payload: { instance_pk: instancePk } }));
            addToConsoleArea(`Client: Requesting details for instance ${instancePk}`, 'client-status');
        } else {
            addToConsoleArea(`Cannot subscribe/load for instance ${instancePk}. WebSocket not open.`, 'warning');
        }
    }
};

function attachInstanceEventListeners(instancePk) {
    const messageInput = document.getElementById('messageInput_' + instancePk);
    const sendMessageBtn = document.getElementById('sendMessageBtn_' + instancePk);

    if (sendMessageBtn) {
        sendMessageBtn.addEventListener('click', function() {
            const message = messageInput.value.trim();
            if (!instancePk) {
                addToConsoleArea("No agent instance selected. Please select an agent from the sidebar.", 'warning');
                return;
            }
            if (websocket && websocket.readyState === WebSocket.OPEN) {
                websocket.send(JSON.stringify({
                    type: 'user_input',
                    payload: { 
                        message: message,
                        instance_pk: instancePk
                    }
                }));
                messageInput.value = '';
            } else {
                addToConsoleArea("WebSocket not connected. Message not sent.", 'error');
            }
        });
    }

    if (messageInput) {
        messageInput.addEventListener('keydown', function(event) {
            // Keep the default behavior of allowing newlines with Enter for the textarea.
            // Sending is handled only by the button click.
        });
    }

    if (sendMessageBtn) {
        sendMessageBtn.addEventListener('keydown', function(event) {
            // Prevent accidental sending when button is focused and Enter is pressed.
            if (event.key === 'Enter') {
                event.preventDefault(); // Stop the default button click behavior
                event.stopPropagation(); // Stop event from bubbling up
                addToConsoleArea("Client: Message not sent. Please click the 'Send' button or press enter in the text area to add newlines.", 'info');
            }
        });
    }
};


// --- Log Area Filtering ---

// This function needs to be called when a new instance tab is opened,
// targeting its specific logArea and filter controls.
function initializeLogFilterControlsForInstance(instancePk) {
    const logAreaContainer = document.getElementById(`logArea_${instancePk}`);
    if (!logAreaContainer) {
        console.error(`logAreaContainer for instance ${instancePk} not found for filter controls.`);
        return;
    }

    let filterControls = logAreaContainer.querySelector('.log-filter-controls');
    if (!filterControls) {
        // Create the filter controls container if it doesn't exist
        filterControls = document.createElement('div');
        filterControls.id = `log-filter-controls_${instancePk}`; // Make ID instance-specific
        filterControls.classList.add('log-filter-container');
        // Prepend it to the log area so it's the first child, allowing it to be sticky
        logAreaContainer.prepend(filterControls);
    }

    // Populate the controls container.
    filterControls.innerHTML = `
        <button class="log-filter-btn" data-log-type="conversation" title="Toggle User/Agent Messages"><i class="fa fa-comments-o"></i></button>
        <button class="log-filter-btn" data-log-type="tool" title="Toggle Tool Calls & Responses"><i class="fa fa-wrench"></i></button>
        <button class="log-filter-btn" data-log-type="fs" title="Toggle Filesystem Logs"><i class="fa fa-folder-open-o"></i></button>
        <button class="log-filter-btn" data-log-type="llm" title="Toggle LLM Queries/Responses"><i class="fa fa-cogs"></i></button>
        <button class="log-filter-btn" data-log-type="debug" title="Toggle Debug Logs"><i class="fa fa-bug"></i></button>
        <button class="log-filter-btn" data-log-type="pyvar" title="Toggle VARS Updates"><i class="fa fa-code"></i></button>
    `;

    // Re-query buttons and attach listeners
    filterControls.querySelectorAll('.log-filter-btn').forEach(button => {
        const logType = button.dataset.logType;
        
        // Sync button's appearance with the log area's current state
        if (logAreaContainer.classList.contains(`hide-${logType}`)) {
            button.classList.remove('active');
        } else {
            button.classList.add('active');
        }

        button.onclick = (event) => {
            event.preventDefault();
            if (!logType) return;
            button.classList.toggle('active');
            logAreaContainer.classList.toggle(`hide-${logType}`);
        };
        
    });
}

function requestAgentInstanceDeletion(instancePk, instanceName) {
    if (confirm(`Are you sure you want to delete agent instance "${instanceName}" (ID: ${instancePk})? This action cannot be undone.`)) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'delete_agent_instance',
                payload: {
                    instance_pk: instancePk
                }
            }));
            addToConsoleArea(`Client: Requesting deletion of agent instance ${instancePk}.`, 'info');
        } else {
            addToConsoleArea("WebSocket not connected. Cannot request agent instance deletion.", 'error');
        }
    } else {
        addToConsoleArea(`Client: Deletion of agent instance ${instancePk} cancelled.`, 'info');
    }
    closeMainTab(`tabContent_agentInstance_${instancePk}`)

}
