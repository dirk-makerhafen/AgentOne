// This file manages the rendering and interaction of the main tab content for an agent instance.

/**
 * Renders the main tab content for a given agent instance.
 * This function is responsible for the overall layout and initial rendering of the tab.
 * It also attaches core event listeners and initializes sub-components.
 * @param {number} instancePk The primary key of the agent instance.
 * @param {string} parentPanelId The ID of the panel where the tab content will be appended.
 */
function renderAgentInstanceTabContent(instancePk, parentPanelId) {
    const agentInstanceTabContentTemplate = getTemplate('TabInstanceTemplate');
    const container = document.getElementById(parentPanelId);
    const tabContentId = `tabContent_agentInstance_${instancePk}`;
    
    // If tab content already exists, just return. This ensures idempotency.
    if (document.getElementById(tabContentId)) {
        return; 
    }

    const html = agentInstanceTabContentTemplate({ instancePk: instancePk });
    container.insertAdjacentHTML('beforeend', html);
    
    const newTabContentElement = document.getElementById(tabContentId);

    // Initialize resizable components within the new tab content
    if (newTabContentElement && typeof initializeSplitForContainer === 'function') {
        initializeSplitForContainer(newTabContentElement);
    }
    
 

    // Initialize log filter controls for this instance
    initializeLogFilterControlsForInstance(instancePk, newTabContentElement);

    // Default to showing the filesystem tab
    showSidebarTabForInstance('filesystem', 
        newTabContentElement.querySelector(`#sidebar-right_${instancePk} .sidebar-tab-btn[data-tab-name="filesystem"]`), 
        instancePk
    );

    // Attach the scroll listener to the new logArea for lazy loading history
    const newLogArea = newTabContentElement.querySelector(`#logArea_${instancePk}`);
    if (newLogArea && typeof attachLogAreaScrollListener === 'function') {
        attachLogAreaScrollListener(newLogArea, instancePk);
    } else {
        console.warn(`[renderAgentInstanceTabContent] Failed to attach scroll listener for instance ${instancePk}.`);
    }
}

/**
 * Manages the selection, creation, and activation of an Agent Instance tab.
 * This is the central function called from the sidebar `AgentInstance.js` to open a tab.
 * @param {number} instancePk The primary key of the agent instance.
 * @param {string} instanceName The name of the agent instance for the tab title.
 * @param {string} [targetPanelId='mainTabPanel'] The ID of the panel where the tab should open.
 */
function selectAgentInstanceTab(instancePk, instanceName, targetPanelId = 'mainTabPanel') {
    // Visually update the sidebar selection regardless of whether a tab is opened
    document.querySelectorAll('.sidebar-instance').forEach(el => el.classList.remove('selected-instance'));
    const sidebarItem = document.getElementById(`agent_instance_${instancePk}`);
    if (sidebarItem) {
        sidebarItem.classList.add('selected-instance');
    }

    const tabButtonId = `tabButton_agentInstance_${instancePk}`;
    const tabContentId = `tabContent_agentInstance_${instancePk}`;
    const existingTabButton = document.getElementById(tabButtonId);

    // If tab exists, just activate it
    if (existingTabButton) {
        // Find its current parent panel to activate it in place.
        const existingParentPanel = existingTabButton.closest('.resizable-panel.flex-column');
        const existingParentPanelId = existingParentPanel ? existingParentPanel.id : targetPanelId;
        openMainTab(null, tabContentId, existingParentPanelId);
    } else {
        // If tab does not exist, create it, subscribe, and load its history.
        const targetPanel = document.getElementById(targetPanelId);
        if (!targetPanel) {
            console.error(`Target panel ${targetPanelId} not found for creating agent instance tab.`);
            return;
        }

        // 1. Create tab button
        const newTabButton = document.createElement('button');
        newTabButton.id = tabButtonId;
        newTabButton.className = 'tab-button';
        newTabButton.dataset.tabId = tabButtonId;
        newTabButton.dataset.tabContentId = tabContentId;
        newTabButton.setAttribute('draggable', 'true');
        newTabButton.ondragstart = (event) => dragTab(event, tabButtonId, tabContentId);
        newTabButton.innerHTML = `
            <span><i class="fa fa-user-circle-o"></i> ${instanceName}</span>
            <i class="fa fa-times close-tab-btn" onclick="event.stopPropagation(); closeMainTab('${tabContentId}')"></i>
        `;
        // The onclick now also updates the global currentAgentInstancePk for UI focus
        newTabButton.setAttribute('onclick', `openMainTab(event, '${tabContentId}', '${targetPanelId}'); window.currentAgentInstancePk = ${instancePk};`);

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

        // 5. Set current instance PK
        window.currentAgentInstancePk = instancePk;

        // 6. Subscribe and load initial data *ONLY ON CREATION*
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({ type: 'subscribe', payload: { instance_pk: instancePk } }));
            addToClientLog(`Client: Sent "subscribe" for instance ${instancePk}`, 'client-status');
            conversationApi.listMessages({ instance_pk: instancePk, limit: 20 });
            addToClientLog(`Client: Sent "load_history" for instance ${instancePk}`, 'info');
            agentInstanceApi.get( { instance_pk: instancePk });
            addToClientLog(`Client: Requesting details for instance ${instancePk}`, 'client-status');
        } else {
            addToClientLog(`Cannot subscribe/load for instance ${instancePk}. WebSocket not open.`, 'warning');
        }
    }
}


/**
 * Sends a message from the user input.
 * @param {Event} event The DOM event.
 * @param {number} instancePk The primary key of the agent instance.
 */
function sendMessage(event, instancePk) {
    event.stopPropagation();
    event.preventDefault(); // Prevent form submission if applicable

    const messageInput = document.querySelector(`#messageInput_${instancePk}`);
    const message = messageInput.value.trim();

    if (message && websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'user_input',
            payload: { 
                message: message,
                instance_pk: instancePk
            }
        }));
        messageInput.value = '';
        messageInput.focus(); // Keep focus on input for quick follow-ups
    }
}

/**
 * Handles keydown events on the message input, specifically Ctrl+Enter to send.
 * @param {Event} event The DOM event.
 * @param {number} instancePk The primary key of the agent instance.
 */
function handleMessageInputKeydown(event, instancePk) {
    if (event.key === 'Enter' && event.ctrlKey) {
        event.preventDefault();
        sendMessage(event, instancePk);
    }
}

/**
 * Initializes log filter controls for a specific agent instance.
 * @param {number} instancePk The primary key of the agent instance.
 * @param {HTMLElement} tabContentElement The root DOM element for the instance tab.
 */
function initializeLogFilterControlsForInstance(instancePk, tabContentElement) {
    const logAreaContainer = tabContentElement.querySelector(`#logArea_${instancePk}`);
    if (!logAreaContainer) {
        console.error(`logAreaContainer for instance ${instancePk} not found for filter controls.`);
        return;
    }

    let filterControls = logAreaContainer.querySelector('.log-filter-controls');
    if (!filterControls) {
        filterControls = document.createElement('div');
        filterControls.id = `log-filter-controls_${instancePk}`;
        filterControls.classList.add('log-filter-container');
        logAreaContainer.prepend(filterControls);
    }

    filterControls.innerHTML = `
        <button class="log-filter-btn" data-log-type="conversation" data-tab-name="conversation" title="Toggle User/Agent Messages"><i class="fa fa-comments-o"></i></button>
        <button class="log-filter-btn" data-log-type="tool" data-tab-name="tool" title="Toggle Tool Calls & Responses"><i class="fa fa-wrench"></i></button>
        <button class="log-filter-btn" data-log-type="fs" data-tab-name="fs" title="Toggle Filesystem Logs"><i class="fa fa-folder-open-o"></i></button>
        <button class="log-filter-btn" data-log-type="llm" data-tab-name="llm" title="Toggle LLM Queries/Responses"><i class="fa fa-cogs"></i></button>
        <button class="log-filter-btn" data-log-type="debug" data-tab-name="debug" title="Toggle Debug Logs"><i class="fa fa-bug"></i></button>
        <button class="log-filter-btn" data-log-type="pyvar" data-tab-name="pyvar" title="Toggle VARS Updates"><i class="fa fa-code"></i></button>
    `;

    filterControls.querySelectorAll('.log-filter-btn').forEach(button => {
        const logType = button.dataset.logType;
        
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

/**
 * Handles the display logic for sidebar tabs within a specific agent instance.
 * This function also initiates data fetching for the selected sidebar tab.
 * @param {string} tabName The name of the tab to show ('filesystem', 'memory', 'vars', etc.).
 * @param {HTMLElement} clickedButton The button element that was clicked.
 * @param {number} instancePk The primary key of the agent instance.
 */
function showSidebarTabForInstance(tabName, clickedButton, instancePk) {
    if (!instancePk) {
        console.error("showSidebarTabForInstance: instancePk is required.");
        return;
    }

    const sidebarRight = document.getElementById(`sidebar-right_${instancePk}`);
    if (!sidebarRight) {
        console.error(`Right sidebar for instance ${instancePk} not found.`);
        return;
    }

    // Hide all tab content within this specific sidebar
    sidebarRight.querySelectorAll('.sidebar-tab-content').forEach(tab => {
        tab.style.display = 'none';
        tab.classList.remove('active');
    });
    // Deactivate all tab buttons within this specific sidebar
    sidebarRight.querySelectorAll('.sidebar-tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show the selected tab content
    const tabContent = document.getElementById(`sidebar-tab-${tabName}_${instancePk}`);
    if (tabContent) {
        tabContent.style.display = 'flex';
        tabContent.classList.add('active');
    }
    
    // Activate the selected tab button
    if (clickedButton) {
        clickedButton.classList.add('active');
    }

    // --- Data Fetching Logic for Instance-Specific Sidebars ---
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        switch (tabName) {
            case 'filesystem':
                const filesystemTabContent = document.getElementById(`sidebar-tab-filesystem_${instancePk}`);
                const trimmedContent = filesystemTabContent.innerHTML.trim();
                const isOnlyComment = trimmedContent === '<!-- Filesystem content will be rendered here by renderSidebarFilesystem.js -->';
                if (filesystemTabContent && (trimmedContent === '' || isOnlyComment)) {
                    if (typeof initializeFilesystemSidebarUI === 'function') {
                        initializeFilesystemSidebarUI(instancePk);
                    } else {
                        console.warn(`showSidebarTabForInstance: initializeFilesystemSidebarUI function not found for instance ${instancePk}. Filesystem sidebar may not render.`);
                    }
                }
                filesystemApi.list({ instance_pk: instancePk });
                addToClientLog(`Client: Requesting Filesystem State for instance ${instancePk}`, 'info');
                break;
            case 'memory':
                
                websocket.send(JSON.stringify({
                    type: 'request_memory_state',
                    payload: { instance_pk: instancePk }
                }));
                addToClientLog(`Client: Requesting Memory State for instance ${instancePk}`, 'info');
                break;
            case 'vars':
                agentInstanceApi.getVars({ instance_pk: instancePk });
                addToClientLog(`Client: Requesting VARS State for instance ${instancePk}`, 'info');
                break;
            case 'permissions':
                
                websocket.send(JSON.stringify({
                    type: 'get_instance_permissions',
                    payload: { instance_pk: instancePk }
                }));
                addToClientLog(`Client: Requesting Permissions for instance ${instancePk}`, 'info');
                break;
            case 'settings':
                agentInstanceApi.get( { instance_pk: instancePk });
                addToClientLog(`Client: Requesting Settings for instance ${instancePk}`, 'info');
                break;
        }
    } else {
        addToClientLog("WebSocket not connected. Cannot fetch sidebar data.", 'error');
    }
}

/**
 * Updates the agent instance status bar in the main tab content.
 * @param {number} instancePk The primary key of the agent instance.
 * @param {object} payload The update payload containing status and status_display.
 */
function updateAgentInstanceStatusBar(instancePk, payload) {
    const instanceTabContent = document.getElementById(`tabContent_agentInstance_${instancePk}`);
    if (instanceTabContent) {
        const statusBar = instanceTabContent.querySelector(`#agent-status-bar_${instancePk}`);
        const statusText = instanceTabContent.querySelector(`#agent-status-text_${instancePk}`);

        if (statusBar && statusText) {
            statusText.textContent = payload.status_display;
            const statusClasses = ['status-bg-THINKING', 'status-bg-EXECUTING_TOOLS', 'status-bg-AWAITING_USER_INPUT', 'status-bg-AWAITING_AGENT_MESSAGE', 'status-bg-IDLE', 'status-bg-COMPLETED', 'status-bg-FAILED', 'status-bg-READY'];
            statusBar.classList.remove(...statusClasses);
            statusBar.classList.add(`status-bg-${payload.status}`);
            statusBar.classList.remove('agent-status-bar-hidden');
        }
    }
}

/**
 * Handles the request for agent instance deletion.
 * @param {number} instancePk The primary key of the agent instance.
 * @param {string} instanceName The name of the agent instance.
 */
function requestAgentInstanceDeletion(instancePk, instanceName) {
    if (confirm(`Are you sure you want to delete agent instance "${instanceName}" (ID: ${instancePk})? This action cannot be undone.`)) {
        agentInstanceApi.delete({instance_pk: instancePk});
    } else {
        addToClientLog(`Client: Deletion of agent instance ${instancePk} cancelled.`, 'info');
    }
    closeMainTab(`tabContent_agentInstance_${instancePk}`);
}