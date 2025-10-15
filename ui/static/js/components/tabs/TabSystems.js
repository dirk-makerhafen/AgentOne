// This file manages the rendering and interactions for the Systems list tab.

window.systemCache = window.systemCache || {};

Handlebars.registerPartial('TabSystemsExecutorModeOptionTemplate', getTemplate('TabSystemsExecutorModeOptionTemplate'));
Handlebars.registerPartial('TabSystemsOSOptionTemplate', getTemplate('TabSystemsOSOptionTemplate'));

let toolInstallationModalTemplate;

function initializeSystemTemplates() {
    toolInstallationModalTemplate = getTemplate('TabSystemsToolInstallationModal');
    Handlebars.registerPartial('SystemListContainerTemplate', getTemplate('TabSystemsTemplate'));
    Handlebars.registerPartial('SystemItemRowTemplate', getTemplate('TabSystemsListItemTemplate'));
    Handlebars.registerPartial('SystemDetailsTemplate', getTemplate('TabSystemsDetailsTemplate'));
    Handlebars.registerPartial('ToolInstallationItemTemplate', getTemplate('TabSystemsToolInstallationItemTemplate'));
    Handlebars.registerPartial('ToolInstanceItemTemplate', getTemplate('TabSystemsToolInstanceItemTemplate')); // Register new partial
    Handlebars.registerPartial('ToolInstallationLogEntryTemplate', getTemplate('TabSystemsToolInstallationLogEntryTemplate'));
}

function renderToolInstallationLogsInline(logs) {
    if (!logs || logs.length === 0) return;
    const toolInstallationLogEntryTemplate = getTemplate('TabSystemsToolInstallationLogEntryTemplate');
    const logsArray = Array.isArray(logs) ? logs : [logs];
    const installationId = logsArray[0].tool_installation_id;
    const container = document.querySelector(`.tool-installation-item[data-installation-id="${installationId}"] .tool-installation-logs`);

    if (container) {
        const formattedLogs = logsArray.map(log => ({
            ...log,
            formatted_timestamp: new Date(log.timestamp).toLocaleString()
        }));
        let html = '';
        formattedLogs.forEach(log => {
            html += toolInstallationLogEntryTemplate(log);
        });
        container.innerHTML = html;
    }
}

function renderSystemList(systems) {
    const containerElement = document.getElementById('tabContent_systems');
    if (!containerElement) {
        // Tab was likely closed before data arrived
        return;
    }
    systems.forEach(system => { window.systemCache[system.id] = system; });
    const body = containerElement.querySelector('#systems-list-body > table > tbody');
    if (!body) { console.error("Could not find tbody in systems list."); return; }
    body.innerHTML = '';
    systems.forEach(system => renderSystem(system, body));
}

function renderSystem(system, tableBody) {
    // If tableBody isn't provided, find it. This happens on single-system updates.
    if (!tableBody) {
        const container = document.getElementById('tabContent_systems');
        if (!container) return; // Tab might be closed
        tableBody = container.querySelector('#systems-list-body > table > tbody');
        if (!tableBody) return; // tbody not found
    }
    const systemItemRowTemplate = getTemplate('TabSystemsListItemTemplate');
    const systemDetailsTemplate = getTemplate('TabSystemsDetailsTemplate');

    if (system && system.id) { window.systemCache[system.id] = system; }

    const existingItemRow = tableBody.querySelector(`tr.system-item[data-system-id="${system.id}"]`);
    let detailsAreVisible = false;
    let isEditing = false;

    if (existingItemRow) {
        const existingDetailsRow = existingItemRow.nextElementSibling;
        if (existingDetailsRow && existingDetailsRow.classList.contains('system-details-row')) {
            // Capture the *current* visibility state from the DOM
            detailsAreVisible = !existingDetailsRow.classList.contains('hidden');
            // Also capture the editing state
            const editForm = existingDetailsRow.querySelector('.system-details-edit');
            isEditing = editForm && editForm.style.display !== 'none';
        }
    }

    const osOptionsData = [
        { value: 'linux', text: 'Linux' }, { value: 'windows', text: 'Windows' }, { value: 'osx', text: 'macOS' }
    ].map(opt => ({ ...opt, isSelected: system.os === opt.value }));

    const executorModeOptionsData = [
        { value: 'local', text: 'Local Execution' }, { value: 'http', text: 'HTTP Remote Executor' }, { value: 'websocket', text: 'WebSocket Remote Executor' }
    ].map(opt => ({ ...opt, isSelected: system.executor_mode === opt.value }));

    const systemData = {
        ...system,
        statusClass: (system.status || 'offline').toLowerCase(),
        executor_mode_display: system.executor_mode || 'N/A',
        executor_url_display: system.executor_url || 'N/A',
        last_heartbeat_display: system.last_heartbeat ? new Date(system.last_heartbeat).toLocaleString() : 'N/A',
        detailsIcon: detailsAreVisible ? 'up' : 'down',
        isHidden: !detailsAreVisible,
        isEditing: isEditing,
        os_display: system.os ? system.os.charAt(0).toUpperCase() + system.os.slice(1) : 'N/A',
        description_display: system.description || 'N/A',
        executor_api_key_display: system.executor_api_key ? '********' : 'N/A',
        osOptions: osOptionsData,
        executorModeOptions: executorModeOptionsData
    };

    const systemItemHtml = systemItemRowTemplate(systemData);
    const systemDetailsHtml = systemDetailsTemplate(systemData);
    
    // Use a temporary tbody element to correctly parse the <tr> HTML strings
    const tempContainer = document.createElement('tbody');
    tempContainer.innerHTML = systemItemHtml + systemDetailsHtml;
    const newItemRow = tempContainer.children[0];
    const newDetailsRow = tempContainer.children[1];

    if (existingItemRow) {
        const existingDetailsRow = existingItemRow.nextElementSibling;
        
        existingItemRow.replaceWith(newItemRow);
        
        if (existingDetailsRow && existingDetailsRow.classList.contains('system-details-row')) {
            existingDetailsRow.replaceWith(newDetailsRow);
        } else {
            // Insert the details row if it was missing for some reason
            newItemRow.after(newDetailsRow);
        }
    } else {
        // If the system row is new, append both children
        tableBody.appendChild(newItemRow);
        tableBody.appendChild(newDetailsRow);
    }
}

function renderToolInstallationList(toolInstallations, systemId) {
    const toolInstallationItemTemplate = getTemplate('TabSystemsToolInstallationItemTemplate');
    const toolInstanceItemTemplate = getTemplate('TabSystemsToolInstanceItemTemplate');
    const container = document.getElementById(`tool-installation-list-${systemId}`);
    if (!container) { return; } // Details row might be closed
    container.innerHTML = '';

    if (toolInstallations && toolInstallations.length > 0) {
        toolInstallations.forEach(installation => {
            const installationStatusLower = installation.status.toLowerCase();
            const runningInstances = installation.instances.filter(
                instance => ['running', 'starting'].includes(instance.status)
            );

            // Data for the main installation item
            const installationData = {
                ...installation,
                installation_status_display: installationStatusLower.replace(/_/g, ' ').replace(/(?:^|\s)\S/g, a => a.toUpperCase()),
                installation_status_class: installationStatusLower.replace(/_/g, '-'),
                running_instances_count: runningInstances.length,
                instance_status_class: runningInstances.length > 0 ? 'running' : 'stopped', // Simplified status for the tag
                can_start: installationStatusLower === 'installed' && runningInstances.length < installation.max_parallel_instances,
            };

            // Render the main installation item
            const installationHtml = toolInstallationItemTemplate(installationData);
            container.insertAdjacentHTML('beforeend', installationHtml);

            // Now, find the container within the newly added element and render the instances
            const newInstallationElement = container.lastElementChild;
            const instanceListContainer = newInstallationElement.querySelector('.tool-instance-list-container');
            
            if (instanceListContainer && runningInstances.length > 0) {
                let instancesHtml = '';
                // Sort to show newest running instance first
                runningInstances.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
                
                runningInstances.forEach(instance => {
                    const instanceData = {
                        ...instance,
                        created_at_display: new Date(instance.created_at).toLocaleString(),
                        status_class: instance.status.toLowerCase().replace(/_/g, '-')
                    };
                    instancesHtml += toolInstanceItemTemplate(instanceData);
                });
                instanceListContainer.innerHTML = instancesHtml;
            }
        });
    } else {
        container.innerHTML = '<p class="no-installations-message">No tools installed on this system.</p>';
    }
}

// --- Tab ---

function openSystemsTab(targetPanelId = 'mainTabPanel') {
    const tabContentId = 'tabContent_systems';
    const tabName = 'Systems';
    
    const existingTab = document.getElementById(tabContentId);

    if (existingTab) {
        openMainTab(null, tabContentId, targetPanelId);
    } else {
        initializeSystemTemplates();
        const tabSystemsTemplate = getTemplate('TabSystemsTemplate');
        const tabContentHtml = tabSystemsTemplate({});
        const modalHtml = toolInstallationModalTemplate({});
        const finalHtml = tabContentHtml + modalHtml;
        openMainTab(null, tabContentId, targetPanelId, tabName, finalHtml);
    }
    
    systemApi.list();
    addToClientLog(`Client: Opened Systems tab.`, 'info');
}


// --- System Actions ---

function systemCreate(event) {
    event.stopPropagation();
    const systemName = prompt("Enter a name for the new system:", "New System");
    if (systemName) {
        systemApi.create(systemName);
    }
}

function systemToggleDetails(event, systemId) {
    event.stopPropagation();
    const detailsRow = document.querySelector(`.system-details-row[data-system-id="${systemId}"]`);
    const icon = event.currentTarget.querySelector('i');
    if (!detailsRow || !icon) return;

    const isHidden = detailsRow.classList.contains('hidden');
    detailsRow.classList.toggle('hidden', !isHidden);
    icon.classList.toggle('fa-chevron-down', !isHidden);
    icon.classList.toggle('fa-chevron-up', isHidden);

    if (isHidden) { // If it WAS hidden, it's now visible
        toolInstallationApi.list(systemId);
    }
}

function systemShowEditForm(event, systemId) {
    event.stopPropagation();
    const detailsRow = document.querySelector(`.system-details-row[data-system-id="${systemId}"]`);
    if (!detailsRow) return;
    detailsRow.querySelector('.system-details-display').style.display = 'none';
    detailsRow.querySelector('.system-details-edit').style.display = 'block';
}

function systemCancelEdit(event, systemId) {
    event.stopPropagation();
    const detailsRow = document.querySelector(`.system-details-row[data-system-id="${systemId}"]`);
    if (!detailsRow) return;
    detailsRow.querySelector('.system-details-edit').style.display = 'none';
    detailsRow.querySelector('.system-details-display').style.display = 'block';
}

function systemSaveChanges(event, systemId) {
    event.stopPropagation();
    const detailsRow = document.querySelector(`.system-details-row[data-system-id="${systemId}"]`);
    if (!detailsRow) return;
    const editForm = detailsRow.querySelector('.system-details-edit');
    const data = {
        description: editForm.querySelector('textarea[name="description"]').value,
        executor_url: editForm.querySelector('input[name="executor_url"]').value,
        executor_api_key: editForm.querySelector('input[name="executor_api_key"]').value,
        os: editForm.querySelector('select[name="os"]').value,
        executor_mode: editForm.querySelector('select[name="executor_mode"]').value
    };
    systemApi.update(systemId, data);
}


// --- Tool Installation Actions ---

function toolInstallationOpenModal(event, systemId) {
    event.stopPropagation();
    const modal = document.querySelector('#toolInstallationModal');
    if (!modal) { addToClientLog("Tool Installation Modal not found.", 'error'); return; }

    modal.querySelector('#toolInstallationModalTitle').textContent = 'Install Tool';
    modal.querySelector('#toolInstallationForm').reset();
    modal.querySelector('#toolInstallationId').value = '';
    modal.querySelector('#toolInstallationSystemId').value = systemId;
    populateToolDefinitionSelect(systemId, modal);
    modal.style.display = 'block';
}

function toolInstallationCloseModal(event) {
    if (event) {
        event.stopPropagation();
    }
    const modal = document.querySelector('#toolInstallationModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function toolInstallationSave(event) {
    event.stopPropagation();
    const modal = document.querySelector('#toolInstallationModal');
    const systemId = modal.querySelector('#toolInstallationSystemId').value;
    const toolDefinitionId = modal.querySelector('#toolInstallationToolDefinitionId').value;
    const maxParallelInstances = parseInt(modal.querySelector('input[name="max_parallel_instances"]').value, 10);

    if (!toolDefinitionId) { alert('Please select a Tool Definition.'); return; }
    if (!systemId) { alert('System ID is missing. This is an internal error.'); return; }
    if (isNaN(maxParallelInstances) || maxParallelInstances < 1 || maxParallelInstances > 64) {
        alert('Max Parallel Instances must be a number between 1 and 64.');
        return;
    }

    toolInstallationApi.create(toolDefinitionId, systemId, maxParallelInstances); // Pass new parameter
    toolInstallationCloseModal(event);
}

function toolInstallationStart(event, installationId) {
    event.stopPropagation();
    toolInstallationApi.start(installationId);
}

function toolInstallationStop(event, instancePkToStop) {
    event.stopPropagation();
    if (instancePkToStop) {
        toolInstanceApi.stop(instancePkToStop);
    } else {
        addToClientLog("Error: No ToolInstance PK provided to stop.", 'error');
    }
}

function toolInstallationDelete(event, installationId, toolName) {
    event.stopPropagation();
    if (confirm(`Are you sure you want to uninstall "${toolName}"?`)) {
        toolInstallationApi.delete(installationId);
    }
}

function toolInstallationToggleLogs(event, installationId) {
    event.stopPropagation();
    const logsContainer = event.currentTarget.closest('.tool-installation-item').querySelector('.tool-installation-logs');
    if (!logsContainer) return;

    const isVisible = logsContainer.style.display === 'block';
    logsContainer.style.display = isVisible ? 'none' : 'block';

    if (!isVisible && logsContainer.innerHTML.trim() === '') {
        logsContainer.innerHTML = '<p class="log-message">Loading logs...</p>';
        toolInstallationApi.getLogs(installationId);
    }
}

function populateToolDefinitionSelect(systemId, modalElement) {
    const toolSelect = modalElement.querySelector('#toolInstallationToolDefinitionId');
    toolSelect.innerHTML = '<option value="">-- Select a Tool --</option>';

    const toolDefinitions = window.allToolDefinitions || {};
    const installedToolIds = Object.values(window.allToolInstallations || {})
        .filter(inst => String(inst.system_id) === String(systemId))
        .map(inst => inst.tool_definition_id);

    const sortedToolDefs = Object.values(toolDefinitions).sort((a, b) => a.name.localeCompare(b.name));

    sortedToolDefs.forEach(toolDef => {
        if (toolDef.is_builtin) return;
        if (!installedToolIds.includes(toolDef.id)) {
            const option = document.createElement('option');
            option.value = toolDef.id;
            option.textContent = `${toolDef.display_name} (${toolDef.name})`;
            toolSelect.appendChild(option);
        }
    });
}


