// This file manages the rendering and interactions for the Filesystem sidebar.

let instanceFilesystemStates = {};

function resetFilesystemState(instancePk) {
    instanceFilesystemStates[instancePk] = {
        items: {}, // Keyed by path, storing the newest FsLogEntry object
        sortColumn: 'path',
        sortDirection: 'asc',
        showUnloaded: false // Flag to control visibility of unloaded items
    };
};

function getInstanceFilesystemState(instancePk) {
    if (!instanceFilesystemStates[instancePk]) resetFilesystemState(instancePk);
    return instanceFilesystemStates[instancePk];
}

function sidebarFsToggleView(event, instancePk) {
    event.stopPropagation();
    const state = getInstanceFilesystemState(instancePk);
    state.showUnloaded = !state.showUnloaded;

    const icon = document.getElementById(`fs-view-toggle_${instancePk}`);
    if (icon) {
        icon.classList.toggle('fa-eye', !state.showUnloaded);
        icon.classList.toggle('fa-eye-slash', state.showUnloaded);
        icon.classList.toggle('active', state.showUnloaded);
    }
    
    const listContainer = document.getElementById(`sidebar-filesystem-list-${instancePk}`);
    if (listContainer) {
        listContainer.classList.toggle('show-unloaded', state.showUnloaded);
    }
}

function renderSidebarFilesystem(payload, instancePk) {
    const state = getInstanceFilesystemState(instancePk);
    initializeFilesystemSidebarUI(instancePk);

    // Defensive Rendering: Ensure the header content exists before we proceed.
    // This prevents a race condition where updateTotalTokensDisplay runs before
    // renderSidebarFilesystemHeader has created the target DOM element.
    const headerContainer = document.getElementById(`sidebar-filesystem-header-container_${instancePk}`);
    if (headerContainer && headerContainer.children.length === 0) {
        const instanceData = window.allAgentInstances[instancePk];
        if (instanceData) {
            renderSidebarFilesystemHeader(instanceData);
        }
    }

    if (Array.isArray(payload)) {
        // Initial load of the list
        state.items = {}; // Clear existing items for a fresh list load
        payload.forEach(item => {
            // Only store the newest version for each path
            if (!state.items[item.path] || item.id > state.items[item.path].id) {
                state.items[item.path] = item;
            }
        });
        sortAndRenderFilesystemItems(instancePk);
    } else {
        // Single item update
        if (!state.items[payload.path] || payload.id > state.items[payload.path].id) {
            state.items[payload.path] = payload;
            renderSingleFilesystemItem(payload, instancePk);
        }
    }
    // Update tokens after any change (initial load or single update)
    updateTotalTokensDisplay(instancePk);
}


function renderSingleFilesystemItem(item, instancePk) {
    const sidebarFilesystemItemTemplate = getTemplate('SidebarFilesystemItemTemplate');
    const listContainer = document.getElementById(`sidebar-filesystem-list-${instancePk}`);
    if (!listContainer) return;

    // Use data-path to find the existing item for replacement
    const existingItem = listContainer.querySelector(`.sidebar-fs-item[data-path="${item.path}"]`);
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = sidebarFilesystemItemTemplate({...item, instancePk});
    const newItemElement = tempDiv.firstElementChild;

    if (existingItem) {
        existingItem.replaceWith(newItemElement);
    } else {
        // If it's a new path, add it to the list and re-sort to maintain order
        listContainer.appendChild(newItemElement);
        sortAndRenderFilesystemItems(instancePk);
    }
}

function initializeFilesystemSidebarUI(instancePk) {
    const sidebarFilesystemContainerTemplate = getTemplate('SidebarFilesystemTemplate');
    const tabContent = document.getElementById(`sidebar-tab-filesystem_${instancePk}`);
    if (tabContent && tabContent.children.length === 0) {
        tabContent.innerHTML = sidebarFilesystemContainerTemplate({ instancePk });
    }
}

function sortAndRenderFilesystemItems(instancePk) {
    const state = getInstanceFilesystemState(instancePk);
    const listContainer = document.getElementById(`sidebar-filesystem-list-${instancePk}`);
    if (!listContainer) return;

    listContainer.classList.toggle('show-unloaded', state.showUnloaded);

    const itemsArray = Object.values(state.items);
    itemsArray.sort((a, b) => {
        let valA = a[state.sortColumn] || (state.sortColumn === 'size' ? 0 : '');
        let valB = b[state.sortColumn] || (state.sortColumn === 'size' ? 0 : '');
        if (state.sortColumn === 'size') { valA = a.tokens; valB = b.tokens; }
        if (valA < valB) return state.sortDirection === 'asc' ? -1 : 1;
        if (valA > valB) return state.sortDirection === 'asc' ? 1 : -1;
        return 0;
    });

    // Get current DOM elements to compare paths
    const currentDomPaths = new Set();
    listContainer.querySelectorAll('.sidebar-fs-item').forEach(el => {
        currentDomPaths.add(el.dataset.path);
    });

    const newDomPaths = new Set(itemsArray.map(item => item.path));

    // Remove items from DOM that are no longer in state.items
    currentDomPaths.forEach(domPath => {
        if (!newDomPaths.has(domPath)) {
            const elToRemove = listContainer.querySelector(`.sidebar-fs-item[data-path="${domPath}"]`);
            if (elToRemove) elToRemove.remove();
        }
    });

    // Now, clear the list container and re-add all items from the sorted state
    // This ensures correct order and replaces any existing items with their newest versions
    listContainer.innerHTML = '';
    const fragment = document.createDocumentFragment();
    itemsArray.forEach(item => {
        const sidebarFilesystemItemTemplate = getTemplate('SidebarFilesystemItemTemplate');
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = sidebarFilesystemItemTemplate({...item, instancePk});
        fragment.appendChild(tempDiv.firstElementChild);
    });
    listContainer.appendChild(fragment);
}


function updateTotalTokensDisplay(instancePk) {
    const state = getInstanceFilesystemState(instancePk);
    const totalTokens = Object.values(state.items)
        .filter(item => item.is_loaded)
        .reduce((sum, item) => sum + (item.tokens || 0), 0);
    const tokenDisplay = document.getElementById(`total-fs-tokens_${instancePk}`);
    if (tokenDisplay) tokenDisplay.textContent = totalTokens;
}

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
    agentInstanceApi.update(instancePk, { [key]: value });
}

function sidebarFsLoad(event, instancePk) {
    event.stopPropagation();
    const pathInput = document.querySelector(`#sidebar-fs-path-input_${instancePk}`);
    const paths = pathInput.value.split('\n').map(p => p.trim()).filter(Boolean);
    if (paths.length > 0) {
        const tool_calls = paths.map(rawPath => {
            let path = rawPath;
            let recursive = false;

            if (path.endsWith('*')) {
                recursive = true;
                path = path.slice(0, -1); // Remove the '*'
            }

            if (path === '') {
                path = '.';
            }

            return {
                function_name: 'fs_load',
                arguments: { path, recursive, mode: 'full' }
            };
        });
        directToolCallApi.call(instancePk, tool_calls);
        pathInput.value = '';
    }
}

function sidebarFsPin(event, instancePk) {
    event.stopPropagation();
    const path = event.currentTarget.dataset.path;
    filesystemApi.togglePin(instancePk, path);
}

function sidebarFsToggleLoadMode(event, instancePk) {
    event.stopPropagation();
    const { path, loadMode } = event.currentTarget.dataset;
    const newMode = loadMode === 'full' ? 'summary' : 'full';
    directToolCallApi.call(instancePk, [{ function_name: 'fs_load', arguments: { path, mode: newMode } }]);
}

function sidebarFsUnload(event, instancePk) {
    event.stopPropagation();
    const path = event.currentTarget.dataset.path;
    directToolCallApi.call(instancePk, [{ function_name: 'fs_unload', arguments: { path } }]);
}

function sidebarFsLoadItem(event, instancePk) {
    event.stopPropagation();
    const path = event.currentTarget.dataset.path;
    directToolCallApi.call(instancePk, [{ function_name: 'fs_load', arguments: { path, mode: 'full' } }]);
}
