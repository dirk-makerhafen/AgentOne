// This file manages the rendering and interactions for the Filesystem sidebar.

let instanceFilesystemStates = {};

// --- STATE MANAGEMENT ---

function resetFilesystemState(instancePk) {
    instanceFilesystemStates[instancePk] = {
        items: {},
        sortColumn: 'path',
        sortDirection: 'asc'
    };
};

function getInstanceFilesystemState(instancePk) {
    if (!instanceFilesystemStates[instancePk]) {
        resetFilesystemState(instancePk);
    }
    return instanceFilesystemStates[instancePk];
}

// --- RENDERING ---

function renderSidebarFilesystem(payload, instancePk) {
    const state = getInstanceFilesystemState(instancePk);
    
    const itemsToProcess = Array.isArray(payload) ? payload : [payload];

    itemsToProcess.forEach(item => {
        state.items[item.id] = item;
    });

    initializeFilesystemSidebarUI(instancePk);
    sortAndRenderFilesystemItems(instancePk);
    updateTotalTokensDisplay(instancePk);
};

function initializeFilesystemSidebarUI(instancePk) {
    const sidebarFilesystemContainerTemplate = getTemplate('SidebarFilesystemTemplate');
    const tabContent = document.getElementById(`sidebar-tab-filesystem_${instancePk}`);
    if (tabContent && tabContent.children.length === 0) {
        tabContent.innerHTML = sidebarFilesystemContainerTemplate({ instancePk });
    }
}

function sortAndRenderFilesystemItems(instancePk) {
    const sidebarFilesystemItemTemplate = getTemplate('SidebarFilesystemItemTemplate');
    const state = getInstanceFilesystemState(instancePk);
    const listContainer = document.getElementById(`sidebar-filesystem-list-${instancePk}`);
    if (!listContainer) return;

    const itemsArray = Object.values(state.items);

    itemsArray.sort((a, b) => {
        let compareA = a[state.sortColumn];
        let compareB = b[state.sortColumn];

        if (state.sortColumn === 'size') {
            compareA = a.tokens || 0;
            compareB = b.tokens || 0;
        }

        if (compareA < compareB) return state.sortDirection === 'asc' ? -1 : 1;
        if (compareA > compareB) return state.sortDirection === 'asc' ? 1 : -1;
        return 0;
    });

    listContainer.innerHTML = '';
    itemsArray.forEach(item => {
        listContainer.insertAdjacentHTML('beforeend', sidebarFilesystemItemTemplate({...item, instancePk}));
    });
}

function updateTotalTokensDisplay(instancePk) {
    const state = getInstanceFilesystemState(instancePk);
    const totalTokens = Object.values(state.items).reduce((sum, item) => sum + (item.tokens || 0), 0);
    const tokenDisplay = document.getElementById(`total-fs-tokens_${instancePk}`);
    if (tokenDisplay) {
        tokenDisplay.textContent = totalTokens;
    }
}

// --- INLINE EVENT HANDLERS ---

function handleFilesystemSort(column, instancePk) {
    const state = getInstanceFilesystemState(instancePk);
    if (state.sortColumn === column) {
        state.sortDirection = state.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        state.sortColumn = column;
        state.sortDirection = 'asc';
    }
    sortAndRenderFilesystemItems(instancePk);
};

function saveSidebarFsPermission(instancePk, key, value) {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        let payloadData = {};
        payloadData[key] = value;
        websocket.send(JSON.stringify({
            type: 'update_agent_instance',
            payload: {
                instance_pk: instancePk,
                ...payloadData
            }
        }));
    }
}

function sidebarFsLoad(event, instancePk) {
    event.stopPropagation();
    const container = document.getElementById(`sidebar-tab-filesystem_${instancePk}`);
    if (!container) return;

    const pathInput = container.querySelector(`#sidebar-fs-path-input_${instancePk}`);
    
    const paths = pathInput.value.split('\n').map(p => p.trim()).filter(Boolean);

    if (paths.length > 0) {
        paths.forEach(path => {
            if (websocket && websocket.readyState === WebSocket.OPEN) {
                websocket.send(JSON.stringify({
                    type: 'direct_tool_call',
                    payload: {
                        tool_calls: [{
                            function_name: 'fs_load',
                            arguments: { path: path, recursive: false, mode: 'full' }
                        }],
                        instance_pk: instancePk
                    }
                }));
            }
        });
        pathInput.value = '';
    }
}

function sidebarFsPin(event, instancePk) {
    event.stopPropagation();
    const target = event.currentTarget;
    const fslogentryPk = target.dataset.fslogentryPk;
    const isPinned = target.dataset.isPinned === 'true';

    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'update_fslogentry_flags',
            payload: {
                instance_pk: instancePk,
                fslogentry_pk: fslogentryPk,
                pin_to_context: !isPinned
            }
        }));
    }
}

function sidebarFsToggleLoadMode(event, instancePk) {
    event.stopPropagation();
    const target = event.currentTarget;
    const path = target.dataset.path;
    const currentMode = target.dataset.loadMode;
    const newMode = currentMode === 'full' ? 'summary' : 'full';

    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'direct_tool_call',
            payload: {
                tool_calls: [{
                    function_name: 'fs_load',
                    arguments: { path: path, mode: newMode }
                }],
                instance_pk: instancePk
            }
        }));
    }
}

function sidebarFsUnload(event, instancePk) {
    event.stopPropagation();
    const path = event.currentTarget.dataset.path;
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'direct_tool_call',
            payload: {
                tool_calls: [{
                    function_name: 'fs_unload',
                    arguments: { path: path }
                }],
                instance_pk: instancePk
            }
        }));
    }
}

function sidebarFsLoadItem(event, instancePk) {
    event.stopPropagation();
    const path = event.currentTarget.dataset.path;
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'direct_tool_call',
            payload: {
                tool_calls: [{
                    function_name: 'fs_load',
                    arguments: { path: path, mode: 'full' } // Always load full when clicking the load icon
                }],
                instance_pk: instancePk
            }
        }));
    }
}