// This file manages the rendering and interactions for the Tool Registry tab.

window.toolDefinitionCache = window.toolDefinitionCache || {};
let currentSortColumn = 'display_name';
let currentSortDirection = 'asc';

function initializeToolTemplates() {
    Handlebars.registerPartial('TabToolsToolDefinitionItemTemplate', getTemplate('TabToolsToolDefinitionItemTemplate'));
    Handlebars.registerPartial('AddToolDefinitionFormTemplate', getTemplate('TabToolsAddToolDefinitionFormTemplate'));
}

function renderToolDefinitionList(toolDefinitions) {
    if (!Handlebars.partials['TabToolsToolDefinitionItemTemplate']) initializeToolTemplates(); // Use the item template here
    const toolRegistryListBody = document.getElementById('tool-registry-list-body');
    if (!toolRegistryListBody) return;

    toolDefinitionCache = {};
    toolDefinitions.forEach(tool => { toolDefinitionCache[tool.id] = tool; });

    const sortedTools = Object.values(toolDefinitionCache).sort((a, b) => {
        const valA = (a[currentSortColumn] || '').toString().toLowerCase();
        const valB = (b[currentSortColumn] || '').toString().toLowerCase();
        if (valA < valB) return currentSortDirection === 'asc' ? -1 : 1;
        if (valA > valB) return currentSortDirection === 'asc' ? 1 : -1;
        return 0;
    });

    toolRegistryListBody.innerHTML = ''; // Clear existing content

    sortedTools.forEach(tool => {
        // Render each tool using the item template and append to the tbody
        toolRegistryListBody.insertAdjacentHTML('beforeend', Handlebars.partials.TabToolsToolDefinitionItemTemplate(tool));
    });
    
    updateSortIndicators();
}

function handleToolDefinitionUpdate(toolDefinition) {
    toolDefinitionCache[toolDefinition.id] = toolDefinition;
    renderToolDefinitionList(Object.values(toolDefinitionCache));
}

function handleToolDefinitionDelete(toolDefinitionId) {
    delete toolDefinitionCache[toolDefinitionId];
    renderToolDefinitionList(Object.values(toolDefinitionCache));
}

function renderSystemAssignment(toolDefinitionId) {
    const tool = toolDefinitionCache[toolDefinitionId];
    const container = document.querySelector(`.assigned-systems-container[data-tool-id="${toolDefinitionId}"]`);
    if (!tool || !container) return;

    container.innerHTML = '';
    const assignedSystemIds = new Set(tool.available_on_systems);
    assignedSystemIds.forEach(systemId => {
        const system = window.systemCache[systemId];
        if (system) {
            const tag = document.createElement('span');
            tag.className = 'assigned-system-tag';
            tag.innerHTML = `${system.name} <i class="fa fa-times remove-system-btn" onclick="toolSystemUnassign(event, '${toolDefinitionId}', '${system.id}')"></i>`;
            container.appendChild(tag);
        }
    });
}

function updateSortIndicators() {
    const table = document.getElementById('tool-registry-table');
    if (!table) return;
    table.querySelectorAll('th[data-sort] i').forEach(icon => icon.className = 'fa fa-sort');
    const header = table.querySelector(`th[data-sort="${currentSortColumn}"] i`);
    if (header) header.className = `fa fa-sort-${currentSortDirection === 'asc' ? 'up' : 'down'}`;
}

function toggleDetails(button, detailsId) {
    const detailsDiv = document.getElementById(detailsId);
    if (!detailsDiv) return;
    const icon = button.querySelector('i');
    const isHidden = detailsDiv.style.display === 'none';
    detailsDiv.style.display = isHidden ? 'block' : 'none';
    icon.className = `fa fa-chevron-${isHidden ? 'up' : 'down'}`;
}

function populateInlineEditForm(toolId) {
    const tool = toolDefinitionCache[toolId];
    const form = document.getElementById(`inline-edit-tool-definition-form-${toolId}`);
    if (!tool || !form) return;
    const serverConfig = tool.manifest?.server || {};
    form.querySelector(`#editToolDefinitionRepoUrl-${toolId}`).value = tool.repository_url || '';
    form.querySelector(`#editToolDefinitionDisplayName-${toolId}`).value = tool.display_name || '';
    form.querySelector(`#editToolDefinitionName-${toolId}`).value = tool.name || '';
    form.querySelector(`#editToolDefinitionDescription-${toolId}`).value = tool.description || '';
    form.querySelector(`#editToolDefinitionTransportType-${toolId}`).value = tool.transport_type || 'stdin_stdout';
    form.querySelector(`#editToolDefinitionExecutionMode-${toolId}`).value = tool.execution_mode || 'shared';
    form.querySelector(`#editToolDefinitionCommand-${toolId}`).value = serverConfig.command || '';
    form.querySelector(`#editToolDefinitionArgs-${toolId}`).value = JSON.stringify(serverConfig.args || []);
    form.querySelector(`#editToolDefinitionPlatforms-${toolId}`).value = (serverConfig.platforms || []).join(',');
    form.querySelector(`#edit-tool-definition-manual-details-${toolId}`).style.display = 'none';
    form.querySelector(`.toggle-details-btn i`).className = 'fa fa-chevron-down';
}

function openToolRegistryTab(targetPanelId = 'mainTabPanel') {
    const tabContentId = 'tabContent_tool_registry';
    const tabName = 'Tool Registry';
    if (!Handlebars.partials['ToolDefinitionTemplate']) initializeToolTemplates();
    const tabToolsTemplate = getTemplate('TabToolsTemplate');
    const tabContentHtml = tabToolsTemplate({});
    openMainTab(null, tabContentId, targetPanelId, tabName, tabContentHtml);
    toolDefinitionApi.list();
}

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
    container.innerHTML = getTemplate('TabToolsAddToolDefinitionFormTemplate')({});
    container.style.display = 'flex';
    setTimeout(() => container.classList.add('add-form-visible'), 10);
}

function toolDefinitionAdd(event) {
    event.preventDefault();
    event.stopPropagation();
    const form = event.target;
    toolDefinitionApi.create({
        display_name: form.querySelector('#addToolDefinitionDisplayName').value,
        name: form.querySelector('#addToolDefinitionName').value,
        description: form.querySelector('#addToolDefinitionDescription').value,
        transport_type: form.querySelector('#addToolDefinitionTransportType').value,
        execution_mode: form.querySelector('#addToolDefinitionExecutionMode').value,
        repository_url: form.querySelector('#addToolDefinitionRepoUrl').value,
        manifest: { server: {
            command: form.querySelector('#addToolDefinitionCommand').value,
            args: JSON.parse(form.querySelector('#addToolDefinitionArgs').value || '[]'),
            platforms: form.querySelector('#addToolDefinitionPlatforms').value.split(',').map(p => p.trim()).filter(Boolean)
        }}
    });
    toolDefinitionCancelAdd(event);
}

function toolDefinitionCancelAdd(event) {
    event.stopPropagation();
    const container = document.getElementById('add-tool-definition-inline-form-container');
    container.classList.remove('add-form-visible');
    setTimeout(() => { container.style.display = 'none'; container.innerHTML = ''; }, 300);
}

function toolDefinitionRefresh(event, toolId) {
    event.stopPropagation();
    event.currentTarget.querySelector('i').classList.add('fa-spin');
    toolDefinitionApi.refreshManifest(toolId);
}

function toolDefinitionDeleteDialog(event, toolId) {
    event.stopPropagation();
    if (confirm('Are you sure you want to delete this tool definition?')) {
        toolDefinitionApi.delete(toolId);
    }
}

function toolDefinitionToggleDetails(event, toolId) {
    event.stopPropagation();
    const detailsRow = document.querySelector(`tr.tool-details-row[data-id="${toolId}"]`);
    const icon = event.currentTarget.querySelector('i');
    if (!detailsRow || !icon) return;
    const isHidden = detailsRow.style.display === 'none';
    detailsRow.style.display = isHidden ? 'table-row' : 'none';
    icon.className = `fa fa-chevron-${isHidden ? 'up' : 'down'}`;
    if (isHidden) {
        renderSystemAssignment(toolId);
        populateInlineEditForm(toolId);
    }
}

function toolDefinitionToggleAllSystems(event, toolId) {
    event.stopPropagation();
    toolDefinitionApi.update(toolId, { available_on_all_systems: event.target.checked });
}

function toolSystemSearch(event, toolId) {
    event.stopPropagation();
    const searchInput = event.target;
    const resultsContainer = document.querySelector(`.system-search-results[data-tool-id="${toolId}"]`);
    const searchTerm = searchInput.value.toLowerCase();
    resultsContainer.innerHTML = '';

    if (!searchTerm) { resultsContainer.classList.remove('visible'); return; }

    const tool = toolDefinitionCache[toolId];
    if (!tool) return;
    const assignedSystemIds = new Set(tool.available_on_systems);
    const filteredSystems = Object.values(window.systemCache || {}).filter(system =>
        !assignedSystemIds.has(system.id) && system.name.toLowerCase().includes(searchTerm)
    );

    if (filteredSystems.length > 0) {
        filteredSystems.forEach(system => {
            const item = document.createElement('div');
            item.className = 'search-result-item';
            item.textContent = system.name;
            item.onclick = () => toolSystemAssign(event, toolId, system.id);
            resultsContainer.appendChild(item);
        });
        resultsContainer.classList.add('visible');
    } else {
        resultsContainer.classList.remove('visible');
    }
}

function toolSystemAssign(event, toolId, systemId) {
    event.stopPropagation();
    toolDefinitionApi.assignSystem(toolId, systemId);
    const searchInput = document.querySelector(`.system-search-input[data-tool-id="${toolId}"]`);
    const resultsContainer = document.querySelector(`.system-search-results[data-tool-id="${toolId}"]`);
    searchInput.value = '';
    resultsContainer.classList.remove('visible');
}

function toolSystemUnassign(event, toolId, systemId) {
    event.stopPropagation();
    toolDefinitionApi.unassignSystem(toolId, systemId);
}

function toolDefinitionSaveChanges(event, toolId) {
    event.preventDefault();
    event.stopPropagation();
    const form = document.getElementById(`inline-edit-tool-definition-form-${toolId}`);
    const updates = {
        display_name: form.querySelector(`#editToolDefinitionDisplayName-${toolId}`).value,
        name: form.querySelector(`#editToolDefinitionName-${toolId}`).value,
        description: form.querySelector(`#editToolDefinitionDescription-${toolId}`).value,
        transport_type: form.querySelector(`#editToolDefinitionTransportType-${toolId}`).value,
        execution_mode: form.querySelector(`#editToolDefinitionExecutionMode-${toolId}`).value,
        repository_url: form.querySelector(`#editToolDefinitionRepoUrl-${toolId}`).value,
        manifest: { server: {
            command: form.querySelector(`#editToolDefinitionCommand-${toolId}`).value,
            args: JSON.parse(form.querySelector(`#editToolDefinitionArgs-${toolId}`).value || '[]'),
            platforms: form.querySelector(`#editToolDefinitionPlatforms-${toolId}`).value.split(',').map(p => p.trim()).filter(Boolean)
        }}
    };
    toolDefinitionApi.update(toolId, updates);
    toolDefinitionToggleDetails(event, toolId); // To close the form
}

function toolDefinitionCancelEdit(event, toolId) {
    event.stopPropagation();
    toolDefinitionToggleDetails(event, toolId);
}
