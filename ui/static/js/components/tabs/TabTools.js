// This file manages the rendering and interactions for the Tool Registry tab.

window.toolDefinitionCache = window.toolDefinitionCache || {};
let currentSortColumn = 'display_name'; // Default sort column
let currentSortDirection = 'asc'; // Default sort direction

// --- TEMPLATE & CACHE INITIALIZATION ---

function initializeToolTemplates() {
    Handlebars.registerPartial('ToolDefinitionTemplate', getTemplate('TabToolsToolDefinitionTemplate'));
    Handlebars.registerPartial('AddToolDefinitionFormTemplate', getTemplate('TabToolsAddToolDefinitionFormTemplate'));
}

// --- RENDER FUNCTIONS ---

function renderToolDefinitionList(toolDefinitions) {
    if (!Handlebars.partials['ToolDefinitionTemplate']) {
        initializeToolTemplates();
    }
    const toolRegistryListBody = document.getElementById('tool-registry-list-body');
    if (!toolRegistryListBody) return;

    toolDefinitionCache = {};
    toolDefinitions.forEach(tool => {
        toolDefinitionCache[tool.id] = tool;
    });

    const sortedTools = Object.values(toolDefinitionCache).sort((a, b) => {
        const valA = (a[currentSortColumn] || '').toString().toLowerCase();
        const valB = (b[currentSortColumn] || '').toString().toLowerCase();
        if (valA < valB) return currentSortDirection === 'asc' ? -1 : 1;
        if (valA > valB) return currentSortDirection === 'asc' ? 1 : -1;
        return 0;
    });

    toolRegistryListBody.innerHTML = Handlebars.partials.ToolDefinitionTemplate(sortedTools);
    updateSortIndicators();
}

function handleToolDefinitionUpdate(toolDefinition) {
    toolDefinitionCache[toolDefinition.id] = toolDefinition;
    renderToolDefinitionList(Object.values(toolDefinitionCache));
}

function handleToolDefinitionDelete(toolDefinitionId) {
    delete toolDefinitionCache[toolDefinitionId];
    renderToolDefinitionList(Object.values(toolDefinitionCache));
    addToClientLog(`Client: Tool definition ${toolDefinitionId} removed from UI.`, 'info');
}

function renderSystemAssignment(toolDefinitionId) {
    const tool = toolDefinitionCache[toolDefinitionId];
    if (!tool) return;

    const assignedSystemsContainer = document.querySelector(`.assigned-systems-container[data-tool-id="${toolDefinitionId}"]`);
    if (!assignedSystemsContainer) return;

    assignedSystemsContainer.innerHTML = '';
    const assignedSystemIds = new Set(tool.available_on_systems);
    assignedSystemIds.forEach(systemId => {
        const system = window.systemCache[systemId];
        if (system) {
            const tag = document.createElement('span');
            tag.className = 'assigned-system-tag';
            tag.innerHTML = `${system.name} <i class="fa fa-times remove-system-btn" onclick="toolSystemUnassign(event, '${toolDefinitionId}', '${system.id}')"></i>`;
            assignedSystemsContainer.appendChild(tag);
        }
    });
}

// --- UI HELPER FUNCTIONS ---

function updateSortIndicators() {
    const toolRegistryTable = document.getElementById('tool-registry-table');
    if (!toolRegistryTable) return;
    toolRegistryTable.querySelectorAll('th[data-sort] i').forEach(icon => {
        icon.className = 'fa fa-sort';
    });
    const currentHeader = toolRegistryTable.querySelector(`th[data-sort="${currentSortColumn}"] i`);
    if (currentHeader) {
        currentHeader.className = `fa fa-sort-${currentSortDirection === 'asc' ? 'up' : 'down'}`;
    }
}

function toggleDetails(button, detailsId) {
    const detailsDiv = document.getElementById(detailsId);
    if (!detailsDiv) return;
    const icon = button.querySelector('i');
    const isHidden = detailsDiv.style.display === 'none';
    detailsDiv.style.display = isHidden ? 'block' : 'none';
    icon.className = `fa ${isHidden ? 'fa-chevron-up' : 'fa-chevron-down'}`;
}

function populateInlineEditForm(toolId) {
    const tool = toolDefinitionCache[toolId];
    if (!tool) return;
    const form = document.getElementById(`inline-edit-tool-definition-form-${toolId}`);
    if (!form) return;

    form.querySelector(`#editToolDefinitionRepoUrl-${toolId}`).value = tool.repository_url || '';
    form.querySelector(`#editToolDefinitionDisplayName-${toolId}`).value = tool.display_name || '';
    form.querySelector(`#editToolDefinitionName-${toolId}`).value = tool.name || '';
    form.querySelector(`#editToolDefinitionDescription-${toolId}`).value = tool.description || '';
    form.querySelector(`#editToolDefinitionTransportType-${toolId}`).value = tool.transport_type || 'tcp';
    form.querySelector(`#editToolDefinitionExecutionMode-${toolId}`).value = tool.execution_mode || 'shared';

    const serverConfig = tool.manifest?.server || {};
    form.querySelector(`#editToolDefinitionCommand-${toolId}`).value = serverConfig.command || '';
    form.querySelector(`#editToolDefinitionArgs-${toolId}`).value = JSON.stringify(serverConfig.args || []);
    form.querySelector(`#editToolDefinitionPlatforms-${toolId}`).value = (serverConfig.platforms || []).join(',');

    const manualDetailsDiv = form.querySelector(`#edit-tool-definition-manual-details-${toolId}`);
    manualDetailsDiv.style.display = 'none';
    form.querySelector(`.toggle-details-btn i`).className = 'fa fa-chevron-down';
}

// --- TAB MANAGEMENT ---

function openToolRegistryTab(targetPanelId = 'mainTabPanel') {
    const tabContentId = 'tabContent_tool_registry';
    const tabName = 'Tool Registry';

    // Ensure templates are ready
    if (!Handlebars.partials['ToolDefinitionTemplate']) {
        initializeToolTemplates();
    }
    
    const tabToolsTemplate = getTemplate('TabToolsTemplate');
    const tabContentHtml = tabToolsTemplate({});

    // The openMainTab function handles both creating and showing the tab.
        openMainTab(null, tabContentId, targetPanelId, tabName, tabContentHtml);
    requestToolDefinitionList();
    addToClientLog(`Client: Opened Tool Registry tab.`, 'info');}

function requestToolDefinitionList() {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: 'request_tool_definition_list' }));
    }
}

// --- INLINE EVENT HANDLERS ---

function toolDefinitionSort(event, newSortColumn) {
    event.stopPropagation();
    if (newSortColumn === currentSortColumn) {
        currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        currentSortColumn = newSortColumn;
        currentSortDirection = 'asc';
    }
    renderToolDefinitionList(Object.values(toolDefinitionCache));
}

function toolDefinitionShowAddForm(event) {
    event.stopPropagation();
    const container = document.getElementById('add-tool-definition-inline-form-container');
    const isVisible = container.classList.contains('add-form-visible');
    if (isVisible) {
        container.classList.remove('add-form-visible');
        setTimeout(() => { container.style.display = 'none'; }, 300);
        return;
    }

    const addFormTemplate = getTemplate('TabToolsAddToolDefinitionFormTemplate');
    container.innerHTML = addFormTemplate({});
    container.style.display = 'flex';
    setTimeout(() => container.classList.add('add-form-visible'), 10);
}

function toolDefinitionAdd(event) {
    event.preventDefault();
    event.stopPropagation();
    const form = event.target;
    const payload = {
        display_name: form.querySelector('#addToolDefinitionDisplayName').value,
        name: form.querySelector('#addToolDefinitionName').value,
        description: form.querySelector('#addToolDefinitionDescription').value,
        transport_type: form.querySelector('#addToolDefinitionTransportType').value,
        execution_mode: form.querySelector('#addToolDefinitionExecutionMode').value,
        repository_url: form.querySelector('#addToolDefinitionRepoUrl').value,
        manifest: {
            server: {
                command: form.querySelector('#addToolDefinitionCommand').value,
                args: JSON.parse(form.querySelector('#addToolDefinitionArgs').value || '[]'),
                platforms: form.querySelector('#addToolDefinitionPlatforms').value.split(',').map(p => p.trim()).filter(p => p !== '')
            }
        }
    };
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: 'create_tool_definition', payload: payload }));
    } else {
        addToClientLog("WebSocket not connected. Cannot create tool definition.", 'error');
    }
    toolDefinitionCancelAdd(event);
}

function toolDefinitionCancelAdd(event) {
    event.stopPropagation();
    const container = document.getElementById('add-tool-definition-inline-form-container');
    container.classList.remove('add-form-visible');
    setTimeout(() => { container.style.display = 'none'; container.innerHTML = ''; }, 300);
}

function toolDefinitionToggleActive(event, toolId) {
    event.stopPropagation();
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: 'toggle_tool_definition_active', payload: { tool_definition_id: toolId } }));
    } else {
        addToClientLog("WebSocket not connected. Cannot toggle tool active status.", 'error');
        event.target.checked = !event.target.checked;
    }
}

function toolDefinitionRefresh(event, toolId) {
    event.stopPropagation();
    const icon = event.currentTarget.querySelector('i');
    icon.classList.add('fa-spin');
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: 'request_refresh_tool_definition_manifest', payload: { tool_definition_id: toolId } }));
    } else {
        addToClientLog("WebSocket not connected. Cannot refresh tool definition.", 'error');
        icon.classList.remove('fa-spin');
    }
}

function toolDefinitionDeleteDialog(event, toolId) {
    event.stopPropagation();
    if (confirm('Are you sure you want to delete this tool definition?')) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({ type: 'delete_tool_definition', payload: { tool_definition_id: toolId } }));
        } else {
            addToClientLog("WebSocket not connected. Cannot delete tool definition.", 'error');
        }
    }
}

function toolDefinitionToggleDetails(event, toolId) {
    event.stopPropagation();
    const detailsRow = document.querySelector(`tr.tool-details-row[data-id="${toolId}"]`);
    const icon = event.currentTarget.querySelector('i');
    if (!detailsRow || !icon) return;

    const isHidden = detailsRow.style.display === 'none';
    detailsRow.style.display = isHidden ? 'table-row' : 'none';
    icon.className = `fa ${isHidden ? 'fa-chevron-up' : 'fa-chevron-down'}`;

    if (isHidden) {
        renderSystemAssignment(toolId);
        populateInlineEditForm(toolId);
    }
}

function toolDefinitionToggleAllSystems(event, toolId) {
    event.stopPropagation();
    const isChecked = event.target.checked;
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'update_tool_definition',
            payload: { tool_definition_id: toolId, updates: { available_on_all_systems: isChecked } }
        }));
    } else {
        addToClientLog("WebSocket not connected. Cannot update system availability.", 'error');
        event.target.checked = !isChecked;
    }
}

function toolSystemSearch(event, toolId) {
    event.stopPropagation();
    const searchInput = event.target;
    const searchResultsContainer = document.querySelector(`.system-search-results[data-tool-id="${toolId}"]`);
    const searchTerm = searchInput.value.toLowerCase();
    searchResultsContainer.innerHTML = '';

    if (searchTerm.length === 0) {
        searchResultsContainer.classList.remove('visible');
        return;
    }

    const tool = toolDefinitionCache[toolId];
    if (!tool) return;
    const assignedSystemIds = new Set(tool.available_on_systems);
    const allSystems = Object.values(window.systemCache || {});
    const filteredSystems = allSystems.filter(system =>
        !assignedSystemIds.has(system.id) && system.name.toLowerCase().includes(searchTerm)
    );

    if (filteredSystems.length > 0) {
        filteredSystems.forEach(system => {
            const resultItem = document.createElement('div');
            resultItem.className = 'search-result-item';
            resultItem.textContent = system.name;
            resultItem.setAttribute('onclick', `toolSystemAssign(event, '${toolId}', '${system.id}')`);
            searchResultsContainer.appendChild(resultItem);
        });
        searchResultsContainer.classList.add('visible');
    } else {
        searchResultsContainer.classList.remove('visible');
    }
}

function toolSystemAssign(event, toolId, systemId) {
    event.stopPropagation();
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'assign_system_to_tool',
            payload: { tool_definition_id: toolId, system_id: systemId }
        }));
    } else {
        addToClientLog("WebSocket not connected. Cannot assign system to tool.", 'error');
    }
    const searchInput = document.querySelector(`.system-search-input[data-tool-id="${toolId}"]`);
    const searchResultsContainer = document.querySelector(`.system-search-results[data-tool-id="${toolId}"]`);
    searchInput.value = '';
    searchResultsContainer.classList.remove('visible');
}

function toolSystemUnassign(event, toolId, systemId) {
    event.stopPropagation();
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'unassign_system_from_tool',
            payload: { tool_definition_id: toolId, system_id: systemId }
        }));
    } else {
        addToClientLog("WebSocket not connected. Cannot unassign system to tool.", 'error');
    }
}

function toolDefinitionSaveChanges(event, toolId) {
    event.preventDefault();
    event.stopPropagation();
    const form = document.getElementById(`inline-edit-tool-definition-form-${toolId}`);
    const payload = {
        tool_definition_id: toolId,
        updates: {
            display_name: form.querySelector(`#editToolDefinitionDisplayName-${toolId}`).value,
            name: form.querySelector(`#editToolDefinitionName-${toolId}`).value,
            description: form.querySelector(`#editToolDefinitionDescription-${toolId}`).value,
            transport_type: form.querySelector(`#editToolDefinitionTransportType-${toolId}`).value,
            execution_mode: form.querySelector(`#editToolDefinitionExecutionMode-${toolId}`).value,
            repository_url: form.querySelector(`#editToolDefinitionRepoUrl-${toolId}`).value,
            manifest: {
                server: {
                    command: form.querySelector(`#editToolDefinitionCommand-${toolId}`).value,
                    args: JSON.parse(form.querySelector(`#editToolDefinitionArgs-${toolId}`).value || '[]'),
                    platforms: form.querySelector(`#editToolDefinitionPlatforms-${toolId}`).value.split(',').map(p => p.trim()).filter(p => p !== '')
                }
            }
        }
    };
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: 'update_tool_definition', payload: payload }));
    } else {
        addToClientLog("WebSocket not connected. Cannot save changes.", 'error');
    }
    const detailsButton = document.querySelector(`tr[data-id="${toolId}"] .toggle-details-btn`);
    if(detailsButton) detailsButton.click();
}

function toolDefinitionCancelEdit(event, toolId) {
    event.stopPropagation();
    const detailsButton = document.querySelector(`tr[data-id="${toolId}"] .toggle-details-btn`);
    if(detailsButton) {
        detailsButton.click();
    }
}
