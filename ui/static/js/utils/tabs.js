// The core function for creating, finding, and activating a tab.
function openMainTab(evt, tabId, parentPanelId = 'mainTabPanel', tabName, tabContentHtml) {
    if (evt) {
        evt.stopPropagation();
        evt.preventDefault();
    }
    
    // Force re-creation of ephemeral tabs like "Add Agent" to prevent stale content.
    if (tabId === 'tabContent_add_agent') {
        const oldTabContent = document.getElementById('tabContent_add_agent');
        if (oldTabContent) oldTabContent.remove();
        const oldTabButton = document.getElementById('tabButton_add_agent');
        if (oldTabButton) oldTabButton.remove();
    }
    
    const parentPanel = document.getElementById(parentPanelId);
    if (!parentPanel) {
        console.error(`Error: Parent panel with ID ${parentPanelId} not found for tab ${tabId}.`);
        return;
    }

    // --- Hide all existing tabs and buttons in the target panel ---
    parentPanel.querySelectorAll('.tab-content').forEach(tab => {
        tab.style.display = 'none';
        tab.classList.remove('active');
    });
    const tabBar = parentPanel.querySelector('.tab-bar');
    if (tabBar) {
        tabBar.querySelectorAll('.tab-button').forEach(btn => {
            btn.classList.remove('active');
        });
    }

    // --- Find or Create Tab Content ---
    let currentTabContent = document.getElementById(tabId);
    if (!currentTabContent && tabContentHtml) {
        const tabControlsArea = parentPanel.querySelector('.tab-controls-area');
        if (tabControlsArea) {
            tabControlsArea.insertAdjacentHTML('afterend', tabContentHtml);
            currentTabContent = document.getElementById(tabId);
        } else {
            console.error(`Could not find .tab-controls-area in panel ${parentPanelId} to insert tab content.`);
            return;
        }
    }
    
    // --- Find or Create Tab Button ---
    let tabButton;
    if (tabBar) {
        const tabButtonId = `tabButton_${String(tabId).replace('tabContent_', '')}`;
        tabButton = document.getElementById(tabButtonId);

        if (!tabButton && tabName) {
            // Button doesn't exist, create it
            const newButton = document.createElement('button');
            newButton.id = tabButtonId;
            newButton.className = 'tab-button';
            newButton.setAttribute('onclick', `openMainTab(event, '${tabId}', '${parentPanelId}')`);
            newButton.setAttribute('draggable', 'true');
            newButton.ondragstart = (event) => dragTab(event, tabButtonId, tabId);

            const textNode = document.createTextNode(tabName + ' ');
            newButton.appendChild(textNode);

            const closeIcon = document.createElement('i');
            closeIcon.className = 'fa fa-times close-tab-btn';
            closeIcon.setAttribute('onclick', `event.stopPropagation(); closeMainTab('${tabId}')`);
            newButton.appendChild(closeIcon);
            
            const splitControls = tabBar.querySelector('.split-controls-container');
            if (splitControls) {
                tabBar.insertBefore(newButton, splitControls);
            } else {
                tabBar.appendChild(newButton);
            }
            tabButton = newButton;
        }
    }
    
    // --- Show and Activate the target tab and button ---
    if (currentTabContent) {
        currentTabContent.style.display = "flex";
        currentTabContent.classList.add('active');
        
        // Remove placeholder content if it exists
        const placeholder = parentPanel.querySelector('.default-split-content');
        if(placeholder) placeholder.remove();
        
    } else {
        console.warn(`Tab content with ID ${tabId} not found and could not be created.`);
    }

    if (tabButton) {
        tabButton.classList.add("active");
        tabButton.style.display = "inline-block";
    } else {
        console.warn(`Tab button for content ID ${tabId} not found in tab bar.`);
    }

    reinitializeAllSplits();
}

function closeMainTab(tabId) {
    const tabContent = document.getElementById(tabId);
    if (!tabContent) {
        console.warn(`Tab content element with ID ${tabId} not found.`);
        return;
    }

    const tabButtonId = `tabButton_${String(tabId).replace('tabContent_', '')}`;
    const tabButton = document.getElementById(tabButtonId);

    const parentPanel = tabContent.closest('.resizable-panel.flex-column');
    const parentPanelId = parentPanel ? parentPanel.id : 'mainTabPanel';
    const tabBar = parentPanel ? parentPanel.querySelector('.tab-bar') : document.getElementById('mainTabBar');

    const instancePkMatch = tabId.match(/tabContent_agentInstance_(\d+)/);
    const instancePk = instancePkMatch ? parseInt(instancePkMatch[1], 10) : null;
    const isEphemeralTab = tabId === 'tabContent_add_agent'; // Future ephemeral tabs can be added here

    if (instancePk) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'unsubscribe',
                payload: { instance_pk: instancePk }
            }));
            addToClientLog(`Client: Unsubscribed from instance ${instancePk}`, 'client-status');
        }
        if (instanceLogStates[instancePk]) delete instanceLogStates[instancePk];
        deselectAgentInstance(instancePk);
        if (window.lastSelectedInstancePk === instancePk) window.lastSelectedInstancePk = null;
    }

    if (instancePk || isEphemeralTab) {
        // Remove instance tabs and ephemeral tabs from the DOM completely
        tabContent.remove();
        if (tabButton) tabButton.remove();
    } else {
        // Hide singleton tabs (like Systems, Tools) instead of removing them
        tabContent.style.display = "none";
        tabContent.classList.remove('active');
        if (tabButton) {
            tabButton.style.display = "none";
            tabButton.classList.remove("active");
        }
    }

    if (tabBar) {
        const visibleTabButtons = Array.from(tabBar.querySelectorAll('.tab-button')).filter(button => {
            return button.style.display !== 'none' && (tabButton ? button.id !== tabButton.id : true) && !button.classList.contains('active');
        });

        if (visibleTabButtons.length > 0) {
            const tabToOpen = visibleTabButtons[visibleTabButtons.length - 1]; // Open the last active tab
            const onclickAttr = tabToOpen.getAttribute('onclick');
            const match = onclickAttr.match(/openMainTab\(event, '([^']+)'(?:,\s*'([^']*)')?\)/);
            if (match && match[1]) {
                openMainTab(null, match[1], match[2] || parentPanelId);
            }
        } else {
            // No other tabs are open in this panel, show a placeholder
            let placeholderContent = parentPanel.querySelector('.default-split-content');
            if (!placeholderContent) {
                placeholderContent = document.createElement('div');
                placeholderContent.id = `tabContent_placeholder_${parentPanel.id}`;
                placeholderContent.className = 'resizable-container tab-content active default-split-content';
                placeholderContent.dataset.orientation = 'vertical';
                placeholderContent.innerHTML = '<p style="text-align: center; padding: 20px;">Select an agent instance or open a tab.</p>';
                parentPanel.insertBefore(placeholderContent, parentPanel.querySelector('.tab-controls-area').nextSibling);
            }
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
        addToClientLog('Error: Dragged tab or target tab bar not found.', 'error');
        return;
    }

    // Identify the original and target parent panels
    const originalParentPanel = document.getElementById(originalParentTabBarId).closest('.resizable-panel.flex-column');
    const targetParentPanel = targetTabBar.closest('.resizable-panel.flex-column');

    if (!originalParentPanel || !targetParentPanel) {
        addToClientLog('Error: Parent panel not found for drag/drop operation.', 'error');
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

    addToClientLog(`Moved tab ${tabButtonId} from ${originalParentTabBarId} to ${targetTabBarId}`, 'info');
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
