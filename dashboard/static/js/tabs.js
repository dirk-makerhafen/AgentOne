// --- Data Fetching Logic for Main Tabs ---
function updateTabContentForPanel(tabId, parentPanelId) {
    const parentElement = document.getElementById(parentPanelId);
    if (!parentElement) {
        console.error(`Parent element with ID ${parentPanelId} not found for tab ${tabId}.`);
        return;
    }
    
    // Check if the tabId corresponds to an agent instance tab
    const instancePkMatch = tabId.match(/tabContent_agentInstance_(\d+)/);
    const instancePk = instancePkMatch ? instancePkMatch[1] : null;

    if (instancePk) {
        // This is an agent instance tab, data fetching handled by selectAgentInstance
        // and subsequent websocket messages for rendering specific components.
        // We ensure a call to selectAgentInstance when an agent instance tab is opened
        // or activated.
        // For now, we don't need explicit data fetching here, as selectAgentInstance
        // will trigger it.
        return;
    }


    if (tabId === 'tabContent_providers') {
        // Ensure we are selecting within the context of the parentPanel
        const providersTabContent = parentElement.querySelector(`#${tabId}`);
        if (providersTabContent && websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'request_provider_list',
                payload: {}
            }));
            const providersListBody = providersTabContent.querySelector('#providers-list-body');
            if (providersListBody) {
                providersListBody.innerHTML = '<p class="log-info">Loading API Providers...</p>';
            }
            addToConsoleArea("Client: Requesting API Providers...", 'info');
        } else if (providersTabContent) {
            const providersListBody = providersTabContent.querySelector('#providers-list-body');
            if (providersListBody) {
                providersListBody.innerHTML = '<p class="log-warning">Could not load API Providers. WebSocket not connected.</p>';
            }
            addToConsoleArea("Could not load API Providers. WebSocket not connected.", 'warning');
        }
    } else if (tabId === 'tabContent_systems') {
        const systemsTabContent = parentElement.querySelector(`#${tabId}`);
        if (systemsTabContent && websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'request_system_list',
                payload: {}
            }));
            const systemsListBody = systemsTabContent.querySelector('#systems-list-body');
            if (systemsListBody) {
                systemsListBody.innerHTML = '<p class="log-info">Loading Systems...</p>';
            }
            addToConsoleArea("Client: Requesting Systems List...", 'info');
        } else if (systemsTabContent) {
            const systemsListBody = systemsTabContent.querySelector('#systems-list-body');
            if (systemsListBody) {
                systemsListBody.innerHTML = '<p class="log-warning">Could not load Systems. WebSocket not connected.</p>';
            }
            addToConsoleArea("Could not load Systems. WebSocket not connected.", 'warning');
        }
    } else if (tabId === 'tabContent_prompts') {
        const promptsTabContent = parentElement.querySelector(`#${tabId}`);
        if (promptsTabContent && websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'request_prompt_list',
                payload: {}
            }));
            const promptsListBody = promptsTabContent.querySelector('#prompts-list-body');
            if (promptsListBody) {
                promptsListBody.innerHTML = '<p class="log-info">Loading Prompt Templates...</p>';
            }
            addToConsoleArea("Client: Requesting Prompt Templates...", 'info');
        } else if (promptsTabContent) {
            const promptsListBody = promptsTabContent.querySelector('#prompts-list-body');
            if (promptsListBody) {
                promptsListBody.innerHTML = '<p class="log-warning">Could not load Prompt Templates. WebSocket not connected.</p>';
            }
            addToConsoleArea("Could not load Prompt Templates. WebSocket not connected.", 'warning');
        }
    }
}

// The openMainTab function will now call updateTabContentForPanel
function openMainTab(evt, tabId, parentPanelId = 'mainTabPanel') {

    
    const parentPanel = document.getElementById(parentPanelId);
    if (!parentPanel) {
        console.error(`Error: Parent panel with ID ${parentPanelId} not found for tab ${tabId}.`);
        return;
    }

    // Get all tab content elements within this specific parent panel and hide them
    parentPanel.querySelectorAll('.tab-content').forEach(tab => {
        tab.style.display = 'none';
        tab.classList.remove('active');
    });
    // Also remove the placeholder if it's there
    const noInstanceContent = parentPanel.querySelector('#no-instance-selected-content');
    if (noInstanceContent) {
        noInstanceContent.style.display = 'none';
        noInstanceContent.classList.remove('active');
    }


    // Get all tab buttons within this specific parent panel's tab bar and remove the "active" class
    const tabBar = parentPanel.querySelector('.tab-bar');
    if (tabBar) {
        tabBar.querySelectorAll('.tab-button').forEach(btn => {
            btn.classList.remove('active');
        });
        // Also hide the placeholder if it's there
        const noInstancePlaceholder = tabBar.querySelector('#no-instance-placeholder');
        if (noInstancePlaceholder) {
            noInstancePlaceholder.style.display = 'none';
            noInstancePlaceholder.classList.remove('active');
        }
    }

    // Show the current tab content, and add an "active" class to it
    const currentTabContent = document.getElementById(tabId);
    if (currentTabContent) {
        currentTabContent.style.display = "flex";
        currentTabContent.classList.add('active');
    } else {
        console.warn(`Tab content with ID ${tabId} not found.`);
    }

    // Find and activate the corresponding tab button within the current panel's tab bar
    if (tabBar) {
        tabBar.querySelectorAll('.tab-button').forEach(button => {
            const buttonOnClick = button.getAttribute('onclick');
            // Check if the onclick event targets the current tabId and the same parentPanelId
            if (buttonOnClick && buttonOnClick.includes(`openMainTab(event, '${tabId}'`)) {
                button.classList.add("active");
                button.style.display = "inline-block"; // Ensure the button is visible
            }
        });
    }

    reinitializeAllSplits();
    updateTabContentForPanel(tabId, parentPanelId);
}

function closeMainTab(tabId) {
    //console.log(`closeMainTab called for tabId: ${tabId}`);
    const tabContent = document.getElementById(tabId);
    if (!tabContent) {
        console.warn(`Tab content element with ID ${tabId} not found.`);
        return;
    }

    // Determine the tab button ID
    const tabButtonId = `tabButton_${String(tabId).replace('tabContent_', '')}`;
    const tabButton = document.getElementById(tabButtonId);

    // Get the parent panel before elements are removed
    const parentPanel = tabContent.closest('.resizable-panel.flex-column');
    const parentPanelId = parentPanel ? parentPanel.id : 'mainTabPanel';
    const tabBar = parentPanel ? parentPanel.querySelector('.tab-bar') : document.getElementById('mainTabBar');

    // Check if it's an agent instance tab
    const instancePkMatch = tabId.match(/tabContent_agentInstance_(\d+)/);
    const instancePk = instancePkMatch ? parseInt(instancePkMatch[1], 10) : null;

    if (instancePk) {
        //console.log(`Closing agent instance tab for instancePk: ${instancePk}.`);
        // 1. Unsubscribe from WebSocket messages for this instance
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'unsubscribe',
                payload: { instance_pk: instancePk }
            }));
            addToConsoleArea(`Client: Unsubscribed from instance ${instancePk}`, 'client-status');
        }

        // 2. Clean up instance-specific state
        if (instanceLogStates[instancePk]) {
            delete instanceLogStates[instancePk];
            //console.log(`Cleaned up instanceLogStates for instancePk: ${instancePk}.`);
        }
        
        // 3. Reset global currentAgentInstancePk if this was the active instance
        if (window.currentAgentInstancePk === instancePk) {
            window.currentAgentInstancePk = null;
            // Optionally hide the global status bar if no instance is selected
            const statusBar = document.getElementById('agent-status-bar');
            if (statusBar) {
                statusBar.classList.add('agent-status-bar-hidden');
            }
        }
        if (window.lastSelectedInstancePk === instancePk) {
            window.lastSelectedInstancePk = null;
        }

        // 4. Remove elements from DOM
        tabContent.remove();
        if (tabButton) {
            tabButton.remove();
        }
        addToConsoleArea(`Agent instance tab for ${instancePk} removed from DOM.`, 'info');

    } else {
        // For static tabs, just hide them as before
        tabContent.style.display = "none";
        tabContent.classList.remove('active');
        if (tabButton) {
            tabButton.style.display = "none";
            tabButton.classList.remove("active");
        }
        addToConsoleArea(`Static tab ${tabId} hidden.`, 'info');
    }

    // After closing/removing, find another tab to open automatically within the same panel
    if (tabBar) {
        const visibleTabButtons = Array.from(tabBar.querySelectorAll('.tab-button')).filter(button => {
            // A button is visible if its display is not 'none' and it's not the one we just closed
            return button.style.display !== 'none' && (tabButton ? button.id !== tabButton.id : true);
        });

        if (visibleTabButtons.length > 0) {
            // Activate the first visible remaining tab
            const tabToOpen = visibleTabButtons[0];
            const onclickAttr = tabToOpen.getAttribute('onclick');
            const match = onclickAttr.match(/openMainTab\(event, '(tabContent_[^']+)'(?:,\s*'([^']+)')?\)/);
            if (match && match[1]) {
                const targetTabId = match[1];
                openMainTab(null, targetTabId, parentPanelId); // Use the original parentPanelId
            }
        } else {
            // If no other tabs are visible in this panel, show the generic placeholder
            let placeholderContent = parentPanel.querySelector('.default-split-content');

            if (!placeholderContent) {
                // Create a new placeholder if it doesn't exist
                placeholderContent = document.createElement('div');
                const placeholderId = `tabContent_split_${parentPanel.id.replace('mainTabPanel_split_', '') || ''}_placeholder`;
                placeholderContent.id = placeholderId;
                placeholderContent.className = 'resizable-container tab-content active default-split-content';
                placeholderContent.dataset.orientation = 'vertical';
                placeholderContent.innerHTML = '<p style="text-align: center; padding: 20px;">New split panel. Drag tabs here or add new content.</p>';
                
                // Add the drag-and-drop handlers to the new placeholder
                placeholderContent.setAttribute('ondragover', 'allowDrop(event)');
                placeholderContent.setAttribute('ondrop', `dropOnPlaceholder(event, '${parentPanel.id}')`);
                placeholderContent.setAttribute('ondragenter', "event.target.classList.add('drag-over')");
                placeholderContent.setAttribute('ondragleave', "event.target.classList.remove('drag-over')");
                
                parentPanel.insertBefore(placeholderContent, parentPanel.querySelector('.tab-controls-area').nextSibling);
            }
            
            placeholderContent.classList.add('active');
            placeholderContent.style.display = 'flex';
        }
    }
    reinitializeAllSplits();
}

// --- Tab Drag and Drop Functions ---
let draggedTabId = null;
let draggedTabContentId = null;
let originalParentTabBarId = null;

function dragTab(event, tabButtonId, tabContentId) {
    draggedTabId = tabButtonId;
    draggedTabContentId = tabContentId;
    originalParentTabBarId = event.target.closest('.tab-bar').id; // Store the ID of the source tab bar

    event.dataTransfer.setData('text/plain', JSON.stringify({
        tabButtonId: tabButtonId,
        tabContentId: tabContentId,
        originalParentTabBarId: originalParentTabBarId
    }));
    event.dataTransfer.effectAllowed = 'move';
}

function allowDrop(event) {
    event.preventDefault(); // Allow drop
    event.dataTransfer.dropEffect = 'move';
}

function dropTab(event, targetTabBarId) {
    event.preventDefault();

    // Preserve the current scroll position of the logArea - now instance-specific
    // Get the instancePk from the active tab in the original panel, or if null, just 0
    let instancePkForScroll = null;
    if (currentAgentInstancePk) {
        instancePkForScroll = currentAgentInstancePk;
    } else {
        // Try to derive it from the dragged tab content itself
        const draggedTabContent = document.getElementById(draggedTabContentId);
        if (draggedTabContent && draggedTabContent.dataset.instancePk) {
            instancePkForScroll = draggedTabContent.dataset.instancePk;
        }
    }
    
    const logAreaForScroll = instancePkForScroll ? document.getElementById(`logArea_${instancePkForScroll}`) : null;
    const savedScrollTop = logAreaForScroll ? logAreaForScroll.scrollTop : 0;


    const data = JSON.parse(event.dataTransfer.getData('text/plain'));
    const tabButtonId = data.tabButtonId;
    const tabContentId = data.tabContentId;
    const originalParentTabBarId = data.originalParentTabBarId;

    const draggedTabButton = document.getElementById(tabButtonId);
    const draggedTabContent = document.getElementById(tabContentId);
    const targetTabBar = document.getElementById(targetTabBarId);

    if (!draggedTabButton || !draggedTabContent || !targetTabBar) {
        addToConsoleArea('Error: Dragged tab or target tab bar not found.', 'error');
        return;
    }

    // Identify the original and target parent panels
    const originalParentPanel = document.getElementById(originalParentTabBarId).closest('.resizable-panel.flex-column');
    const targetParentPanel = targetTabBar.closest('.resizable-panel.flex-column');

    if (!originalParentPanel || !targetParentPanel) {
        addToConsoleArea('Error: Parent panel not found for drag/drop operation.', 'error');
        return;
    }

    // 1. Deactivate all tabs and content in the target panel
    targetParentPanel.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
    targetParentPanel.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
        content.style.display = 'none'; // Ensure content is hidden
    });
    // Remove any existing default split content in the target panel, as a new tab is being dropped
    const defaultContentInTarget = targetParentPanel.querySelector('.default-split-content');
    if (defaultContentInTarget) {
        defaultContentInTarget.remove();
    }


    // 2. Move the tab button to the target tab bar
    const splitControlsContainer = targetTabBar.querySelector('.split-controls-container');
    if (splitControlsContainer) {
        targetTabBar.insertBefore(draggedTabButton, splitControlsContainer);
    } else {
        targetTabBar.appendChild(draggedTabButton); // Fallback, though should not be needed
    }

    // 3. Move the tab content to the target panel (directly after the tab-controls-area)
    const tabControlsArea = targetParentPanel.querySelector('.tab-controls-area');
    if (tabControlsArea) {
        // Remove any existing default split content
        const defaultContent = targetParentPanel.querySelector('.default-split-content');
        if (defaultContent) {
            defaultContent.remove();
        }
        targetParentPanel.insertBefore(draggedTabContent, tabControlsArea.nextSibling);
    } else {
        targetParentPanel.appendChild(draggedTabContent);
    }

    // 4. Activate the dropped tab and its content
    draggedTabButton.classList.add('active');
    draggedTabContent.classList.add('active');

    // 5. Update the onclick attribute of the draggedTabButton to reflect its new parentPanelId
    const newOnClick = `openMainTab(event, '${tabContentId}', '${targetParentPanel.id}')`;
    draggedTabButton.setAttribute('onclick', newOnClick);

    // 6. Update display styles (important for tabs that were hidden)
    draggedTabButton.style.display = 'inline-block'; // Ensure the dropped tab button is visible
    draggedTabContent.style.display = 'flex'; // Ensure the dropped tab content is visible

    // 6. Check if the original panel became empty
    const remainingButtonsInOriginal = originalParentPanel.querySelectorAll('.tab-bar .tab-button:not([style*="display: none"])');
    if (remainingButtonsInOriginal.length === 0) {
        // If no visible tabs left, show a placeholder
        let placeholderContent = originalParentPanel.querySelector('.default-split-content');

        if (!placeholderContent) {
            // Create a new placeholder content div if it doesn't exist
            placeholderContent = document.createElement('div');
            placeholderContent.id = `tabContent_split_${originalParentPanel.id.replace('mainTabPanel_split_', '') || ''}_placeholder`;
            placeholderContent.className = 'resizable-container tab-content active default-split-content';
            placeholderContent.dataset.orientation = 'vertical';
            placeholderContent.innerHTML = '<p style="text-align: center; padding: 20px;">New split panel. Drag tabs here or add new content.</p>';
            
            // Add the drag-and-drop handlers to the new placeholder
            placeholderContent.setAttribute('ondragover', 'allowDrop(event)');
            placeholderContent.setAttribute('ondrop', `dropOnPlaceholder(event, '${originalParentPanel.id}')`);
            placeholderContent.setAttribute('ondragenter', "event.target.classList.add('drag-over')");
            placeholderContent.setAttribute('ondragleave', "event.target.classList.remove('drag-over')");

            originalParentPanel.insertBefore(placeholderContent, originalParentPanel.querySelector('.tab-controls-area').nextSibling);
        }
        
        // Always ensure the placeholder is active and visible
        placeholderContent.classList.add('active');
        placeholderContent.style.display = 'flex';
    } else {
        // If other tabs remain in the original panel, activate the first one
        const firstRemainingButton = remainingButtonsInOriginal[0];
        const onclickAttr = firstRemainingButton.getAttribute('onclick');
        // This regex needs to capture the tabId AND the optional parentPanelId, with proper escaping for JavaScript string literal
        const match = onclickAttr.match(/openMainTab\(event, '(tabContent_[^']+)'(?:,\s*'([^']+)')?\)/);
        if (match && match[1]) {
            const targetTabId = match[1];
            const targetPanelId = originalParentPanel.id; // Correctly get the ID of the original panel
            openMainTab(null, targetTabId, targetPanelId); 
        }
    }
    
    // Re-initialize splits to adjust sizes and add new handlers (if panels changed significantly)
    if (typeof reinitializeAllSplits === 'function') {
        reinitializeAllSplits();
    } else {
        console.error("reinitializeAllSplits function not found. Split.js setup failed.");
    }

    // 7. Clean up drag-over visual feedback on the target tab bar
    targetTabBar.classList.remove('drag-over');

    // 7. Clean up drag-over visual feedback on the target tab bar
    targetTabBar.classList.remove('drag-over');

    // Restore the scroll position of the logArea
    if (logAreaForScroll) {
        logAreaForScroll.scrollTop = savedScrollTop;
    }

    addToConsoleArea(`Moved tab ${tabButtonId} from ${originalParentTabBarId} to ${targetTabBarId}`, 'info');
}


// --- New function to handle dropping tabs on the placeholder content ---
function dropOnPlaceholder(event, targetPanelId) {
    event.preventDefault();
    event.stopPropagation(); // Stop the event from bubbling up further

    const targetPanel = document.getElementById(targetPanelId);
    if (!targetPanel) {
        console.error(`Drop target panel ${targetPanelId} not found.`);
        return;
    }
    const targetTabBar = targetPanel.querySelector('.tab-bar');
    if (!targetTabBar) {
        console.error(`Tab bar in target panel ${targetPanelId} not found.`);
        return;
    }

    // Now that we have the tab bar, we can call the existing dropTab function
    dropTab(event, targetTabBar.id);
    
    // Clean up the drag-over class from the placeholder itself
    const placeholderId = `tabContent_split_${targetPanelId.replace('mainTabPanel_split_', '')}_placeholder`;
    const placeholder = document.getElementById(placeholderId);
    if (placeholder) {
        placeholder.classList.remove('drag-over');
    }
}
