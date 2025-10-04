const systemListContainerTemplate = Handlebars.compile(`
    <table class="systems-table table table-striped table-hover">
        <thead>
            <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Executor Mode</th>
                <th>Executor URL</th>
                <th>Last Heartbeat</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            <!-- System rows will be appended here -->
        </tbody>
    </table>
`);

const systemItemRowTemplate = Handlebars.compile(`
    <tr class="system-item" data-system-id="{{id}}">
        <td><span class="system-name">{{name}}</span></td>
        <td><span class="system-status status-{{statusClass}}">{{status}}</span></td>
        <td>{{executor_mode_display}}</td>
        <td>{{executor_url_display}}</td>
        <td><span class="heartbeat-time">{{last_heartbeat_display}}</span></td>
        <td>
            <button class="btn btn-xs btn-default toggle-details-btn" title="Show Details">
                <i class="fa fa-chevron-{{detailsIcon}}"></i>
            </button>
            <button class="btn btn-xs btn-default deploy-system-btn" title="Deploy" disabled>
                <i class="fa fa-upload"></i>
            </button>
        </td>
    </tr>
`);

// Define and register executorModeOptionTemplate partial
const executorModeOptionTemplate = Handlebars.compile(`
    <option value="{{value}}" {{#if isSelected}}selected{{/if}}>{{text}}</option>
`);
Handlebars.registerPartial('executorModeOptionTemplate', executorModeOptionTemplate);

// Define and register osOptionTemplate partial
const osOptionTemplate = Handlebars.compile(`
    <option value="{{value}}" {{#if isSelected}}selected{{/if}}>{{text}}</option>
`);
Handlebars.registerPartial('osOptionTemplate', osOptionTemplate);


const systemDetailsTemplate = Handlebars.compile(`
    <tr class="system-details-row {{#if isHidden}}hidden{{/if}}">
        <td colspan="6">
            <div class="system-details-content">
                <!-- Display View -->
                <div class="system-details-display" style="display: {{#if isEditing}}none{{else}}block{{/if}};">
                    <p>Description: <b>{{description_display}}</b></p>
                    <p>Operating System: <b>{{os_display}}</b></p>
                    <p>Is Remote Executor: <b>{{is_remote_executor_display}}</b></p>
                    <p>Executor URL: <b>{{executor_url_display}}</b></p>
                    <p>Executor API Key: <b>{{executor_api_key_display}}</b></p>
                    <p>Executor Mode: <b>{{executor_mode_display}}</b></p>
                    <button class="btn btn-xs btn-info edit-system-btn" style="margin-top: 10px;">Edit</button>
                </div>
                <div class="system-installed-tools">
                    <h4>Installed Tools 
                        <button class="btn btn-xs btn-default add-tool-installation-btn" title="Install Tool">
                            <i class="fa fa-plus"></i>
                        </button>
                    </h4>
                    <div class="tool-installation-list" id="tool-installation-list-{{id}}">
                        <!-- Tool installations for this system will be rendered here -->
                        <p class="no-installations-message">No tools installed on this system.</p>
                    </div>
                </div>

                <!-- Edit View -->
                <div class="system-details-edit" style="display: {{#if isEditing}}block{{else}}none{{/if}};">
                    <div class="form-group"><label>Description:</label><textarea class="form-control" name="description">{{description}}</textarea></div>
                    <div class="form-group"><label>Is Remote Executor:</label><input type="checkbox" name="is_remote_executor" {{#if is_remote_executor}}checked{{/if}}></div>
                    <div class="form-group"><label>Executor URL:</label><input type="url" class="form-control" name="executor_url" value="{{executor_url}}"></div>
                    <div class="form-group"><label>Executor API Key:</label><input type="text" class="form-control" name="executor_api_key" value="{{executor_api_key}}"></div>
                    <div class="form-group"><label>Operating System:</label><select class="form-control" name="os">
                        {{#each osOptions}}
                            {{> osOptionTemplate this}}
                        {{/each}}
                    </select></div>
                    <div class="form-group"><label>Executor Mode:</label><select class="form-control" name="executor_mode">
                        {{#each executorModeOptions}}
                            {{> executorModeOptionTemplate this}}
                        {{/each}}
                    </select></div>
                    <div style="margin-top: 10px;">
                        <button class="btn btn-xs btn-success save-system-btn">Save</button>
                        <button class="btn btn-xs btn-default cancel-edit-system-btn">Cancel</button>
                    </div>
                </div>
            </div>
        </td>
    </tr>
`);

const toolInstallationItemTemplate = Handlebars.compile(`
    <div class="tool-installation-item" data-installation-id="{{id}}" data-system-id="{{system_id}}" data-tool-definition-id="{{tool_definition_id}}">
        <div class="tool-installation-item-header">
            <span class="tool-installation-name">{{tool_definition_name}}</span>
            <span class="tool-installation-status status-{{status}}">{{status_display}}</span>

        </div>
        <div class="tool-installation-details">
            {{#if local_path}}<p class="tool-installation-path">Path: <code>{{local_path}}</code></p>{{/if}}
            {{#if assigned_port}}<p class="tool-installation-port">Port: <b>{{assigned_port}}</b></p>{{/if}}
            {{#if process_id}}<p class="tool-installation-pid">PID: <b>{{process_id}}</b></p>{{/if}}
        </div>

        <div class="tool-installation-actions">
            {{#if can_start}}
                <button class="btn btn-xs btn-success start-tool-installation-btn" title="Start Tool"> <i class="fa fa-play"></i> </button>
            {{/if}}
            {{#if can_stop}}
                <button class="btn btn-xs btn-warning stop-tool-installation-btn" title="Stop Tool"> <i class="fa fa-stop"></i> </button>
            {{/if}}
            <button class="btn btn-xs btn-info view-tool-logs-btn" title="View/Hide Logs"> <i class="fa fa-file-text-o"></i> </button>
            <button class="btn btn-xs btn-danger delete-tool-installation-btn" title="Uninstall Tool"> <i class="fa fa-trash"></i> </button>
        </div>
        <div class="tool-installation-logs" style="display: none;"></div>
    </div>
`);

const toolInstallationLogEntryTemplate = Handlebars.compile(`
    <div class="log-entry log-{{this.level}}">
        <span class="log-timestamp">{{this.formatted_timestamp}}</span>
        <span class="log-message">{{this.message}}</span>
    </div>
`);

function renderToolInstallationLogsInline(logs) {
    if (!logs || logs.length === 0) return;
    const installationId = logs[0].tool_installation_id;
    const container = $(`.tool-installation-item[data-installation-id="${installationId}"] .tool-installation-logs`);
    
    if (container.length) {
        const formattedLogs = logs.map(log => ({
            ...log,
            formatted_timestamp: new Date(log.timestamp).toLocaleString()
        }));
        
        let html = '';
        formattedLogs.forEach(log => {
            html += toolInstallationLogEntryTemplate(log);
        });
        container.html(html);
    }
}

function renderSystemList(systems) {
    const container = $('#tabContent_systems');
    if (container.length === 0) return;

    $('#add-system-btn').off('click').on('click', function() {
        const systemName = prompt("Enter a name for the new system:", "New System");
        if (systemName) {
            sendSystemCreateRequest(systemName);
        }
    });

    const body = container.find('#systems-list-body');
    body.empty(); // Clear existing content

    // Create the table structure using template
    body.append(systemListContainerTemplate());
    const tableBody = body.find('tbody'); // Get the tbody after it's been appended

    // Render each system as a table row
    systems.forEach(system => {
        renderSystem(system);
    });
}

function renderSystem(system) {
    const tableBody = $('#tabContent_systems').find('tbody');

    // Check if system already exists to preserve state
    const existingItemRow = tableBody.find(`tr[data-system-id="${system.id}"]`);
    let detailsAreVisible = false;
    let isEditing = false;

    if (existingItemRow.length > 0) {
        const existingDetailsRow = existingItemRow.next('.system-details-row');
        if (existingDetailsRow.length > 0) {
            detailsAreVisible = !existingDetailsRow.hasClass('hidden');
            isEditing = existingDetailsRow.find('.system-details-edit').is(':visible');
        }
    }

    const osOptionsData = [
        { value: 'linux', text: 'Linux' },
        { value: 'windows', text: 'Windows' },
        { value: 'osx', text: 'macOS' }
    ].map(opt => ({
        ...opt,
        isSelected: system.os === opt.value
    }));

    const executorModeOptionsData = [
        { value: 'local', text: 'Local Execution' },
        { value: 'http', text: 'HTTP Remote Executor' },
        { value: 'websocket', text: 'WebSocket Remote Executor' }
    ].map(opt => ({
        ...opt,
        isSelected: system.executor_mode === opt.value
    }));

    const systemData = {
        ...system,
        statusClass: (system.status || 'offline').toLowerCase(),
        executor_mode_display: system.executor_mode || 'N/A',
        executor_url_display: system.executor_url || 'N/A',
        last_heartbeat_display: system.last_heartbeat ? new Date(system.last_heartbeat).toLocaleString() : 'N/A',
        detailsIcon: detailsAreVisible ? 'up' : 'down',
        isHidden: !detailsAreVisible, // For the details row
        isEditing: isEditing,
        os_display: system.os ? system.os.charAt(0).toUpperCase() + system.os.slice(1) : 'N/A',
        description_display: system.description || 'N/A',
        is_remote_executor_display: system.is_remote_executor ? 'Yes' : 'No',
        executor_api_key_display: system.executor_api_key ? '********' : 'N/A',
        osOptions: osOptionsData,
        executorModeOptions: executorModeOptionsData
    };

    const systemItemHtml = systemItemRowTemplate(systemData);
    const systemDetailsHtml = systemDetailsTemplate(systemData);

    if (existingItemRow.length > 0) {
        existingItemRow.next('.system-details-row').remove(); // Remove old details row
        existingItemRow.replaceWith(systemItemHtml); // Replace main item row
        tableBody.find(`tr[data-system-id="${system.id}"]`).after(systemDetailsHtml); // Insert new details after it
    } else {
        tableBody.append(systemItemHtml);
        tableBody.find(`tr[data-system-id="${system.id}"]`).after(systemDetailsHtml);
    }
}

function renderToolInstallationList(toolInstallations, systemId) {
    const container = $(`#tool-installation-list-${systemId}`);
    if (container.length === 0) {
        console.error(`Tool installation list container not found for system ID: ${systemId}`);
        return;
    }
    container.empty();

    if (toolInstallations && toolInstallations.length > 0) {
        toolInstallations.forEach(installation => {
            const statusLower = installation.status.toLowerCase();
            const html = toolInstallationItemTemplate({
                ...installation,
                status: statusLower.replace(/_/g, '-'), // For CSS classes
                status_display: installation.status.replace(/_/g, ' ').replace(/(?:^|\s)\S/g, a => a.toUpperCase()), // "not_installed" -> "Not Installed"
                can_start: statusLower === 'stopped' || statusLower === 'installed' || statusLower === 'error',
                can_stop: statusLower === 'running'
            });
            container.append(html);
        });
    } else {
        container.append('<p class="no-installations-message">No tools installed on this system.</p>');
    }
}

// Global functions for Tool Installation Modal
function openAddToolInstallationModal(systemId) {
    $('#toolInstallationModalTitle').text('Install Tool');
    $('#toolInstallationForm')[0].reset();
    $('#toolInstallationId').val('');
    $('#toolInstallationSystemId').val(systemId);

    populateToolDefinitionSelect(systemId); // Populate select with available tools for this system

    $('#saveToolInstallationBtn').off('click').on('click', saveToolInstallation);
    $('#toolInstallationModal').show();
}

function requestToolInstallationAction(installationId, actionType) {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: `tool_installation_${actionType}`, // e.g., 'tool_installation_start'
            payload: { installation_pk: installationId }
        }));
    } else {
        alert(`Cannot ${actionType} installation. WebSocket is not connected.`);
    }
}

function closeToolInstallationModal() {
    $('#toolInstallationModal').hide();
    $('#toolInstallationForm')[0].reset();
    $('#toolInstallationToolDefinitionId').prop('disabled', false); // Re-enable for next add
}

function populateToolDefinitionSelect(systemId, selectedToolDefinitionId = null) {
    const toolSelect = $('#toolInstallationToolDefinitionId');
    toolSelect.empty();
    toolSelect.append('<option value="">-- Select a Tool --</option>');

    const toolDefinitions = window.allToolDefinitions || {};
    const installedToolIds = Object.values(window.allToolInstallations || {})
                                .filter(inst => String(inst.system_id) === String(systemId))
                                .map(inst => inst.tool_definition_id);

    const sortedToolDefs = Object.values(toolDefinitions).sort((a, b) => a.name.localeCompare(b.name));

    sortedToolDefs.forEach(toolDef => {
        if (toolDef.is_builtin) return; // Don't allow installing built-in tools

        if (!installedToolIds.includes(toolDef.id) || toolDef.id === selectedToolDefinitionId) {
            const option = $('<option></option>')
                .val(toolDef.id)
                .text(`${toolDef.display_name} (${toolDef.name})`);
            if (toolDef.id === selectedToolDefinitionId) {
                option.prop('selected', true);
            }
            toolSelect.append(option);
        }
    });
}

function saveToolInstallation() {
    const installationId = $('#toolInstallationId').val();
    const systemId = $('#toolInstallationSystemId').val();
    const toolDefinitionId = $('#toolInstallationToolDefinitionId').val();

    if (!toolDefinitionId) {
        alert('Please select a Tool Definition.');
        return;
    }
    if (!systemId) {
        alert('System ID is missing. This is an internal error.');
        return;
    }

    const payload = {
        tool_definition_pk: toolDefinitionId,
        system_pk: systemId,
    };

    let messageType = 'create_tool_installation';
    if (installationId) {
        messageType = 'create_tool_installation'; 
        payload.installation_pk = installationId;
    }
    
    websocket.send(JSON.stringify({ type: messageType, payload: payload }));
    closeToolInstallationModal();
}

function requestToolInstallationDeletion(installationId, toolName) {
    if (confirm(`Are you sure you want to uninstall "${toolName}"?`)) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'delete_tool_installation',
                payload: { installation_pk: installationId }
            }));
        } else {
            alert("Cannot delete installation. WebSocket is not connected.");
        }
    }
}

// Single, unified event listener for the Systems tab
document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('tabContent_systems');
    if (!container) return;

    container.addEventListener('click', function(event) {
        const target = $(event.target);
        
        let systemItemRow = target.closest('.system-item');
        let systemDetailsRow;

        if (!systemItemRow.length && target.closest('.system-details-row').length) {
            systemDetailsRow = target.closest('.system-details-row');
            systemItemRow = systemDetailsRow.prev('.system-item');
        } else if (systemItemRow.length) {
            systemDetailsRow = systemItemRow.next('.system-details-row');
        } else {
            return;
        }
        
        if (!systemItemRow.length) return;
        const systemId = systemItemRow.data('system-id');

        // Add Tool Installation
        if (target.closest('.add-tool-installation-btn').length) {
            openAddToolInstallationModal(systemId);
            return;
        }

        // Start Tool Installation
        if (target.closest('.start-tool-installation-btn').length) {
            const installationId = target.closest('.tool-installation-item').data('installation-id');
            requestToolInstallationAction(installationId, 'start');
            return;
        }

        // Stop Tool Installation
        if (target.closest('.stop-tool-installation-btn').length) {
            const installationId = target.closest('.tool-installation-item').data('installation-id');
            requestToolInstallationAction(installationId, 'stop');
            return;
        }

        // View/Hide Tool Logs
        if (target.closest('.view-tool-logs-btn').length) {
            const installationItem = target.closest('.tool-installation-item');
            const installationId = installationItem.data('installation-id');
            const logsContainer = installationItem.find('.tool-installation-logs');

            const isVisible = logsContainer.is(':visible');
            logsContainer.toggle(!isVisible);

            if (!isVisible && logsContainer.is(':empty')) {
                logsContainer.html('<p class="log-message">Loading logs...</p>');
                if (websocket && websocket.readyState === WebSocket.OPEN) {
                    websocket.send(JSON.stringify({
                        type: 'request_tool_installation_logs',
                        payload: { installation_id: installationId }
                    }));
                } else {
                    logsContainer.html('<p class="log-message log-error">WebSocket is not connected.</p>');
                }
            }
            return;
        }

        // Delete Tool Installation
        if (target.closest('.delete-tool-installation-btn').length) {
            const installationItem = target.closest('.tool-installation-item');
            const installationId = installationItem.data('installation-id');
            const toolName = installationItem.find('.tool-installation-name').text();
            requestToolInstallationDeletion(installationId, toolName);
            return;
        }

        // Edit System Details
        if (target.closest('.edit-system-btn').length) {
            systemDetailsRow.find('.system-details-display').hide();
            systemDetailsRow.find('.system-details-edit').show();
            return;
        }

        // Cancel Edit System Details
        if (target.closest('.cancel-edit-system-btn').length) {
            systemDetailsRow.find('.system-details-edit').hide();
            systemDetailsRow.find('.system-details-display').show();
            return;
        }

        // Save System Details
        if (target.closest('.save-system-btn').length) {
            const editForm = systemDetailsRow.find('.system-details-edit');
            const data = {
                description: editForm.find('textarea[name="description"]').val(),
                is_remote_executor: editForm.find('input[name="is_remote_executor"]').is(':checked'),
                executor_url: editForm.find('input[name="executor_url"]').val(),
                executor_api_key: editForm.find('input[name="executor_api_key"]').val(),
                os: editForm.find('select[name="os"]').val(),
                executor_mode: editForm.find('select[name="executor_mode"]').val()
            };
            if (websocket && websocket.readyState === WebSocket.OPEN) {
                websocket.send(JSON.stringify({
                    type: 'update_system_details',
                    payload: { system_pk: systemId, data: data }
                }));
            }
            return;
        }

        // Toggle details button
        if (target.closest('.toggle-details-btn').length) {
            const icon = target.closest('.toggle-details-btn').find('i');
            const isHidden = systemDetailsRow.hasClass('hidden');
            
            systemDetailsRow.toggleClass('hidden');
            icon.removeClass(isHidden ? 'fa-chevron-down' : 'fa-chevron-up')
                .addClass(isHidden ? 'fa-chevron-up' : 'fa-chevron-down');

            if (isHidden) { // If it WAS hidden, it's now visible
                websocket.send(JSON.stringify({
                    type: 'request_tool_installation_list',
                    payload: { system_pk: systemId }
                }));
            }
        }
    });
});
