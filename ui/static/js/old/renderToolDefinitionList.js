// Global variables
let toolDefinitionCache = {};
const toolRegistryListBody = document.getElementById('tool-registry-list-body');
const toolRegistryTable = document.getElementById('tool-registry-table');
let currentSortColumn = 'display_name'; // Default sort column
let currentSortDirection = 'asc'; // Default sort direction

// Helper function to update sort indicators
function updateSortIndicators() {
    if (!toolRegistryTable) return;
    toolRegistryTable.querySelectorAll('th[data-sort] i').forEach(icon => {
        icon.className = 'fa fa-sort'; // Reset all icons
    });

    const currentHeader = toolRegistryTable.querySelector(`th[data-sort="${currentSortColumn}"] i`);
    if (currentHeader) {
        currentHeader.className = `fa fa-sort-${currentSortDirection === 'asc' ? 'up' : 'down'}`;
    }
}

// Helper function to populate modal fields (used by add/edit modals)
function populateToolDefinitionModalFields(modalPrefix, tool) {
    document.getElementById(`${modalPrefix}ToolDefinitionRepoUrl`).value = tool.repository_url || '';
    document.getElementById(`${modalPrefix}ToolDefinitionDisplayName`).value = tool.display_name || '';
    document.getElementById(`${modalPrefix}ToolDefinitionName`).value = tool.name || '';
    document.getElementById(`${modalPrefix}ToolDefinitionDescription`).value = tool.description || '';
    document.getElementById(`${modalPrefix}ToolDefinitionTransportType`).value = tool.transport_type || 'tcp';
    document.getElementById(`${modalPrefix}ToolDefinitionExecutionMode`).value = tool.execution_mode || 'shared'; // Set execution mode

    const serverConfig = tool.manifest?.server || {};
    const mcpConfig = serverConfig.mcp_config || {};
    document.getElementById(`${modalPrefix}ToolDefinitionCommand`).value = mcpConfig.command || '';
    document.getElementById(`${modalPrefix}ToolDefinitionArgs`).value = JSON.stringify(mcpConfig.args || []);
    document.getElementById(`${modalPrefix}ToolDefinitionPlatforms`).value = (serverConfig.platforms || []).join(',');

    const detailsButton = document.querySelector(`#${modalPrefix}ToolDefinitionModal .toggle-details-btn`);
    const detailsDiv = document.getElementById(`${modalPrefix}-tool-definition-details`);
    if (detailsDiv && detailsDiv.style.display === 'none') {
        toggleDetails(detailsButton, `${modalPrefix}-tool-definition-details`);
    }
}

// Helper function to toggle details section in modals
function toggleDetails(button, detailsId) {
    const detailsDiv = document.getElementById(detailsId);
    detailsDiv.style.display = detailsDiv.style.display === 'none' ? 'block' : 'none';
}

// Functions to manage the Add/Edit modals
function closeToolDefinitionModal() {
    document.getElementById('addToolDefinitionModal').style.display = 'none';
    document.getElementById('editToolDefinitionModal').style.display = 'none';
}

function openAddToolDefinitionModal() {
    const container = document.getElementById('add-tool-definition-inline-form-container');
    if (!container) return;

    if (container.classList.contains('add-form-visible')) {
        container.classList.remove('add-form-visible');
        setTimeout(() => { container.style.display = 'none'; }, 300); // Wait for transition
        return;
    }

    const inlineAddFormTemplate = Handlebars.compile(`
        <form id="inline-add-tool-definition-form" class="tool-definition-inline-form">
            <div class="form-group full-width">
                <label for="addToolDefinitionRepoUrl">Repository URL (Optional)</label>
                <input type="url" class="form-control" id="addToolDefinitionRepoUrl" placeholder="e.g., https://github.com/my-org/my-tool.git">
                <small class="form-text text-muted">Leave empty for manual definition.</small>
            </div>
            <div class="form-group">
                <label for="addToolDefinitionDisplayName">Display Name </label>
                <input type="text" class="form-control" id="addToolDefinitionDisplayName">
            </div>
            <div class="form-group">
                <label for="addToolDefinitionName">Internal Name</label>
                <input type="text" class="form-control" id="addToolDefinitionName">
                <small class="form-text text-muted">Unique identifier (snake_case, no spaces).</small>
            </div>
            <div class="form-group full-width">
                <label for="addToolDefinitionDescription">Description</label>
                <textarea class="form-control" id="addToolDefinitionDescription" rows="2"></textarea>
            </div>
            <div class="form-group">
                <label for="addToolDefinitionTransportType">Transport Type</label>
                <select class="form-control" id="addToolDefinitionTransportType">
                    <option value="stdio">STDIO</option>
                    <option value="tcp">TCP</option>
                    </select>
            </div>
            <div class="form-group">
                <label for="addToolDefinitionExecutionMode">Execution Mode</label>
                <select class="form-control" id="addToolDefinitionExecutionMode">
                    <option value="shared">Shared (per System)</option>
                    <option value="dedicated">Dedicated (per Agent Instance)</option>
                </select>
            </div>
            <button class="btn btn-default toggle-details-btn full-width" type="button" onclick="toggleDetails(this, 'add-tool-definition-manual-details')">
                Manual Manifest Details <i class="fa fa-chevron-down"></i>
            </button>
            <div id="add-tool-definition-manual-details" class="full-width" style="display: none;">
                <div class="form-group">
                    <label for="addToolDefinitionCommand">Command</label>
                    <input type="text" class="form-control" id="addToolDefinitionCommand" placeholder="e.g., python my_tool.py">
                    <small class="form-text text-muted">Required for manual definitions.</small>
                </div>
                <div class="form-group">
                    <label for="addToolDefinitionArgs">Arguments (JSON Array)</label>
                    <input type="text" class="form-control" id="addToolDefinitionArgs" value="[]" placeholder='e.g., ["--port", "5000"]'>
                </div>
                <div class="form-group">
                    <label for="addToolDefinitionPlatforms">Platforms (Comma-separated)</label>
                    <input type="text" class="form-control" id="addToolDefinitionPlatforms" placeholder="e.g., linux,windows">
                </div>
            </div>
            <div style="margin-top: 15px;">
                <button type="submit" class="btn btn-success">Save New Tool</button>
                <button type="button" class="btn btn-default cancel-inline-add-btn">Cancel</button>
            </div>
        </form>
    `);

    container.innerHTML = inlineAddFormTemplate({});
    container.style.display = 'flex'; // Set to flex to prepare for layout, before animation
    container.classList.add('add-form-visible');

    const form = document.getElementById('inline-add-tool-definition-form');
    form.addEventListener('submit', function(event) {
        event.preventDefault();
        const payload = {
            display_name: document.getElementById('addToolDefinitionDisplayName').value,
            name: document.getElementById('addToolDefinitionName').value,
            description: document.getElementById('addToolDefinitionDescription').value,
            transport_type: document.getElementById('addToolDefinitionTransportType').value,
            execution_mode: document.getElementById('addToolDefinitionExecutionMode').value,
            repository_url: document.getElementById('addToolDefinitionRepoUrl').value,
            manifest: {
                server: {
                    command: document.getElementById('addToolDefinitionCommand').value,
                    args: JSON.parse(document.getElementById('addToolDefinitionArgs').value || '[]'),
                    platforms: document.getElementById('addToolDefinitionPlatforms').value.split(',').map(p => p.trim()).filter(p => p !== '')
                }
            }
        };
        websocket.send(JSON.stringify({ type: 'create_tool_definition', payload: payload }));
        container.classList.remove('add-form-visible');
        setTimeout(() => { container.style.display = 'none'; }, 300); // Hide form after animation
        form.reset();
    });

    container.querySelector('.cancel-inline-add-btn').addEventListener('click', function() {
        container.classList.remove('add-form-visible');
        setTimeout(() => { container.style.display = 'none'; }, 300); // Hide form after animation
        form.reset();
    });
}

// Helper to populate fields for the inline edit form
function populateInlineEditForm(tool) {
    const formId = `inline-edit-tool-definition-form-${tool.id}`;
    const form = document.getElementById(formId);
    if (!form) return;

    // Use querySelector within the form to get elements by ID
    form.querySelector(`#editToolDefinitionRepoUrl-${tool.id}`).value = tool.repository_url || '';
    form.querySelector(`#editToolDefinitionDisplayName-${tool.id}`).value = tool.display_name || '';
    form.querySelector(`#editToolDefinitionName-${tool.id}`).value = tool.name || '';
    form.querySelector(`#editToolDefinitionDescription-${tool.id}`).value = tool.description || '';
    form.querySelector(`#editToolDefinitionTransportType-${tool.id}`).value = tool.transport_type || 'tcp';
    form.querySelector(`#editToolDefinitionExecutionMode-${tool.id}`).value = tool.execution_mode || 'shared';

    const serverConfig = tool.manifest?.server || {};
    const mcpConfig = serverConfig.mcp_config || {}; // Assuming manifest is directly server config
    form.querySelector(`#editToolDefinitionCommand-${tool.id}`).value = serverConfig.command || '';
    form.querySelector(`#editToolDefinitionArgs-${tool.id}`).value = JSON.stringify(serverConfig.args || []);
    form.querySelector(`#editToolDefinitionPlatforms-${tool.id}`).value = (serverConfig.platforms || []).join(',');

    // Ensure the manual details section is hidden by default when opening the form
    const manualDetailsDiv = form.querySelector(`#edit-tool-definition-manual-details-${tool.id}`);
    if (manualDetailsDiv) {
        manualDetailsDiv.style.display = 'none';
        const toggleBtn = form.querySelector('.toggle-details-btn');
        if (toggleBtn) {
            toggleBtn.querySelector('i').className = 'fa fa-chevron-down';
        }
    }
}

// Function to toggle the inline edit form visibility
function toggleEditToolDefinitionInlineForm(toolId, showEditForm = true) {
    const detailsRow = toolRegistryListBody.querySelector(`tr.tool-details-row[data-id="${toolId}"]`);
    if (!detailsRow) return;

    const editSection = detailsRow.querySelector('.tool-details-edit-section');
    if (!editSection) return;

    const editForm = editSection.querySelector('form');
    if (!editForm) return;

    if (showEditForm) {
        editForm.style.display = 'flex'; // Show the form itself (which is flexed)
        const tool = toolDefinitionCache[toolId];
        if (tool) {
            populateInlineEditForm(tool);
        }
    } else {
        editForm.style.display = 'none'; // Hide the form
    }
}

// Function to render the system assignment section
function renderSystemAssignment(toolDefinitionId) {
    const toolDefinition = toolDefinitionCache[toolDefinitionId];
    if (!toolDefinition) return;

    const assignedSystemsContainer = toolRegistryListBody.querySelector(`.assigned-systems-container[data-tool-id="${toolDefinitionId}"]`);
    const searchInput = toolRegistryListBody.querySelector(`.system-search-input[data-tool-id="${toolDefinitionId}"]`);
    const searchResultsContainer = toolRegistryListBody.querySelector(`.system-search-results[data-tool-id="${toolDefinitionId}"]`);
    if (!assignedSystemsContainer || !searchInput || !searchResultsContainer) return;

    // Render assigned system tags
    assignedSystemsContainer.innerHTML = '';
    const assignedSystemIds = new Set(toolDefinition.available_on_systems);
    assignedSystemIds.forEach(systemId => {
        const system = window.systemCache[systemId];
        if (system) {
            const tag = document.createElement('span');
            tag.className = 'assigned-system-tag';
            tag.innerHTML = `${system.name} <i class="fa fa-times remove-system-btn" data-system-id="${system.id}" data-tool-id="${toolDefinitionId}"></i>`;
            assignedSystemsContainer.appendChild(tag);
        }
    });

    // Search input event listener
    searchInput.oninput = function() {
        const searchTerm = this.value.toLowerCase();
        searchResultsContainer.innerHTML = '';
        if (searchTerm.length === 0) {
            searchResultsContainer.classList.remove('visible');
            return;
        }

        const allSystems = Object.values(window.systemCache || {});
        const filteredSystems = allSystems.filter(system =>
            !assignedSystemIds.has(system.id) && system.name.toLowerCase().includes(searchTerm)
        );

        if (filteredSystems.length > 0) {
            filteredSystems.forEach(system => {
                const resultItem = document.createElement('div');
                resultItem.className = 'search-result-item';
                resultItem.textContent = system.name;
                resultItem.dataset.systemId = system.id;
                resultItem.onclick = () => {
                    websocket.send(JSON.stringify({
                        type: 'assign_system_to_tool',
                        payload: { tool_definition_id: toolDefinitionId, system_id: system.id }
                    }));
                    searchInput.value = '';
                    searchResultsContainer.classList.remove('visible');
                };
                searchResultsContainer.appendChild(resultItem);
            });
            searchResultsContainer.classList.add('visible');
        } else {
            searchResultsContainer.classList.remove('visible');
        }
    };
    
    // Hide search results when clicking outside
    document.addEventListener('click', function(event) {
        if (!searchResultsContainer.contains(event.target) && event.target !== searchInput) {
            searchResultsContainer.classList.remove('visible');
        }
    });
}


// Main rendering function for the tool definition list
function renderToolDefinitionList(toolDefinitions) {
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

    const templateSource = `
        {{#each this}}
        <tr data-id="{{this.id}}">
            <td class="tool-definition-name-cell">
                <div class="tool-definition-name">{{this.display_name}}</div>
                <div class="tool-definition-internal-name">({{this.name}})</div>
            </td>
            <td>{{#if this.is_builtin}}Built-in{{else}}External{{/if}}</td>
            <td>{{this.manifest_version}}</td>
            <td><span class="status-label status-{{this.status}}">{{this.status}}</span></td>
            <td>{{this.execution_mode}}</td> <!-- Display execution_mode -->
            <td><p class="tool-definition-description">{{this.description}}</p></td>
            <td>
                <label class="switch" title="Globally enable or disable this tool">
                    <input type="checkbox" class="toggle-active-btn" {{#if this.is_active}}checked{{/if}}>
                    <span class="slider round"></span>
                </label>
            </td>
            <td>
                <div class="tool-definition-actions">
                    {{#unless this.is_builtin}}
                        <button class="btn btn-xs btn-default refresh-tool-definition-btn" title="Refresh Manifest"><i class="fa fa-refresh"></i></button>
                    {{/unless}}

                    <button class="btn btn-xs btn-danger delete-tool-definition-btn" title="Delete Tool"><i class="fa fa-trash"></i></button>
                    <button class="btn btn-xs btn-default toggle-tool-details-btn" title="Toggle Details"><i class="fa fa-chevron-down"></i></button>
                </div>
            </td>
        </tr>
        <tr class="tool-details-row" data-id="{{this.id}}" style="display: none;">
            <td colspan="8">
                <div class="tool-details-container">
                    <div class="tool-details-flex-container">
                        <div class="tool-details-display-section">
                            <h5>System Availability</h5>
                            <div class="form-check">
                                <input class="form-check-input available-on-all-systems-checkbox" type="checkbox" id="availableOnAllSystems-{{this.id}}" data-tool-id="{{this.id}}" {{#if this.available_on_all_systems}}checked{{/if}}>
                                <label class="form-check-label" for="availableOnAllSystems-{{this.id}}">Available on all compatible systems</label>
                            </div>
                            <div class="system-assignment-section" style="{{#if this.available_on_all_systems}}display: none;{{/if}}">
                                <div class="assigned-systems-container" data-tool-id="{{this.id}}"></div>
                                <div class="search-and-add-systems">
                                    <input type="text" class="form-control system-search-input" placeholder="Add system..." data-tool-id="{{this.id}}">
                                    <div class="system-search-results" data-tool-id="{{this.id}}"></div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="tool-details-edit-section">
                            <form id="inline-edit-tool-definition-form-{{this.id}}">
                                <h5>Edit Tool Definition</h5>
                                <div class="form-group full-width">
                                    <label for="editToolDefinitionRepoUrl-{{this.id}}">Repository URL (Optional)</label>
                                    <input type="url" class="form-control" id="editToolDefinitionRepoUrl-{{this.id}}" placeholder="e.g., https://github.com/my-org/my-tool.git">
                                    <small class="form-text text-muted">Leave empty for manual definition.</small>
                                </div>
                                <div class="form-group">
                                    <label for="editToolDefinitionDisplayName-{{this.id}}">Display Name <span class="required">*</span></label>
                                    <input type="text" class="form-control" id="editToolDefinitionDisplayName-{{this.id}}" required>
                                </div>
                                <div class="form-group">
                                    <label for="editToolDefinitionName-{{this.id}}">Internal Name <span class="required">*</span></label>
                                    <input type="text" class="form-control" id="editToolDefinitionName-{{this.id}}" required>
                                    <small class="form-text text-muted">Unique identifier (snake_case, no spaces).</small>
                                </div>
                                <div class="form-group full-width">
                                    <label for="editToolDefinitionDescription-{{this.id}}">Description</label>
                                    <textarea type="text" class="form-control" id="editToolDefinitionDescription-{{this.id}}" rows="2"></textarea>
                                </div>
                                <div class="form-group">
                                    <label for="editToolDefinitionTransportType-{{this.id}}">Transport Type</label>
                                    <select class="form-control" id="editToolDefinitionTransportType-{{this.id}}">
                                        <option value="tcp">TCP</option>
                                        <option value="stdio">STDIO</option>
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label for="editToolDefinitionExecutionMode-{{this.id}}">Execution Mode</label>
                                    <select class="form-control" id="editToolDefinitionExecutionMode-{{this.id}}">
                                        <option value="shared">Shared (per System)</option>
                                        <option value="dedicated">Dedicated (per Agent Instance)</option>
                                    </select>
                                </div>
                                <button class="btn btn-default toggle-details-btn full-width" type="button" onclick="toggleDetails(this, 'edit-tool-definition-manual-details-{{this.id}}')">
                                    Manual Manifest Details <i class="fa fa-chevron-down"></i>
                                </button>
                                <div id="edit-tool-definition-manual-details-{{this.id}}" class="full-width" style="display: none;">
                                    <div class="form-group">
                                        <label for="editToolDefinitionCommand-{{this.id}}">Command</label>
                                        <input type="text" class="form-control" id="editToolDefinitionCommand-{{this.id}}" placeholder="e.g., python my_tool.py">
                                        <small class="form-text text-muted">Required for manual definitions.</small>
                                    </div>
                                    <div class="form-group">
                                        <label for="editToolDefinitionArgs-{{this.id}}">Arguments (JSON Array)</label>
                                        <input type="text" class="form-control" id="editToolDefinitionArgs-{{this.id}}" value="[]" placeholder='e.g., ["--port", "5000"]'>
                                    </div>
                                    <div class="form-group">
                                        <label for="editToolDefinitionPlatforms-{{this.id}}">Platforms (Comma-separated)</label>
                                        <input type="text" class="form-control" id="editToolDefinitionPlatforms-{{this.id}}" placeholder="e.g., linux,windows">
                                    </div>
                                </div>
                                <div style="margin-top: 15px;">
                                    <button type="submit" class="btn btn-success save-inline-edit-btn" data-tool-id="{{this.id}}">Save Changes</button>
                                    <button type="button" class="btn btn-default cancel-inline-edit-btn" data-tool-id="{{this.id}}">Cancel</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </td>
        </tr>
        {{/each}}
    `;
    const toolDefinitionTemplate = Handlebars.compile(templateSource);
    toolRegistryListBody.innerHTML = toolDefinitionTemplate(sortedTools);
    updateSortIndicators();
}

function handleToolDefinitionUpdate(toolDefinition) {
    toolDefinitionCache[toolDefinition.id] = toolDefinition;
    const toolRow = toolRegistryListBody.querySelector(`tr[data-id="${toolDefinition.id}"]:not(.tool-details-row)`);
    if (!toolRow) {
        renderToolDefinitionList(Object.values(toolDefinitionCache));
        return;
    }

    // In-place update of the main row
    toolRow.cells[0].innerHTML = `<div class="tool-definition-name">${toolDefinition.display_name}</div><div class="tool-definition-internal-name">(${toolDefinition.name})</div>`;
    toolRow.cells[1].textContent = toolDefinition.is_builtin ? 'Built-in' : 'External';
    toolRow.cells[2].textContent = toolDefinition.manifest_version || '';
    toolRow.cells[3].innerHTML = `<span class="status-label status-${toolDefinition.status}">${toolDefinition.status}</span>`;
    toolRow.cells[4].textContent = toolDefinition.execution_mode; // Update execution_mode
    toolRow.cells[5].querySelector('p').textContent = toolDefinition.description;
    toolRow.cells[6].querySelector('input').checked = toolDefinition.is_active;

    // In-place update of the details row content
    const detailsRow = toolRegistryListBody.querySelector(`tr.tool-details-row[data-id="${toolDefinition.id}"]`);
    if (detailsRow) {
        const allSystemsCheckbox = detailsRow.querySelector('.available-on-all-systems-checkbox');
        const assignmentSection = detailsRow.querySelector('.system-assignment-section');
        allSystemsCheckbox.checked = toolDefinition.available_on_all_systems;
        assignmentSection.style.display = toolDefinition.available_on_all_systems ? 'none' : 'block';
        if (detailsRow.style.display !== 'none') {
            renderSystemAssignment(toolDefinition.id);
        }
    }
}

function handleToolDefinitionDelete(toolDefinitionId) {
    delete toolDefinitionCache[toolDefinitionId];
    const toolRow = toolRegistryListBody.querySelector(`tr[data-id="${toolDefinitionId}"]:not(.tool-details-row)`);
    if (toolRow) {
        const detailsRow = toolRegistryListBody.querySelector(`tr.tool-details-row[data-id="${toolDefinitionId}"]`);
        if (detailsRow) detailsRow.remove();
        toolRow.remove();
    }
}

// Expose functions globally for websocket.js to call
window.renderToolDefinitionList = renderToolDefinitionList;
window.handleToolDefinitionUpdate = handleToolDefinitionUpdate;
window.handleToolDefinitionDelete = handleToolDefinitionDelete;

// DOMContentLoaded listener to set up initial event handlers
document.addEventListener('DOMContentLoaded', function() {
    if (toolRegistryTable) {
        toolRegistryTable.querySelector('thead').addEventListener('click', function(event) {
            const th = event.target.closest('th[data-sort]');
            if (!th) return;
            const newSortColumn = th.dataset.sort;
            if (newSortColumn === currentSortColumn) {
                currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                currentSortColumn = newSortColumn;
                currentSortDirection = 'asc';
            }
            renderToolDefinitionList(Object.values(toolDefinitionCache));
        });
    }

    if (toolRegistryListBody) {
        toolRegistryListBody.addEventListener('click', function(event) {
            const target = event.target;
            const toolRow = target.closest('tr[data-id]:not(.tool-details-row)'); // Exclude details row itself
            const toolId = toolRow ? toolRow.dataset.id : null;

            if (target.closest('.edit-tool-definition-btn')) {
                // Toggle the inline edit form
                toggleEditToolDefinitionInlineForm(toolId);
            } else if (target.closest('.refresh-tool-definition-btn')) {
                target.closest('.refresh-tool-definition-btn').querySelector('i').classList.add('fa-spin');
                websocket.send(JSON.stringify({ type: 'request_refresh_tool_definition_manifest', payload: { tool_definition_id: toolId } }));
            } else if (target.closest('.delete-tool-definition-btn')) {
                if (confirm('Are you sure you want to delete this tool definition?')) {
                    websocket.send(JSON.stringify({ type: 'delete_tool_definition', payload: { tool_definition_id: toolId } }));
                }
            } else if (target.closest('.toggle-tool-details-btn')) {
                const detailsRow = toolRegistryListBody.querySelector(`tr.tool-details-row[data-id="${toolId}"]`);
                const icon = target.closest('.toggle-tool-details-btn').querySelector('i');
                const isHidden = detailsRow.style.display === 'none';
                detailsRow.style.display = isHidden ? 'table-row' : 'none';
                icon.className = `fa ${isHidden ? 'fa-chevron-up' : 'fa-chevron-down'}`;
                // Toggle the inline edit form visibility as well
                toggleEditToolDefinitionInlineForm(toolId, isHidden);

                if (isHidden) { // If it's now visible
                    renderSystemAssignment(toolId);
                    toggleEditToolDefinitionInlineForm(toolId, true); // Show and populate the edit form
                } else {
                    toggleEditToolDefinitionInlineForm(toolId, false); // Hide the edit form
                }
            } else if (target.closest('.remove-system-btn')) {
                const systemId = target.dataset.systemId;
                websocket.send(JSON.stringify({ type: 'unassign_system_from_tool', payload: { tool_definition_id: toolId, system_id: systemId } }));
            } else if (target.closest('.save-inline-edit-btn')) {
                event.preventDefault(); // Prevent default form submission
                const form = target.closest('form');
                const editedToolId = target.dataset.toolId;

                const payload = {
                    tool_definition_id: editedToolId,
                    updates: {
                        display_name: form.querySelector(`#editToolDefinitionDisplayName-${editedToolId}`).value,
                        name: form.querySelector(`#editToolDefinitionName-${editedToolId}`).value,
                        description: form.querySelector(`#editToolDefinitionDescription-${editedToolId}`).value,
                        transport_type: form.querySelector(`#editToolDefinitionTransportType-${editedToolId}`).value,
                        execution_mode: form.querySelector(`#editToolDefinitionExecutionMode-${editedToolId}`).value,
                        repository_url: form.querySelector(`#editToolDefinitionRepoUrl-${editedToolId}`).value,
                        manifest: {
                            server: {
                                command: form.querySelector(`#editToolDefinitionCommand-${editedToolId}`).value,
                                args: JSON.parse(form.querySelector(`#editToolDefinitionArgs-${editedToolId}`).value || '[]'),
                                platforms: form.querySelector(`#editToolDefinitionPlatforms-${editedToolId}`).value.split(',').map(p => p.trim()).filter(p => p !== '')
                            }
                        }
                    }
                };
                websocket.send(JSON.stringify({ type: 'update_tool_definition', payload: payload }));
                toggleEditToolDefinitionInlineForm(editedToolId, false); // Hide form after saving
            } else if (target.closest('.cancel-inline-edit-btn')) {
                const cancelledToolId = target.dataset.toolId;
                toggleEditToolDefinitionInlineForm(cancelledToolId, false); // Hide form
            }
        });

        toolRegistryListBody.addEventListener('change', function(event) {
            const target = event.target;
            const toolRow = target.closest('tr[data-id]');
            const toolId = toolRow ? toolRow.dataset.id : null;

            if (target.matches('.toggle-active-btn')) {
                websocket.send(JSON.stringify({ type: 'toggle_tool_definition_active', payload: { tool_definition_id: toolId } }));
            } else if (target.matches('.available-on-all-systems-checkbox')) {
                websocket.send(JSON.stringify({
                    type: 'update_tool_definition',
                    payload: { tool_definition_id: toolId, updates: { available_on_all_systems: target.checked } }
                }));
            }
        });
    }

    const addToolBtn = document.getElementById('add-tool-definition-btn');
    if (addToolBtn) {
        addToolBtn.addEventListener('click', openAddToolDefinitionModal);
    }
});
