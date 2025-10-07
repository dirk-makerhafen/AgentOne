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
    const systemItemRowTemplate = getTemplate('TabSystemsListItemTemplate');
    const systemDetailsTemplate = getTemplate('TabSystemsDetailsTemplate');

    if (system && system.id) { window.systemCache[system.id] = system; }

    const existingItemRow = tableBody.querySelector(`tr.system-item[data-system-id="${system.id}"]`);
    let detailsAreVisible = false;
    let isEditing = false;

    if (existingItemRow) {
        const existingDetailsRow = existingItemRow.nextElementSibling;
        if (existingDetailsRow && existingDetailsRow.classList.contains('system-details-row')) {
            detailsAreVisible = !existingDetailsRow.classList.contains('hidden');
            isEditing = existingDetailsRow.querySelector('.system-details-edit') && existingDetailsRow.querySelector('.system-details-edit').style.display !== 'none';
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
        is_remote_executor_display: system.is_remote_executor ? 'Yes' : 'No',
        executor_api_key_display: system.executor_api_key ? '********' : 'N/A',
        osOptions: osOptionsData,
        executorModeOptions: executorModeOptionsData
    };

    const systemItemHtml = systemItemRowTemplate(systemData);
    const systemDetailsHtml = systemDetailsTemplate(systemData);
    
    const tempContainer = document.createElement('tbody');
    tempContainer.innerHTML = systemItemHtml + systemDetailsHtml;
    
    if (existingItemRow) {
        const existingDetailsRow = existingItemRow.nextElementSibling;
        existingItemRow.replaceWith(tempContainer.firstChild);
        if (existingDetailsRow && existingDetailsRow.classList.contains('system-details-row')) {
            existingDetailsRow.replaceWith(tempContainer.lastChild);
        }
    } else {
        tableBody.appendChild(tempContainer.firstChild);
        tableBody.appendChild(tempContainer.firstChild);
    }
}

function renderToolInstallationList(toolInstallations, systemId) {
    const toolInstallationItemTemplate = getTemplate('TabSystemsToolInstallationItemTemplate');
    const container = document.getElementById(`tool-installation-list-${systemId}`);
    if (!container) { 
        // Details row might be closed
        return; 
    }
    container.innerHTML = '';

    if (toolInstallations && toolInstallations.length > 0) {
        toolInstallations.forEach(installation => {
            const statusLower = installation.status.toLowerCase();
            const html = toolInstallationItemTemplate({
                ...installation,
                status: statusLower.replace(/_/g, '-'),
                status_display: installation.status.replace(/_/g, ' ').replace(/(?:^|\s)\S/g, a => a.toUpperCase()),
                can_start: statusLower === 'stopped' || statusLower === 'installed' || statusLower === 'error',
                can_stop: statusLower === 'running'
            });
            container.insertAdjacentHTML('beforeend', html);
        });
    } else {
        container.insertAdjacentHTML('beforeend', '<p class="no-installations-message">No tools installed on this system.</p>');
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
    
    requestSystemList();
    addToClientLog(`Client: Opened Systems tab.`, 'info');
}


// --- System Actions ---

function requestSystemList() {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: 'request_system_list' }));
    }
}

function systemCreate(event) {
    event.stopPropagation();
    const systemName = prompt("Enter a name for the new system:", "New System");
    if (systemName) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({ type: 'create_system', payload: { name: systemName } }));
            addToClientLog(`Client: Requesting creation of system "${systemName}".`, 'info');
        } else {
            addToClientLog("WebSocket not connected. Cannot create system.", 'error');
        }
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
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({ type: 'request_tool_installation_list', payload: { system_pk: systemId } }));
            addToClientLog(`Client: Requesting tool installation list for system ${systemId}.`, 'info');
        } else {
            addToClientLog("WebSocket not connected. Cannot fetch tool installations.", 'error');
        }
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
        is_remote_executor: editForm.querySelector('input[name="is_remote_executor"]').checked,
        executor_url: editForm.querySelector('input[name="executor_url"]').value,
        executor_api_key: editForm.querySelector('input[name="executor_api_key"]').value,
        os: editForm.querySelector('select[name="os"]').value,
        executor_mode: editForm.querySelector('select[name="executor_mode"]').value
    };
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: 'update_system_details', payload: { system_pk: systemId, data: data } }));
        addToClientLog(`Client: Requesting update for system ${systemId} details.`, 'info');
    } else {
        addToClientLog("WebSocket not connected. Cannot save system details.", 'error');
    }
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
    event.stopPropagation();
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

    if (!toolDefinitionId) { alert('Please select a Tool Definition.'); return; }
    if (!systemId) { alert('System ID is missing. This is an internal error.'); return; }

    const payload = { tool_definition_pk: toolDefinitionId, system_pk: systemId };
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: 'create_tool_installation', payload: payload }));
        addToClientLog(`Client: Requesting creation of tool installation for tool ${toolDefinitionId} on system ${systemId}.`, 'info');
    } else {
        addToClientLog("WebSocket not connected. Cannot save tool installation.", 'error');
    }
    toolInstallationCloseModal(event);
}

function toolInstallationStart(event, installationId) {
    event.stopPropagation();
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: 'tool_installation_start', payload: { installation_pk: installationId } }));
        addToClientLog(`Client: Requesting to start tool installation ${installationId}.`, 'info');
    } else {
        addToClientLog(`Cannot start installation. WebSocket is not connected.`, 'error');
    }
}

function toolInstallationStop(event, installationId) {
    event.stopPropagation();
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: 'tool_installation_stop', payload: { installation_pk: installationId } }));
        addToClientLog(`Client: Requesting to stop tool installation ${installationId}.`, 'info');
    } else {
        addToClientLog(`Cannot stop installation. WebSocket is not connected.`, 'error');
    }
}

function toolInstallationDelete(event, installationId, toolName) {
    event.stopPropagation();
    if (confirm(`Are you sure you want to uninstall "${toolName}"?`)) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({ type: 'delete_tool_installation', payload: { installation_pk: installationId } }));
            addToClientLog(`Client: Requesting deletion of tool installation ${installationId} ("${toolName}").`, 'info');
        } else {
            addToClientLog("Cannot delete installation. WebSocket is not connected.", 'error');
        }
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
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({ type: 'request_tool_installation_logs', payload: { installation_id: installationId } }));
            addToClientLog(`Client: Requesting logs for tool installation ${installationId}.`, 'info');
        } else {
            logsContainer.innerHTML = '<p class="log-message log-error">WebSocket is not connected.</p>';
            addToClientLog("WebSocket not connected. Cannot fetch logs.", 'error');
        }
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
