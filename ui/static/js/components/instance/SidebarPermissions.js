// This file manages the rendering and interactions for the Permissions sidebar.
// Assume getTemplate is provided globally by ui/static/js/core/utils.js

const instanceAvailableInstancesMap = new Map(); 

function renderSidebarPermissions(payload) {
    const sidebarPermissionsTemplate = getTemplate('SidebarPermissionsTemplate');
    const container = document.getElementById(`sidebar-tab-permissions_${payload.instancePk}`);
    if (container) {
        instanceAvailableInstancesMap.set(payload.instancePk, payload.available_instances);
        container.innerHTML = sidebarPermissionsTemplate(payload);
    }
};

function filterAvailableInstances(query, instancePk) {
    const searchResultItemTemplate = getTemplate('SearchResultItemTemplate');
    const resultsContainer = document.getElementById(`permission-search-results_${instancePk}`);
    const available = instanceAvailableInstancesMap.get(instancePk) || [];
    resultsContainer.innerHTML = '';
    if (query.trim() === '') return;

    const filtered = available.filter(inst => inst.target_instance_name.toLowerCase().includes(query.toLowerCase()));
    filtered.forEach(inst => {
        resultsContainer.insertAdjacentHTML('beforeend', searchResultItemTemplate({...inst, instancePk}));
    });
}

function addInstanceToMatrix(targetPk, instancePk) {
    const permissionMatrixRowTemplate = getTemplate('PermissionMatrixRowTemplate');
    const available = instanceAvailableInstancesMap.get(instancePk) || [];
    const instanceToAdd = available.find(inst => inst.target_instance_pk === targetPk);
    
    document.getElementById(`permission-search-results_${instancePk}`).innerHTML = '';
    document.getElementById(`permission-search-input_${instancePk}`).value = '';
    
    // Hide empty state message if it exists
    const emptyState = document.getElementById(`permissions-empty-state_${instancePk}`);
    if (emptyState) {
        emptyState.style.display = 'none';
    }
    
    const tableBody = document.querySelector(`#permissions-matrix-table_${instancePk} tbody`);
    if (tableBody) {
        tableBody.insertAdjacentHTML('beforeend', permissionMatrixRowTemplate({...instanceToAdd, instancePk}));
    }
}

function removeInstanceFromMatrix(targetPk, instancePk) {
    const rowToRemove = document.getElementById(`perm-row-${targetPk}_${instancePk}`);
    if (rowToRemove) {
        rowToRemove.remove();
        sendPermissionUpdate(targetPk, 'revoke_all', false, instancePk); // Revoke all permissions on removal

        // If no rows remain, show empty state
        const tableBody = document.querySelector(`#permissions-matrix-table_${instancePk} tbody`);
        if (tableBody && tableBody.children.length === 0) {
            const emptyState = document.getElementById(`permissions-empty-state_${instancePk}`);
            if (emptyState) {
                emptyState.style.display = 'block';
            }
        }
    }
}

function handlePermissionChange(checkbox, instancePk) {
    const targetPk = checkbox.dataset.targetPk;
    const permissionType = checkbox.dataset.permissionType;
    const isEnabled = checkbox.checked;
    sendPermissionUpdate(targetPk, permissionType, isEnabled, instancePk);
}

function sendPermissionUpdate(targetPk, permissionType, isEnabled, instancePk) {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'update_instance_permission',
            payload: {
                instance_pk: instancePk,
                target_instance_pk: targetPk,
                permission_type: permissionType,
                enabled: isEnabled
            }
        }));
        addToClientLog(`Client: Updated permission ${permissionType} for target ${targetPk} to ${isEnabled} for instance ${instancePk}`, 'info', null, instancePk);
    } else {
        addToClientLog("WebSocket not connected. Cannot update permission.", 'error', null, instancePk);
    }
}

// Function to update the UI based on a single permission update from WebSocket
function updatePermissionCardUI(payload) {
    // Only update if the message is for the currently viewed instance
    if (window.currentAgentInstancePk && window.currentAgentInstancePk === payload.instance_pk) {
        const checkbox = document.querySelector(
            `#perm-row-${payload.target_instance_pk}_${payload.instance_pk} ` +
            `input[data-permission-type="${payload.permission_type}"]`
        );
        if (checkbox) {
            checkbox.checked = payload.enabled;
            addToClientLog(`UI updated for permission ${payload.permission_type} to ${payload.enabled} for target ${payload.target_instance_pk}`, 'client-status', null, payload.instance_pk);
        } else {
            // This might happen if a permission is granted for a target not yet in the matrix
            // In a more robust system, we would re-render the row or add it if missing
            // For now, log a warning
            addToClientLog(`Warning: Received permission update for missing checkbox: target ${payload.target_instance_pk}, type ${payload.permission_type}`, 'warning', null, payload.instance_pk);
        }
    }
}