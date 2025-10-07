window.instanceMemoryStates = {}; 

const memoryTabButtonTemplate = Handlebars.compile(`
    <button class="memory-tab-btn {{#if isActive}}active{{/if}}" onclick="showMemoryTrack('{{trackName}}', {{instancePk}})">{{trackName}}</button>
`);

const memoryTrackPaneTemplate = Handlebars.compile(`
    <div id="memory-track-{{trackName}}_{{instancePk}}" class="memory-track-pane {{#if isActive}}active{{/if}}"></div>
`);

const memoryLayerContainerTemplate = Handlebars.compile(`
    <h5 class="memory-layer-header">{{layerDisplayName}} ({{layerName}})</h5>
    <div class="memory-layer-items" id="memory-items-{{trackName}}-{{layerName}}_{{instancePk}}"></div>
`);

const memoryItemTemplate = Handlebars.compile(`
    <b class="memory-item-index">[{{index}}]</b>
    <span class="memory-editable-content" contenteditable="true" 
          onfocus="handleMemoryFocus(this)" 
          onblur="handleMemoryBlur(this, '{{trackName}}', '{{layerName}}', '{{index}}', {{instancePk}})"
          oninput="handleMemoryInput(this)">{{{content}}}</span>
    <div class="memory-item-actions" style="display: none;">
        <button class="btn btn-xs btn-success" onclick="saveMemoryEdit('{{trackName}}', '{{layerName}}', '{{index}}', {{instancePk}})">Save</button>
        <button class="btn btn-xs btn-default" onclick="cancelMemoryEdit('{{trackName}}', '{{layerName}}', '{{index}}', {{instancePk}})">Cancel</button>
    </div>
`);

// Main function to render a single memory item
function renderSidebarMemory(item, instancePk) {
    if (!instancePk) {
        console.error("renderSidebarMemory: instancePk is required.");
        return;
    }
    // Ensure the tab structure exists for this instance
    createMemoryTabs(instancePk);

    const instanceState = getInstanceMemoryState(instancePk);
    const trackContainer = document.getElementById(`memory-track-${item.track}_${instancePk}`);
    if (!trackContainer) {
        console.error(`Memory track container not found for track: ${item.track} in instance ${instancePk}`);
        return;
    }

    // --- Find or Create Layer Container ---
    const layerOrder = { 'ST': 1, 'MT': 2, 'LT': 3 };
    const layerNames = { 'ST': 'Short-Term', 'MT': 'Medium-Term', 'LT': 'Long-Term' };

    const layerContainerId = `memory-layer-container-${item.track}-${item.layer}_${instancePk}`;
    let layerContainer = document.getElementById(layerContainerId);

    // Update token count for this layer
    // Only add tokens if the item is new (not just an update to existing content)
    if (!document.getElementById(`memory-item-${item.track}-${item.layer}-${item.index}_${instancePk}`)) {
        instanceState.memoryLayerTokenCounts[item.track][item.layer] += item.tokens;
    }
    

    if (!layerContainer) {
        layerContainer = document.createElement('div');
        layerContainer.id = layerContainerId;
        layerContainer.className = 'memory-layer-container';
        layerContainer.dataset.order = layerOrder[item.layer] || 99; // Assign order for sorting
        layerContainer.innerHTML = memoryLayerContainerTemplate({
            layerDisplayName: layerNames[item.layer] || item.layer,
            layerName: item.layer,
            trackName: item.track,
            instancePk: instancePk
        });

        // Insert the new layer container in the correct ST -> MT -> LT order
        const existingLayers = trackContainer.querySelectorAll('.memory-layer-container');
        let inserted = false;
        for (const existing of existingLayers) {
            if (parseInt(layerContainer.dataset.order) < parseInt(existing.dataset.order)) {
                trackContainer.insertBefore(layerContainer, existing);
                inserted = true;
                break;
            }
            if (existing.id === layerContainer.id) {
                inserted = true;
                break;
            }
        }
        if (!inserted) {
            trackContainer.appendChild(layerContainer);
        }
    }
    
    // --- Create or Update the Memory Item ---
    const itemsContainer = layerContainer.querySelector('.memory-layer-items');
    const memoryItemId = `memory-item-${item.track}-${item.layer}-${item.index}_${instancePk}`;
    let element = document.getElementById(memoryItemId);

    // HTML content for the individual memory item, now with Save/Cancel buttons
    const itemHtml = memoryItemTemplate({
        index: item.index,
        content: item.content,
        trackName: item.track,
        layerName: item.layer,
        instancePk: instancePk
    });


    if (element) {
        // Update existing element if it's already there, but only if it's not currently being edited
        const editableSpan = element.querySelector('.memory-editable-content');
        if (document.activeElement !== editableSpan) {
            element.innerHTML = itemHtml;
        }
    } else {
        // Create a new element for the memory item
        element = document.createElement('div');
        element.id = memoryItemId;
        element.className = 'memory-item';
        element.innerHTML = itemHtml;
        // Insert the new element in the correct order based on its index
        let inserted = false;
        const existingItems = itemsContainer.children;
        for (let i = 0; i < existingItems.length; i++) {
            const existingItem = existingItems[i];
            const existingIndex = parseInt(existingItem.querySelector('.memory-item-index').textContent.replace('[','').replace(']',''));
            if (item.index < existingIndex) {
                itemsContainer.insertBefore(element, existingItem);
                inserted = true;
                break;
            }
        }
        if (!inserted) {
            itemsContainer.appendChild(element); // If no smaller index found, append to the end
        }
    }
    updateLayerHeaderTokens(item.track, item.layer, instancePk); // Update header after item is added/updated
};

// Function to create the initial tab structure for the memory sidebar
function createMemoryTabs(instancePk) {
    const memoryContainer = document.getElementById(`sidebar-tab-memory_${instancePk}`);
    if (!memoryContainer) {
        console.error(`Memory container for instance ${instancePk} not found.`);
        return;
    }
    
    // Only create if not already initialized for this instance
    if (memoryContainer.querySelector('.memory-tabs')) {
        return; 
    }

    const tracks = [ 'SELF', 'STATUS', 'REVIEW', 'INSIGHTS', 'SYSTEMS', 'GOALS', 'PLANS', 'PREDICTIONS', 'MEMORY'];

    let tabsHtml = '<div class="memory-tabs">';
    tracks.forEach((track, index) => {
        tabsHtml += memoryTabButtonTemplate({
            trackName: track,
            instancePk: instancePk,
            isActive: index === 0
        });
    });
    tabsHtml += '</div>';

    let contentHtml = '<div class="memory-content">';
    tracks.forEach((track, index) => {
        contentHtml += memoryTrackPaneTemplate({
            trackName: track,
            instancePk: instancePk,
            isActive: index === 0
        });
    });
    contentHtml += '</div>';

    memoryContainer.innerHTML = tabsHtml + contentHtml;
    
    // Initialize token counts for all tracks and layers for this instance
    const instanceState = getInstanceMemoryState(instancePk);
    tracks.forEach(track => {
        instanceState.memoryLayerTokenCounts[track] = { 'ST': 0, 'MT': 0, 'LT': 0 };
    });
};

// Function to switch between memory track tabs
function showMemoryTrack(trackName, instancePk) {
    const memoryContainer = document.getElementById(`sidebar-tab-memory_${instancePk}`);
    if (!memoryContainer) {
        console.error(`Memory container for instance ${instancePk} not found for showMemoryTrack.`);
        return;
    }

    // Hide all panes and deactivate all buttons within this specific instance's memory tab
    memoryContainer.querySelectorAll('.memory-track-pane').forEach(pane => pane.classList.remove('active'));
    memoryContainer.querySelectorAll('.memory-tab-btn').forEach(btn => btn.classList.remove('active'));

    // Show the selected pane and activate its button
    const paneToShow = memoryContainer.querySelector(`#memory-track-${trackName}_${instancePk}`);
    if (paneToShow) {
        paneToShow.classList.add('active');
    }
    const btnToActivate = [...memoryContainer.querySelectorAll('.memory-tab-btn')].find(btn => btn.textContent === trackName);
    if (btnToActivate) {
        btnToActivate.classList.add('active');
    }
};

// Function to update the header with token count
function updateLayerHeaderTokens(track, layer, instancePk) {
    const instanceState = getInstanceMemoryState(instancePk);
    const layerHeader = document.getElementById(`memory-layer-container-${track}-${layer}_${instancePk}`).querySelector('.memory-layer-header');
    if (layerHeader && instanceState.memoryLayerTokenCounts[track] && instanceState.memoryLayerTokenCounts[track][layer] !== undefined) {
        const layerNames = { 'ST': 'Short-Term', 'MT': 'Medium-Term', 'LT': 'Long-Term' };
        const tokens = instanceState.memoryLayerTokenCounts[track][layer];
        layerHeader.innerHTML = `${layerNames[layer] || layer} (${layer}) (${tokens} tokens)`;
    }
}


function getInstanceMemoryState(instancePk) {
    if (!window.instanceMemoryStates[instancePk]) {
        window.instanceMemoryStates[instancePk] = {
            memoryLayerTokenCounts: { 'SELF': { 'ST': 0, 'MT': 0, 'LT': 0 }, 'STATUS': { 'ST': 0, 'MT': 0, 'LT': 0 }, 
                                    'REVIEW': { 'ST': 0, 'MT': 0, 'LT': 0 }, 'INSIGHTS': { 'ST': 0, 'MT': 0, 'LT': 0 },
                                    'SYSTEMS': { 'ST': 0, 'MT': 0, 'LT': 0 }, 'GOALS': { 'ST': 0, 'MT': 0, 'LT': 0 },
                                    'PLANS': { 'ST': 0, 'MT': 0, 'LT': 0 }, 'PREDICTIONS': { 'ST': 0, 'MT': 0, 'LT': 0 },
                                    'MEMORY': { 'ST': 0, 'MT': 0, 'LT': 0 } },
            // Add any other instance-specific state variables here
        };
    }
    return window.instanceMemoryStates[instancePk];
}

function handleMemoryFocus(element) {
    // Store the original value only if it hasn't been stored already
    if (element.dataset.originalValue === undefined) {
        element.dataset.originalValue = element.textContent.trim();
    }
    // Show the action buttons on focus to indicate edit mode
    const memoryItem = element.closest('.memory-item');
    if (memoryItem) {
        const actions = memoryItem.querySelector('.memory-item-actions');
        if (actions) {
            actions.style.display = 'block';
        }
    }
}

function handleMemoryInput(element) {
    const memoryItem = element.closest('.memory-item');
    if (!memoryItem) return;
    const actions = memoryItem.querySelector('.memory-item-actions');
    const originalValue = element.dataset.originalValue || '';
    const currentValue = element.textContent.trim();

    if (currentValue !== originalValue) {
        actions.style.display = 'block';
    } else {
        actions.style.display = 'none';
    }
}

function saveMemoryEdit(track, layer, index, instancePk) {
    const memoryItemId = `memory-item-${track}-${layer}-${index}_${instancePk}`;
    const memoryItem = document.getElementById(memoryItemId);
    if (!memoryItem) return;

    const editableSpan = memoryItem.querySelector('.memory-editable-content');
    const actions = memoryItem.querySelector('.memory-item-actions');
    const newContent = editableSpan.textContent.trim();

    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'update_memory_item',
            payload: {
                instance_pk: instancePk, 
                track: track,
                layer: layer,
                index: index,
                content: newContent
            }
        }));
        addToConsoleArea(`Client: Saving memory item for instance ${instancePk}: ${track} ${layer} ${index}`, 'info');
        
        // Update the original value and hide controls
        editableSpan.dataset.originalValue = newContent;
        actions.style.display = 'none';
        delete editableSpan.dataset.originalValue; // clean up for next edit

    } else {
        addToConsoleArea('WebSocket is not connected. Cannot save memory changes.', 'error');
    }
}

function cancelMemoryEdit(track, layer, index, instancePk) {
    const memoryItemId = `memory-item-${track}-${layer}-${index}_${instancePk}`;
    const memoryItem = document.getElementById(memoryItemId);
    if (!memoryItem) return;

    const editableSpan = memoryItem.querySelector('.memory-editable-content');
    const actions = memoryItem.querySelector('.memory-item-actions');
    
    // Revert to original value and hide controls
    editableSpan.textContent = editableSpan.dataset.originalValue || '';
    actions.style.display = 'none';
    // Clear the stored original value on cancel
    delete editableSpan.dataset.originalValue;
}

function handleMemoryBlur(element, track, layer, index, instancePk) {
    // Use a short timeout to allow click events on the Save/Cancel buttons to register
    setTimeout(() => {
        // If the focus is now on one of the action buttons, don't do anything
        if (document.activeElement.closest('.memory-item-actions')) {
            return;
        }

        // If the element is blurred and not saved, cancel the edit
        const memoryItem = element.closest('.memory-item');
        if (memoryItem) {
            const actions = memoryItem.querySelector('.memory-item-actions');
            if (actions && actions.style.display !== 'none') {
                cancelMemoryEdit(track, layer, index, instancePk);
            }
        }
    }, 100); // 100ms delay
}