// This file manages the rendering and interactions for the Memory sidebar.

let instanceMemoryStates = {};

// --- STATE MANAGEMENT ---

function resetMemoryState(instancePk) {
    instanceMemoryStates[instancePk] = {
        items: {},
        activeTrack: 'REVIEW', // Default to REVIEW track
    };
}

function getInstanceMemoryState(instancePk) {
    if (!instanceMemoryStates[instancePk]) {
        resetMemoryState(instancePk);
    }
    return instanceMemoryStates[instancePk];
}

// --- RENDERING ---

function renderSidebarMemory(payload, instancePk) {
    const state = getInstanceMemoryState(instancePk);

    // Process incoming payload(s)
    const itemsToProcess = Array.isArray(payload) ? payload : [payload];
    itemsToProcess.forEach(item => {
        if (item.content === '[DELETED]') {
            delete state.items[item.id];
        } else {
            state.items[item.id] = item;
        }
    });

    initializeSidebarMemoryUI(instancePk);
    renderMemoryTrackButtons(instancePk); // Render track buttons first
    renderMemoryItemsForActiveTrack(instancePk); // Then render items for the active track
}

function initializeSidebarMemoryUI(instancePk) {
    const sidebarMemoryContainerTemplate = getTemplate('SidebarMemoryTemplate');
    const tabContent = document.getElementById(`sidebar-tab-memory_${instancePk}`);
    if (tabContent) { // Removed the children.length check here
        tabContent.innerHTML = sidebarMemoryContainerTemplate({ instancePk });
    }
}

function renderMemoryTrackButtons(instancePk) {
    const state = getInstanceMemoryState(instancePk);
    const tabsContainer = document.getElementById(`sidebar-memory-track-buttons_${instancePk}`);
    if (!tabsContainer) return;

    tabsContainer.innerHTML = '';
    const uniqueTracks = Array.from(new Set(Object.values(state.items).map(item => item.track))).sort();
    const allPossibleTracks = ['REVIEW', 'SELF', 'INSIGHTS', 'GOALS', 'STATUS', 'SYSTEMS', 'PLANS', 'PREDICTIONS', 'MEMORY'];

    // Ensure default tracks are present even if no items exist for them
    const tracksToShow = Array.from(new Set([...allPossibleTracks, ...uniqueTracks])).sort();

    tracksToShow.forEach(track => {
        const button = document.createElement('button');
        button.className = `memory-tab-btn ${state.activeTrack === track ? 'active' : ''}`;
        button.dataset.trackName = track;
        button.onclick = (event) => toggleMemoryTrack(event, track, instancePk);
        button.textContent = track;
        tabsContainer.appendChild(button);
    });
}

function renderMemoryItemsForActiveTrack(instancePk) {
    const memoryItemTemplate = getTemplate('SidebarMemoryItemTemplate');
    const state = getInstanceMemoryState(instancePk);
    const itemsListContainer = document.getElementById(`memory-items-actual-list_${instancePk}`); // Updated target ID
    const noItemsMessage = document.getElementById(`no-memory-items-message_${instancePk}`);

    if (!itemsListContainer || !noItemsMessage) return;

    const itemsForActiveTrack = Object.values(state.items).filter(item => item.track === state.activeTrack);

    if (itemsForActiveTrack.length === 0) {
        itemsListContainer.innerHTML = ''; // Clear actual list
        noItemsMessage.style.display = 'block'; // Show no items message
        return;
    } else {
        noItemsMessage.style.display = 'none'; // Hide no items message
    }

    // Group items by layer
    const groupedByLayer = { 'LT': [], 'MT': [], 'ST': [] };
    itemsForActiveTrack.forEach(item => {
        if (groupedByLayer[item.layer]) {
            groupedByLayer[item.layer].push(item);
        }
    });

    // Sort items within each layer (newest first for ST/MT, oldest for LT might make sense, but consistency for now)
    for (const layer in groupedByLayer) {
        groupedByLayer[layer].sort((a, b) => b.id - a.id); // Sort by ID descending (newest first)
    }

    // Build HTML for all layers within the active track
    let htmlContent = '';
    const layerOrder = ['LT', 'MT', 'ST']; // Display order for layers
    layerOrder.forEach(layer => {
        if (groupedByLayer[layer].length > 0) {
            htmlContent += `<div class="memory-layer-group">`;
            htmlContent += `<h5 class="memory-layer-header">${layer} Layer</h5>`;
            htmlContent += `<ul>`;
            groupedByLayer[layer].forEach(item => {
                htmlContent += memoryItemTemplate({ item: item, instancePk: instancePk });
            });
            htmlContent += `</ul>`;
            htmlContent += `</div>`;
        }
    });

    itemsListContainer.innerHTML = htmlContent; // Render into the new target div
}

// --- INLINE EVENT HANDLERS ---
function toggleMemoryTrack(event, track, instancePk) {
    event.stopPropagation();
    const state = getInstanceMemoryState(instancePk);

    // Update active track in state
    state.activeTrack = track;

    // Update button active states
    const tabsContainer = document.getElementById(`sidebar-memory-track-buttons_${instancePk}`);
    if (tabsContainer) {
        tabsContainer.querySelectorAll('.memory-tab-btn').forEach(button => {
            if (button.dataset.trackName === track) {
                button.classList.add('active');
            } else {
                button.classList.remove('active');
            }
        });
    }

    // Re-render memory items for the newly active track
    renderMemoryItemsForActiveTrack(instancePk);
}

function handleMemoryFocus(event) {
    const editableElement = event.target;
    const itemId = editableElement.dataset.itemId;
    const editActions = document.getElementById(`memory-edit-actions-${itemId}`);
    if (editActions) {
        editActions.classList.remove('hidden');
        editableElement.dataset.originalValue = editableElement.textContent;
    }
}

function handleMemoryBlur(event) {
    const editableElement = event.target;
    const itemId = editableElement.dataset.itemId;
    const editActions = document.getElementById(`memory-edit-actions-${itemId}`);
    setTimeout(() => {
        if (editActions && !editActions.contains(document.activeElement)) {
            editActions.classList.add('hidden');
        }
    }, 100);
}

function saveMemoryEdit(event, instancePk) {
    event.stopPropagation();
    const button = event.currentTarget;
    const itemId = button.dataset.itemId;
    const editableValueElement = document.getElementById(`memory-item-content-${itemId}`);
    const newValue = editableValueElement.textContent;
    directToolCallApi.call(instancePk, [{
            function_name: 'memory_correct',
            arguments: {
                track: editableValueElement.dataset.itemTrack,
                layer: editableValueElement.dataset.itemLayer,
                index: itemId,
                content: newValue
            }
        }]
    )
    editableValueElement.blur();
}

function cancelMemoryEdit(event) {
    event.stopPropagation();
    const button = event.currentTarget;
    const itemId = button.dataset.itemId;
    const editableValueElement = document.getElementById(`memory-item-content-${itemId}`);
    if (editableValueElement) {
        editableValueElement.textContent = editableValueElement.dataset.originalValue || editableValueElement.textContent;
    }
    editableValueElement.blur();
}

function addMemoryItem(event, instancePk) {
    event.stopPropagation();
    const button = event.currentTarget;
    const track = button.dataset.itemTrack;
    const layer = button.dataset.itemLayer;
    const newContent = prompt(`Enter new memory content for ${track} - ${layer}:`);
    if (newContent) {
        directToolCallApi.call(instancePk,  [{
                function_name: 'memory_add',
                arguments: { track: track, layer: layer, content: newContent }
            }]
        );
    }
}

function deleteMemoryItem(event, instancePk) {
    event.stopPropagation();
    const button = event.currentTarget;
    const itemId = button.dataset.itemId;
    const track = button.dataset.itemTrack;
    const layer = button.dataset.itemLayer;
    if (confirm(`Are you sure you want to delete memory item ${itemId} from ${track} - ${layer}?`)) {
        directToolCallApi.call(instancePk,[{
                function_name: 'memory_correct',
                arguments: {
                    track: track,
                    layer: layer,
                    index: itemId,
                    content: '[DELETED]'
                }}]);
    }
}

function repositionMemoryItem(event, instancePk) {
    event.stopPropagation();
    const button = event.currentTarget;
    const itemId = button.dataset.itemId;
    const track = button.dataset.itemTrack;
    const layer = button.dataset.itemLayer;
    const steps = button.dataset.direction === 'up' ? -1 : 1;
    directToolCallApi.call(instancePk, [{
            function_name: 'memory_reposition',
            arguments: {
                track: track, layer: layer, index: itemId, steps: steps
            }
        }],
    );
}