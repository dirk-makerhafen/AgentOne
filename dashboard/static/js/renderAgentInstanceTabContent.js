const agentInstanceTabContentTemplate = Handlebars.compile(`
<div id="tabContent_agentInstance_{{instancePk}}" class="tab-content resizable-container active" data-orientation="vertical">
    
    <!-- Header Panel -->
    <div class="resizable-panel agentInstanceHeader" id="agentInstanceHeader_{{instancePk}}" data-size-pc="5">
        <!-- Content will be rendered by renderAgentInstanceHeader.js -->
    </div>

    <!-- Main Content Area (Chat + Right Sidebar) - This needs to be a resizable-container for horizontal split -->
    <div class="resizable-panel resizable-container" data-orientation="horizontal" data-size-pc=95>
        
        <!-- Chat Area Panel -->
        <div class="resizable-panel" data-orientation="vertical" data-size-pc=70>
            <div class="resizable-container" data-orientation="vertical" data-size-pc=15>
                <div id="logArea_{{instancePk}}" class="logArea resizable-panel conversation-log flex-column hide-tool">
                    <!-- Log messages and filter controls will be rendered here by JavaScript -->
                    <div id="agent-status-ribbon_{{instancePk}}" class="agent-status-ribbon agent-status-ribbon-hidden">
                        <span class="status-text"></span>
                    </div>
                </div>
                <div class="resizable-panel flex-row" data-size-pc="20">
                    <div class="chat_user_input">
                        <textarea id="messageInput_{{instancePk}}" name="user_input" rows="4" cols="50" placeholder="Enter your message..."></textarea>
                    </div>
                    <div class="chat-actions">
                        <button id="sendMessageBtn_{{instancePk}}" class="submit_button btn btn-success" type="submit">Send</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Right Sidebar Panel -->
        <div class="resizable-panel resizable-container" data-orientation="vertical" data-size-pc="30">
            <div class="resizable-panel resizable-container" data-orientation="vertical"  id="sidebar-right_{{instancePk}}">
                <div class="sidebar-tabs">
                    <button class="sidebar-tab-btn active" onclick="showSidebarTabForInstance('filesystem', this, {{instancePk}})">Filesystem</button>
                    <button class="sidebar-tab-btn" onclick="showSidebarTabForInstance('memory', this, {{instancePk}})">Memory</button>
                    <button class="sidebar-tab-btn" onclick="showSidebarTabForInstance('vars', this, {{instancePk}})">VARS</button>
                    <button class="sidebar-tab-btn" onclick="showSidebarTabForInstance('settings', this, {{instancePk}})">Settings</button>
                    <button class="sidebar-tab-btn" onclick="showSidebarTabForInstance('permissions', this, {{instancePk}})">Permissions</button>
                </div>

                <div id="sidebar-tab-filesystem_{{instancePk}}" class="sidebar-tab-content active">
                    <!-- Filesystem content will be rendered here by renderSidebarFilesystem.js -->
                </div>

                <div id="sidebar-tab-memory_{{instancePk}}" class="sidebar-tab-content flex-column" style="display: none;">
                    <!-- Memory content will be rendered here by renderSidebarMemory.js -->
                </div>

                <div id="sidebar-tab-permissions_{{instancePk}}" class="sidebar-tab-content" style="display: none;">
                    <!-- Permissions content will be rendered here by renderSidebarPermissions.js -->
                </div>

                <div id="sidebar-tab-settings_{{instancePk}}" class="sidebar-tab-content" style="display: none;">
                    <!-- Settings content will be rendered here by renderSidebarSettings.js -->
                </div>

                <div id="sidebar-tab-vars_{{instancePk}}" class="sidebar-tab-content" style="display: none;">
                    <!-- VARS content will be rendered here by renderSidebarVars.js -->
                </div>
            </div>
        </div>
    </div>

    <!-- Instance-specific Agent Status Bar -->
    <div id="agent-status-bar_{{instancePk}}" class="agent-status-bar agent-status-bar-hidden">
        <span id="agent-status-text_{{instancePk}}" class="status-text"></span>
    </div>
</div>
`);


function renderAgentInstanceTabContent(instancePk, parentPanelId) {
    const parentPanel = document.getElementById(parentPanelId);
    if (!parentPanel) {
        console.error(`renderAgentInstanceTabContent: Parent panel ${parentPanelId} not found.`);
        return;
    }

    const html = agentInstanceTabContentTemplate({ instancePk: instancePk });
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html.trim();
    const newTabContentElement = tempDiv.firstChild;

    // The agent-status-bar should always be at the very bottom of the parent panel.
    // So, we insert the new tab content *before* the status bar if it exists.
    const statusBar = parentPanel.querySelector('#agent-status-bar');
    if (statusBar) {
        parentPanel.insertBefore(newTabContentElement, statusBar);
    } else {
        // If status bar is not found in this specific parentPanel, just append it.
        // This handles cases for split panels that might not have the global status bar.
        parentPanel.appendChild(newTabContentElement);
    }

    // --- Attach event listeners for chat input and send button ---
    const messageInput = newTabContentElement.querySelector(`#messageInput_${instancePk}`);
    const sendMessageBtn = newTabContentElement.querySelector(`#sendMessageBtn_${instancePk}`);

    if (messageInput && sendMessageBtn) {
        // 1. Handle sending message on button click
        sendMessageBtn.addEventListener('click', function() {
            const message = messageInput.value.trim();
            if (message && websocket && websocket.readyState === WebSocket.OPEN) {
                websocket.send(JSON.stringify({
                    type: 'user_input',
                    payload: {
                        message: message,
                        instance_pk: instancePk
                    }
                }));
                messageInput.value = ''; // Clear input
                messageInput.focus(); // Return focus to the textarea
            }
        });

        // 2. Handle Ctrl+Enter to send from textarea for better UX
        messageInput.addEventListener('keydown', function(event) {
            if (event.key === 'Enter' && event.ctrlKey) {
                event.preventDefault();
                sendMessageBtn.click();
            }
        });

        // 3. Prevent Enter key on the button from firing a click event (the user's direct request)
        sendMessageBtn.addEventListener('keydown', function(event) {
            if (event.key === 'Enter' || event.key === ' ') { // Also prevent spacebar activation
                event.preventDefault();
            }
        });
    }

    requestAnimationFrame(() => {
          reinitializeAllSplits();
    });
    showSidebarTabForInstance('filesystem', 
        newTabContentElement.querySelector(`#sidebar-right_${instancePk} .sidebar-tab-btn.active`), 
        instancePk
    );
    // Attach the scroll listener to the new logArea
    const newLogArea = newTabContentElement.querySelector(`#logArea_${instancePk}`);
    if (newLogArea && typeof attachLogAreaScrollListener === 'function') {
        attachLogAreaScrollListener(newLogArea, instancePk);
    } else {
        console.error(`[renderAgentInstanceTabContent] Failed to attach scroll listener for instance ${instancePk}. newLogArea: ${newLogArea}, attachLogAreaScrollListener is function: ${typeof attachLogAreaScrollListener === 'function'}.`);
    }
};

/**
 * Handles the display logic for sidebar tabs within a specific agent instance.
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
                // Check if the sidebar-tab-filesystem_{instancePk} has been initialized
                // with its base HTML structure. If not, initialize it.
                const filesystemTabContent = document.getElementById(`sidebar-tab-filesystem_${instancePk}`);
                //console.log(`showSidebarTabForInstance: Filesystem tab content innerHTML for instance ${instancePk} before init: '${filesystemTabContent.innerHTML.trim()}'`);
                const trimmedContent = filesystemTabContent.innerHTML.trim();
                const isOnlyComment = trimmedContent === '<!-- Filesystem content will be rendered here by renderSidebarFilesystem.js -->';
                if (filesystemTabContent && (trimmedContent === '' || isOnlyComment)) {
                    if (typeof initializeFilesystemSidebarUI === 'function') {
                        //console.log(`showSidebarTabForInstance: Calling initializeFilesystemSidebarUI for instance ${instancePk}.`);
                        initializeFilesystemSidebarUI(instancePk);
                    } else {
                        console.warn(`showSidebarTabForInstance: initializeFilesystemSidebarUI function not found for instance ${instancePk}. Filesystem sidebar may not render.`);
                    }
                }
                // Request initial state (contents will be rendered by renderSidebarFilesystem)
                websocket.send(JSON.stringify({
                    type: 'request_fs_state',
                    payload: { instance_pk: instancePk }
                }));
                addToConsoleArea(`Client: Requesting Filesystem State for instance ${instancePk}`, 'info');
                break;
            case 'memory':
                websocket.send(JSON.stringify({
                    type: 'request_memory_state',
                    payload: { instance_pk: instancePk }
                }));
                addToConsoleArea(`Client: Requesting Memory State for instance ${instancePk}`, 'info');
                break;
            case 'vars':
                websocket.send(JSON.stringify({
                    type: 'request_vars_state',
                    payload: { instance_pk: instancePk }
                }));
                addToConsoleArea(`Client: Requesting VARS State for instance ${instancePk}`, 'info');
                break;
            case 'permissions':
                websocket.send(JSON.stringify({
                    type: 'get_instance_permissions',
                    payload: { instance_pk: instancePk }
                }));
                addToConsoleArea(`Client: Requesting Permissions for instance ${instancePk}`, 'info');
                break;
            case 'settings':
                websocket.send(JSON.stringify({
                    type: 'request_instance_details',
                    payload: { instance_pk: instancePk }
                }));
                addToConsoleArea(`Client: Requesting Settings for instance ${instancePk}`, 'info');
                break;
        }
    } else {
        addToConsoleArea("WebSocket not connected. Cannot fetch sidebar data.", 'error');
    }
};

