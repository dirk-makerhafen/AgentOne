// This file manages the rendering and interactions for the Memory sidebar.

let instanceMemoryStates = {};

// --- STATE MANAGEMENT ---

function resetMemoryState(instancePk) {
    instanceMemoryStates[instancePk] = {
        items: {},
        activeFilters: new Set(['ST', 'MT', 'LT']), // Default to all active
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

    const itemsToProcess = Array.isArray(payload) ? payload : [payload];
    itemsToProcess.forEach(item => {
        if (item.content === '[DELETED]') {
            delete state.items[item.id];
        } else {
            state.items[item.id] = item;
        }
    });

    initializeSidebarMemoryUI(instancePk);
    filterAndRenderMemoryItems(instancePk);
}

function initializeSidebarMemoryUI(instancePk) {
    const sidebarMemoryContainerTemplate = getTemplate('SidebarMemoryTemplate');
    const tabContent = document.getElementById(`sidebar-tab-memory_${instancePk}`);
    if (tabContent && tabContent.children.length === 0) {
        tabContent.innerHTML = sidebarMemoryContainerTemplate({ instancePk });
        renderMemoryFilters(instancePk);
    }
}

function renderMemoryFilters(instancePk) {
    const memoryFilterButtonTemplate = getTemplate('SidebarMemoryFilterButtonTemplate');
    const state = getInstanceMemoryState(instancePk);
    const filterContainer = document.getElementById(`sidebar-memory-filters_${instancePk}`);
    if (!filterContainer) return;

    filterContainer.innerHTML = '';
    const layers = ['ST', 'MT', 'LT'];
    layers.forEach(layer => {
        filterContainer.insertAdjacentHTML('beforeend', memoryFilterButtonTemplate({
            layer: layer,
            isActive: state.activeFilters.has(layer),
            instancePk: instancePk
        }));
    });
}

function filterAndRenderMemoryItems(instancePk) {
    const memoryItemTemplate = getTemplate('SidebarMemoryItemTemplate');
    const state = getInstanceMemoryState(instancePk);
    const listContainer = document.getElementById(`sidebar-memory-list-${instancePk}`);
    if (!listContainer) return;

    const itemsArray = Object.values(state.items);
    itemsArray.sort((a, b) => {
        const layerOrder = { 'LT': 0, 'MT': 1, 'ST': 2 };
        if (layerOrder[a.layer] !== layerOrder[b.layer]) return layerOrder[a.layer] - layerOrder[b.layer];
        return b.id - a.id;
    });

    let html = '<ul>';
    itemsArray.forEach(item => {
        if (state.activeFilters.has(item.layer)) {
            html += memoryItemTemplate({ item: item, instancePk: instancePk });
        }
    });
    html += '</ul>';
    listContainer.innerHTML = html;
}

// --- INLINE EVENT HANDLERS ---

function toggleMemoryFilter(button, layer, instancePk) {
    const state = getInstanceMemoryState(instancePk);
    if (state.activeFilters.has(layer)) {
        state.activeFilters.delete(layer);
        button.classList.remove('active');
    } else {
        state.activeFilters.add(layer);
        button.classList.add('active');
    }
    filterAndRenderMemoryItems(instancePk);
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

    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'direct_tool_call',
            payload: {
                tool_calls: [{
                    function_name: 'memory_correct',
                    arguments: {
                        track: editableValueElement.dataset.itemTrack,
                        layer: editableValueElement.dataset.itemLayer,
                        index: itemId,
                        content: newValue
                    }
                }],
                instance_pk: instancePk
            }
        }));
    }
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
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'direct_tool_call',
                payload: {
                    tool_calls: [{
                        function_name: 'memory_add',
                        arguments: { track: track, layer: layer, content: newContent }
                    }],
                    instance_pk: instancePk
                }
            }));
        }
    }
}

function deleteMemoryItem(event, instancePk) {
    event.stopPropagation();
    const button = event.currentTarget;
    const itemId = button.dataset.itemId;
    const track = button.dataset.itemTrack;
    const layer = button.dataset.itemLayer;
    if (confirm(`Are you sure you want to delete memory item ${itemId} from ${track} - ${layer}?`)) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'direct_tool_call',
                payload: {
                    tool_calls: [{
                        function_name: 'memory_correct',
                        arguments: {
                            track: track,
                            layer: layer,
                            index: itemId,
                            content: '[DELETED]'
                        }
                    }],
                    instance_pk: instancePk
                }
            }));
        }
    }
}

function repositionMemoryItem(event, instancePk) {
    event.stopPropagation();
    const button = event.currentTarget;
    const itemId = button.dataset.itemId;
    const track = button.dataset.itemTrack;
    const layer = button.dataset.itemLayer;
    const steps = button.dataset.direction === 'up' ? -1 : 1;

    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'direct_tool_call',
            payload: {
                tool_calls: [{
                    function_name: 'memory_reposition',
                    arguments: {
                        track: track, layer: layer, index: itemId, steps: steps
                    }
                }],
                instance_pk: instancePk
            }
        }));
    }
}