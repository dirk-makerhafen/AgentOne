
const sidebarFilesystemContainerTemplate = Handlebars.compile(`
    <div class="sidebar-section">
        <div id="sidebar-filesystem-header-container_{{instancePk}}">
            <!-- The new, combined header will be rendered here -->
        </div>
        
        <div class="sidebar-fs-list-header" id="sidebar-fs-list-header_{{instancePk}}">
            <span class="sort-header-item" data-sort-column="path" onclick="handleFilesystemSort('path', {{instancePk}})">Name <i class="fa fa-sort"></i></span>
            <span class="sort-header-item" data-sort-column="size" onclick="handleFilesystemSort('size', {{instancePk}})">Size <i class="fa fa-sort"></i></span>
            <span class="sort-header-item sort-header-actions" data-sort-column="actions" onclick="handleFilesystemSort('actions', {{instancePk}})">Actions <i class="fa fa-sort"></i></span>
        </div>

        <div id="sidebar-filesystem-list-{{instancePk}}" class="sidebar-fs-list">
            <!-- Loaded files and directories will be rendered here -->
        </div>
        <div class="sidebar-fs-input-container">
            <textarea id="sidebar-fs-path-input_{{instancePk}}" rows="3" placeholder="Enter one path per line..."></textarea>
            <button id="sidebar-fs-load-btn_{{instancePk}}" class="sidebar-button">Load</button>
        </div>
        <div class="sidebar-fs-rules-container">
            <i class="fa fa-question-circle fs-rules-help" title="Access Rules Syntax:\n- Deny: !path/to/deny\n- Allow Write: >path/to/allow\n- Read-only: <path/to/file\nRules are checked in order. Wildcards (*) are supported. Default is deny."></i>
            <textarea id="fs-access-rules_{{instancePk}}" class="fs-rules-textarea" placeholder="Access Rules (!/denied, >/writeok, </readonly)" onblur="saveSidebarFsPermission('{{instancePk}}', 'access_rules', this.value)"></textarea>
        </div>
    </div>`);
    

const sidebarFilesystemItemTemplate = Handlebars.compile(`
<div id="fs-item-{{id}}" class="sidebar-fs-item {{#unless is_loaded}}fs-item-unloaded{{/unless}}" data-timestamp="{{created_at}}" data-is-loaded="{{is_loaded}}" data-instance-pk="{{instancePk}}" data-load-mode="{{load_mode}}">
    <i class="fa {{#if is_dir}}fa-folder-o{{else}}{{#if is_summary}}fa-file{{else}}fa-file-o{{/if}}{{/if}} item-icon"></i>
    
    <span class="fs-path item-text" title="{{path}}">{{path}}</span>
    <span class="fs-token-count">{{tokens}}</span>
    {{#if deleted}}<span class="item-deleted" title="File no longer exists"><i class="fa fa-exclamation-circle"></i></span>{{/if}}
    <div class="item-actions">
        <i class="fa fa-thumb-tack fs-pin-btn {{#if is_pinned}}pinned{{/if}}" 
           data-path="{{path}}" 
           data-type="{{#if is_dir}}directory{{else}}file{{/if}}"
           title="{{#if is_pinned}}Unpin this item{{else}}Pin this item{{/if}}"></i>
        {{#unless is_dir}}
            {{#if is_loaded}}
                {{#if is_summary}}
                    <i class="fa fa-expand fs-toggle-load-mode-btn" data-path="{{path}}" data-load-mode="summary" title="Switch to Full Load Mode"></i>
                {{else}}
                    <i class="fa fa-compress fs-toggle-load-mode-btn" data-path="{{path}}" data-load-mode="full" title="Switch to Summary Load Mode"></i>
                {{/if}}
            {{/if}}
        {{/unless}}
        <i class="fa fa-sign-out fs-unload-btn" data-path="{{path}}" title="Unload this item" style="{{#unless is_loaded}}display: none;{{/unless}}"></i>
        <i class="fa fa-sign-in fs-load-btn" data-path="{{path}}" title="Load this item" style="{{#if is_loaded}}display: none;{{/if}}"></i>
    </div>
</div>`);

let instanceFilesystemStates = {};

function renderSidebarFilesystem(payload, instancePk) {
    //console.log(`[FS Sidebar] Incoming Payload for instance ${instancePk}:`, payload);

    const instanceState = getInstanceFilesystemState(instancePk);
    const container = document.getElementById(`sidebar-filesystem-list-${instancePk}`);
    if (!container) {
        //console.error(`[FS Sidebar] Container sidebar-filesystem-list-${instancePk} not found.`);
        return;
    }

    // If it's an InitialFilesystemState message, clear everything and re-render.
    if (payload.action === 'initial_state') {
        console.log(`[FS Sidebar - Debug] Processing initial_state for instance ${instancePk}.`);
        instanceState.sidebarPathToIdMap = {};
        instanceState.totalFilesystemTokens = 0;
        container.innerHTML = ''; // Clear all existing items
        payload.items.forEach(item => { // Iterate over items in initial_state payload
            renderSidebarFilesystem(item, instancePk); // Recursively render each item
        });
        updateTotalTokensDisplay(instancePk);
        return; // Exit after processing initial state
    }

    const path = payload.path;
    const newFsLogEntryId = payload.id; // This is the FsLogEntry.id
    const newElementDomId = `fs-item-${newFsLogEntryId}`; // Ensure DOM ID uses newFsLogEntryId

    
    // Get the *current* FsLogEntry ID stored in the map for this path
    const currentStoredFsLogEntryId = instanceState.sidebarPathToIdMap[path];
    const currentElementDomId = currentStoredFsLogEntryId ? `fs-item-${currentStoredFsLogEntryId}` : null;
    let existingElement = currentElementDomId ? document.getElementById(currentElementDomId) : null;
    

    // Determine if this incoming payload is newer than what we currently have displayed for this path
    let isNewerPayload = true; // Assume newer if no existing item
    if (existingElement) {
        const existingTimestamp = existingElement.getAttribute('data-timestamp'); // Timestamp of the currently displayed item
        
        const isNewerTimestamp = new Date(payload.created_at) > new Date(existingTimestamp);
        const isSameTimestamp = new Date(payload.created_at).getTime() === new Date(existingTimestamp).getTime();
        const isNewerIdOnSameTimestamp = isSameTimestamp && newFsLogEntryId > currentStoredFsLogEntryId;

        // A payload is considered "newer" if its timestamp is later, OR if timestamps are the same and its ID is higher.
        // It's "not newer" if its timestamp is older, OR if timestamps are the same and its ID is less than or equal to the current.
        if (!isNewerTimestamp && !isNewerIdOnSameTimestamp) {
            isNewerPayload = false; // The incoming payload is older or the same as the current display
        }
        
    }

    if (!isNewerPayload) {
        return; // Ignore older or duplicate payloads
    }

    // Prepare template data
    const is_loaded = payload.load_mode !== null;
    const templateData = {
        id: newFsLogEntryId, // Use the new FsLogEntry ID for the rendered item's ID
        path: path,
        tokens: payload.tokens,
        deleted: !payload.exists_on_fs,
        is_dir: payload.is_directory,
        is_pinned: payload.is_pinned,
        is_loaded: is_loaded,
        is_summary: payload.load_mode === "summary",
        created_at: payload.created_at,
        load_mode: payload.load_mode,
        instancePk: instancePk
    };
    const renderedHtml = sidebarFilesystemItemTemplate(templateData);

    // Create a temporary div to parse HTML string into a DOM element
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = renderedHtml.trim();
    const newElement = tempDiv.firstChild;
    //console.log(`[FS Sidebar] New element created with ID: ${newElement.id}`);

    // --- Token Calculation Logic ---
    // Get the token count of the element being replaced, but ONLY if it was actually loaded.
    const oldTokens = (existingElement && existingElement.getAttribute('data-is-loaded') === 'true')
                      ? (parseInt(existingElement.querySelector('.fs-token-count').textContent, 10) || 0)
                      : 0;
    
    // Get the token count of the new element, but ONLY if it's loaded.
    const newTokens = is_loaded ? (payload.tokens || 0) : 0;

    // Calculate the net change and update the total.
    const tokenChange = newTokens - oldTokens;
    instanceState.totalFilesystemTokens += tokenChange;

    if (existingElement) { // If replacing an existing element
        existingElement.replaceWith(newElement);
    } else { // If inserting a new element

        // If no existing element, append it in sorted order based on path
        let inserted = false;
        const children = container.children;
        for (let i = 0; i < children.length; i++) {
            const child = children[i];
            const childPath = child.querySelector('.fs-path').textContent; // Assuming path is visible
            if (path < childPath) { // Simple alphabetical sort by path
                container.insertBefore(newElement, child);
                inserted = true;
                break;
            }
        }
        if (!inserted) {
            container.appendChild(newElement); // If no smaller path found, append to the end
        }
    }
    
    // Always update the map with the latest FsLogEntry ID for this path
    instanceState.sidebarPathToIdMap[path] = newFsLogEntryId;
    
    // After any add/update, refresh the total token count display
    updateTotalTokensDisplay(instancePk);
    
    sortAndRenderFilesystemItems(instancePk); // Re-apply sort after any item update/insertion
};



function resetFilesystemState(instancePk) {
    const instanceState = getInstanceFilesystemState(instancePk);
    const container = document.getElementById(`sidebar-filesystem-list-${instancePk}`);
    instanceState.totalFilesystemTokens = 0;
    instanceState.sidebarPathToIdMap = {};
    if (container) {
        container.innerHTML = '';
    }
    updateTotalTokensDisplay(instancePk);
};


function getInstanceFilesystemState(instancePk) {
    if (!instanceFilesystemStates[instancePk]) {
        instanceFilesystemStates[instancePk] = {
            totalFilesystemTokens: 0,
            sidebarPathToIdMap: {},
            currentSortColumn: 'path', // Default sort column
            currentSortDirection: 'asc', // Default sort direction ('asc' or 'desc')
            // Add any other instance-specific state variables here
        };
    }
    return instanceFilesystemStates[instancePk];
}



// New function to initialize the entire UI structure for the filesystem sidebar
function initializeFilesystemSidebarUI(instancePk) {
    //console.log(`initializeFilesystemSidebarUI: Executing for instance ${instancePk}.`);
    const container = document.getElementById(`sidebar-tab-filesystem_${instancePk}`);
    if (!container) {
        console.error(`initializeFilesystemSidebarUI: Filesystem sidebar container for instance ${instancePk} not found.`);
        return;
    }
    // Render the main container template
    container.innerHTML = sidebarFilesystemContainerTemplate({ instancePk: instancePk });
    // Attach event listeners to the newly created elements
    initializeSidebarFilesystemListeners(instancePk);
}


/**
 * Updates the display of total tokens for a given instance.
 * @param {number} instancePk
 */
function updateTotalTokensDisplay(instancePk) {
    const instanceState = getInstanceFilesystemState(instancePk);
    const tokenDisplay = document.getElementById(`total-fs-tokens_${instancePk}`);
    if (tokenDisplay) {
        tokenDisplay.textContent = instanceState.totalFilesystemTokens;
    }
}

/**
 * Handles clicks on sortable header items in the filesystem sidebar.
 * @param {string} column The column to sort by ('path', 'size', 'actions').
 * @param {number} instancePk The primary key of the agent instance.
 */
function handleFilesystemSort(column, instancePk) {
    const instanceState = getInstanceFilesystemState(instancePk);
    let newDirection = 'asc';

    if (instanceState.currentSortColumn === column) {
        // If clicking the same column, toggle direction
        newDirection = instanceState.currentSortDirection === 'asc' ? 'desc' : 'asc';
    }

    instanceState.currentSortColumn = column;
    instanceState.currentSortDirection = newDirection;

    // Update sort icons visually
    const headerItems = document.querySelectorAll(`#sidebar-fs-list-header_${instancePk} .sort-header-item`);
    headerItems.forEach(item => {
        const icon = item.querySelector('i');
        if (icon) {
            icon.className = 'fa fa-sort'; // Reset all to default sort icon
        }
        if (item.dataset.sortColumn === column) {
            if (icon) {
                icon.className = `fa fa-sort-${newDirection}`; // Set active column's icon
            }
        }
    });

    sortAndRenderFilesystemItems(instancePk);
};

/**
 * Sorts the filesystem items for a given instance and re-renders the list.
 * @param {number} instancePk The primary key of the agent instance.
 */
function sortAndRenderFilesystemItems(instancePk) {
    const instanceState = getInstanceFilesystemState(instancePk);
    const container = document.getElementById(`sidebar-filesystem-list-${instancePk}`);
    if (!container) return;

    const items = Array.from(container.children); // Get all current DOM elements

    // Convert to a sortable array, extracting relevant data
    const sortableItems = items.map(element => {
        return {
            element: element,
            path: element.querySelector('.fs-path').textContent,
            tokens: parseInt(element.querySelector('.fs-token-count').textContent) || 0,
            is_dir: element.querySelector('.fa-folder-o') !== null,
            // Add other data if needed for sorting (e.g., is_pinned, timestamps)
        };
    });

    sortableItems.sort((a, b) => {
        let comparison = 0;
        if (instanceState.currentSortColumn === 'path') {
            // Directories first, then alphabetical by path
            if (a.is_dir && !b.is_dir) comparison = -1;
            else if (!a.is_dir && b.is_dir) comparison = 1;
            else comparison = a.path.localeCompare(b.path);
        } else if (instanceState.currentSortColumn === 'size') {
            // Sort by tokens
            comparison = a.tokens - b.tokens;
        } else if (instanceState.currentSortColumn === 'actions') {
            // Example: sort by pinned status (pinned first)
            const aPinned = a.element.querySelector('.fs-pin-btn.pinned') !== null;
            const bPinned = b.element.querySelector('.fs-pin-btn.pinned') !== null;
            if (aPinned && !bPinned) comparison = -1;
            else if (!aPinned && bPinned) comparison = 1;
            else comparison = a.path.localeCompare(b.path); // Fallback to path
        }
        
        return instanceState.currentSortDirection === 'asc' ? comparison : -comparison;
    });

    // Clear and re-append sorted elements
    container.innerHTML = '';
    sortableItems.forEach(item => container.appendChild(item.element));
}


function saveSidebarFsPermission(instancePk, key, value) {
    if (!instancePk) {
        addToConsoleArea("Cannot save FS permission: instancePk is not set.", 'warning', null, 'global');
        return;
    }
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'update_instance_data',
            payload: {
                instance_pk: instancePk,
                data: {
                    [key]: value
                }
            }
        }));
        addToConsoleArea(`Client: Updated filesystem permission '${key}' for instance ${instancePk}.`, 'info');
    } else {
        addToConsoleArea("Failed to save permission: WebSocket not connected.", 'error');
    }
}

function initializeSidebarFilesystemListeners(instancePk) {
    const sidebarTabContent = document.getElementById(`sidebar-tab-filesystem_${instancePk}`);
    if (!sidebarTabContent) {
        console.error(`Sidebar filesystem tab content for instance ${instancePk} not found.`);
        return;
    }
    const loadBtn = sidebarTabContent.querySelector(`#sidebar-fs-load-btn_${instancePk}`);
    const pathInput = sidebarTabContent.querySelector(`#sidebar-fs-path-input_${instancePk}`);

    if (loadBtn && pathInput) {
        loadBtn.addEventListener('click', () => {
            if (websocket && websocket.readyState === WebSocket.OPEN) {
                const paths = pathInput.value.trim().split('\n').filter(p => p.trim() !== '');
                if (paths.length === 0) return;

                const toolCalls = paths.map(path => {
                    let recursive = false;
                    if (path.endsWith("/*")) {
                        recursive = true;
                        path = path.slice(0, -1);
                    }
                    return {
                        function_name: "fs_load",
                        arguments: { path, recursive }
                    };
                });

                websocket.send(JSON.stringify({
                    type: 'direct_tool_call',
                    payload: { 
                        tool_calls: toolCalls,
                        instance_pk: instancePk
                    }
                }));
                pathInput.value = '';
                addToConsoleArea(`Client: Requesting to load paths for instance ${instancePk}.`, 'info');
            } else {
                addToConsoleArea("Cannot load paths. WebSocket is not connected.", 'error');
            }
        });
    }

    const fsContainer = sidebarTabContent.querySelector(`#sidebar-filesystem-list-${instancePk}`);
    if (fsContainer) {
        fsContainer.addEventListener('click', (event) => {
            const target = event.target;
            if (!target) return;
            
            if (!websocket || websocket.readyState !== WebSocket.OPEN) {
                addToConsoleArea("Action failed. WebSocket is not connected.", 'error');
                return;
            }

            if (target.classList.contains('fs-unload-btn')) {
                const path = target.getAttribute('data-path');
                if (!path) return;
                const fsItem = target.closest('.sidebar-fs-item');
                const pinButton = fsItem ? fsItem.querySelector('.fs-pin-btn') : null;
                const isPinned = pinButton ? pinButton.classList.contains('pinned') : false;
                const toolCallArgs = { path: path };
                if (isPinned) {
                    toolCallArgs.force = true;
                }
                websocket.send(JSON.stringify({
                    type: 'direct_tool_call',
                    payload: {
                        tool_calls: [{ function_name: 'fs_unload', arguments: toolCallArgs }],
                        instance_pk: instancePk
                    }
                }));
                addToConsoleArea(`Client: Requesting to unload file: ${path} for instance ${instancePk}.`, 'info');
            }

            if (target.classList.contains('fs-load-btn')) {
                const path = target.getAttribute('data-path');
                if (!path) return;
                websocket.send(JSON.stringify({
                    type: 'direct_tool_call',
                    payload: {
                        tool_calls: [{ function_name: 'fs_load', arguments: { path: path } }],
                        instance_pk: instancePk
                    }
                }));
                addToConsoleArea(`Client: Requesting to load file: ${path} for instance ${instancePk}.`, 'info');
            }

            if (target.classList.contains('fs-pin-btn')) {
                const path = target.getAttribute('data-path');
                const objectType = target.getAttribute('data-type');
                if (!path || !objectType) return;
                target.classList.toggle("pinned");
                websocket.send(JSON.stringify({
                    type: 'toggle_fs_pin',
                    payload: {
                        path: path,
                        object_type: objectType,
                        instance_pk: instancePk
                    }
                }));
                addToConsoleArea(`Client: Toggling pin for ${objectType}: ${path} for instance ${instancePk}.`, 'info');
            }

            if (target.classList.contains('fs-toggle-load-mode-btn')) {
                const path = target.getAttribute('data-path');
                const currentLoadMode = target.getAttribute('data-load-mode');
                if (!path || !currentLoadMode) return;
                toggleSidebarFilesystemLoadMode(path, instancePk, currentLoadMode);
            }
        });
    }
}

/**
 * Toggles the load mode (summary/full) for a file in the sidebar and reloads it.
 * @param {string} path The file path to load.
 * @param {number} instancePk The instance PK for scoping.
 * @param {string} currentLoadMode The current load mode ('full' or 'summary').
 */
function toggleSidebarFilesystemLoadMode(path, instancePk, currentLoadMode) {
    if (!instancePk) {
        addToConsoleArea("Cannot toggle load mode: No agent instance selected.", 'warning');
        return;
    }

    const newLoadMode = (currentLoadMode === 'summary') ? 'full' : 'summary';

    if (websocket && websocket.readyState === WebSocket.OPEN) {
        addToConsoleArea(`Client: Requesting to load file: ${path} in ${newLoadMode} mode.`, 'info');
        websocket.send(JSON.stringify({
            type: 'direct_tool_call',
            payload: {
                tool_calls: [{ function_name: 'fs_load', arguments: { path: path, mode: newLoadMode } }],
                instance_pk: instancePk
            }
        }));
    } else {
        addToConsoleArea("Cannot toggle load mode: WebSocket not connected.", 'error');
    }
}
