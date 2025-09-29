const sidebarPermissionsTemplate = Handlebars.compile(`
<div class="permissions-container" id="permissions-container_{{instancePk}}">
    <h4>Outbound Permissions</h4>
    <p class="text-muted"><small>Define which agents this instance can communicate with.</small></p>

    <div class="permission-search-container">
        <input type="text" id="permission-search-input_{{instancePk}}" onkeyup="filterAvailableInstances(this.value, {{instancePk}})" placeholder="Search agents to add to matrix...">
        <div id="permission-search-results_{{instancePk}}"></div>
    </div>

    <div class="permissions-matrix-container">
        {{#if outbound_permissions.length}}
        <table class="permissions-matrix" id="permissions-matrix-table_{{instancePk}}">
            <thead>
                <tr>
                    <th>Target Agent</th>
                    <th class="permission-checkbox-cell">Can Send</th>
                    <th class="permission-checkbox-cell">Can Receive</th>
                    <th class="actions-cell">Actions</th>
                </tr>
            </thead>
            <tbody>
                {{#each outbound_permissions}}
                <tr id="perm-row-{{this.target_instance_pk}}_{{../instancePk}}">
                    <td class="agent-name-cell">{{this.target_instance_name}}</td>
                    <td class="permission-checkbox-cell">
                        <input type="checkbox" data-target-pk="{{this.target_instance_pk}}" data-permission-type="can_send" {{#if this.can_send}}checked{{/if}} onchange="handlePermissionChange(this, {{../instancePk}})">
                    </td>
                    <td class="permission-checkbox-cell">
                        <input type="checkbox" data-target-pk="{{this.target_instance_pk}}" data-permission-type="can_receive" {{#if this.can_receive}}checked{{/if}} onchange="handlePermissionChange(this, {{../instancePk}})">
                    </td>
                    <td class="actions-cell">
                        <button class="remove-permission-btn" title="Remove from matrix" onclick="removeInstanceFromMatrix('{{this.target_instance_pk}}', {{../instancePk}})">
                            <i class="fa fa-trash-o"></i>
                        </button>
                    </td>
                </tr>
                {{/each}}
            </tbody>
        </table>
        {{else}}
            <div id="permissions-empty-state_{{instancePk}}" class="permissions-empty-state">
                <p>No outbound permissions configured.</p>
                <p><small>Use the search bar above to find and add agents to the matrix.</small></p>
            </div>
        {{/if}}
    </div>

    <hr class="permission-divider"/>

    <h4>Inbound Permissions</h4>
    <p class="text-muted"><small>Shows which agents have permission to communicate with this instance.</small></p>
    
    <div class="permissions-matrix-container">
        {{#if inbound_permissions.length}}
        <table class="permissions-matrix readonly">
            <thead>
                <tr>
                    <th>Source Agent</th>
                    <th class="permission-checkbox-cell">Can Send to Me</th>
                    <th class="permission-checkbox-cell">Can Receive from Me</th>
                </tr>
            </thead>
            <tbody>
                {{#each inbound_permissions}}
                <tr>
                    <td class="agent-name-cell">{{this.source_instance_name}}</td>
                    <td class="permission-checkbox-cell">
                        <i class="fa {{#if this.can_send}}fa-check-square-o text-success{{else}}fa-square-o{{/if}}"></i>
                    </td>
                    <td class="permission-checkbox-cell">
                         <i class="fa {{#if this.can_receive}}fa-check-square-o text-success{{else}}fa-square-o{{/if}}"></i>
                    </td>
                </tr>
                {{/each}}
            </tbody>
        </table>
        {{else}}
            <div class="permissions-empty-state">
                <p>No other agents have permissions configured for this instance.</p>
            </div>
        {{/if}}
    </div>
</div>`);

// Template for a single search result item
const searchResultItemTemplate = Handlebars.compile(`
    <div class="search-result-item">
        <div class="search-result-info">
            <div class="name">{{target_instance_name}}</div>
            <div class="description">{{target_instance_description || 'No description'}}</div>
        </div>
        <button class="add-permission-btn" onclick="addInstanceToMatrix({{target_instance_pk}}, {{instancePk}})">Add</button>
    </div>`);

// Template for a new row in the permissions matrix
const permissionMatrixRowTemplate = Handlebars.compile(`
    <tr id="perm-row-{{target_instance_pk}}_{{instancePk}}">
        <td class="agent-name-cell">{{target_instance_name}}</td>
        <td class="permission-checkbox-cell">
            <input type="checkbox" data-target-pk="{{target_instance_pk}}" data-permission-type="can_send" onchange="handlePermissionChange(this, {{instancePk}})">
        </td>
        <td class="permission-checkbox-cell">
            <input type="checkbox" data-target-pk="{{target_instance_pk}}" data-permission-type="can_receive" onchange="handlePermissionChange(this, {{instancePk}})">
        </td>
        <td class="actions-cell">
            <button class="remove-permission-btn" title="Remove from matrix" onclick="removeInstanceFromMatrix('{{target_instance_pk}}', {{instancePk}})">
                <i class="fa fa-trash-o"></i>
            </button>
        </td>
    </tr>`);



// Stores available instances per instancePk
const instanceAvailableInstancesMap = new Map(); 

function renderSidebarPermissions(payload) {
    const container = document.getElementById(`sidebar-tab-permissions_${payload.instance_pk}`);
    if (!container) {
        console.error(`Permissions container for instance ${payload.instance_pk} not found.`);
        return;
    }    
    instanceAvailableInstancesMap.set(payload.instance_pk, payload.all_available_instances || []);
    container.innerHTML = sidebarPermissionsTemplate({
        instancePk: payload.instance_pk,
        inbound_permissions:  payload.inbound_permissions,
        outbound_permissions: payload.outbound_permissions.filter(
            inst => inst.can_send === true || inst.can_receive === true
        )
    });
    
    // Hide the search results container initially, if it exists
    const searchResults = document.getElementById(`permission-search-results_${payload.instance_pk}`);
    if (searchResults) {
        searchResults.style.display = 'none';
    }
};

/**
 * Filters and displays available instances based on user input.
 */
function filterAvailableInstances(query, instancePk) {
    if (!instancePk) {
        console.error("filterAvailableInstances: instancePk is required.");
        return;
    }
    const permissionsContainer = document.getElementById(`permissions-container_${instancePk}`);
    if (!permissionsContainer) {
        console.error(`Permissions container for instance ${instancePk} not found.`);
        return;
    }
    const resultsContainer = permissionsContainer.querySelector(`#permission-search-results_${instancePk}`);
    const matrixTableBody = permissionsContainer.querySelector(`#permissions-matrix-table_${instancePk} tbody`);
    query = query.toLowerCase().trim();

    if (!query) {
        resultsContainer.innerHTML = '';
        resultsContainer.style.display = 'none';
        return;
    }

    const existingPks = new Set();
    if (matrixTableBody) {
        matrixTableBody.querySelectorAll('tr').forEach(row => {
            const idParts = row.id.split('_');
            // Assuming row ID format is `perm-row-{target_instance_pk}_{instancePk}`
            // We need the target_instance_pk part
            existingPks.add(idParts[1]); // Corrected index for target_instance_pk
        });
    }
    
    const availableInstancesForThisPk = instanceAvailableInstancesMap.get(instancePk) || [];

    const filtered = availableInstancesForThisPk.filter(inst => {
        const pkStr = String(inst.target_instance_pk);
        return (String(inst.target_instance_pk) !== String(instancePk)) && // Don't allow adding self
               !existingPks.has(pkStr) && // Don't add if already in matrix
               (inst.target_instance_name.toLowerCase().includes(query) ||
                (inst.target_instance_description || '').toLowerCase().includes(query) ||
                pkStr.includes(query));
    });

    if (filtered.length > 0) {
        let resultsHtml = '';
        filtered.forEach(inst => {
            resultsHtml += searchResultItemTemplate({
                target_instance_pk: inst.target_instance_pk,
                target_instance_name: inst.target_instance_name,
                target_instance_description: inst.target_instance_description,
                instancePk: instancePk // Pass the parent instancePk for context
            });
        });
        resultsContainer.innerHTML = resultsHtml;
        resultsContainer.style.display = 'block';
    } else {
        resultsContainer.innerHTML = '<div class="search-result-item"><div class="search-result-info">No matches found.</div></div>';
        resultsContainer.style.display = 'block';
    }
};

/**
 * Adds a selected instance to the permissions matrix.
 */
function addInstanceToMatrix(targetPk, instancePk) {
    if (!instancePk) {
        console.error("addInstanceToMatrix: instancePk is required.");
        return;
    }
    const availableInstancesForThisPk = instanceAvailableInstancesMap.get(instancePk) || [];
    const instanceData = availableInstancesForThisPk.find(inst => inst.target_instance_pk === targetPk);
    if (!instanceData) return;

    const permissionsContainer = document.getElementById(`permissions-container_${instancePk}`);
    if (!permissionsContainer) {
        console.error(`Permissions container for instance ${instancePk} not found.`);
        return;
    }

    const emptyState = permissionsContainer.querySelector(`#permissions-empty-state_${instancePk}`);
    if (emptyState) emptyState.style.display = 'none';
    
    let table = permissionsContainer.querySelector(`#permissions-matrix-table_${instancePk}`);
    if (!table) {
        const matrixContainer = permissionsContainer.querySelector('.permissions-matrix-container');
        if (matrixContainer) {
            matrixContainer.innerHTML = `
                <table class="permissions-matrix" id="permissions-matrix-table_${instancePk}">
                    <thead><tr><th>Agent</th><th class="permission-checkbox-cell">Can Send</th><th class="permission-checkbox-cell">Can Receive</th><th class="actions-cell">Actions</th></tr></thead>
                    <tbody></tbody>
                </table>`;
            table = permissionsContainer.querySelector(`#permissions-matrix-table_${instancePk}`);
        } else {
            console.error('Permissions matrix container not found.');
            return;
        }
    }
    const tableBody = table.querySelector('tbody');

    const newRowHtml = permissionMatrixRowTemplate({
        target_instance_pk: instanceData.target_instance_pk,
        target_instance_name: instanceData.target_instance_name,
        instancePk: instancePk // Pass the parent instancePk for context
    });
    tableBody.insertAdjacentHTML('beforeend', newRowHtml);

    const searchInput = permissionsContainer.querySelector(`#permission-search-input_${instancePk}`);
    const resultsContainer = permissionsContainer.querySelector(`#permission-search-results_${instancePk}`);
    if (searchInput) searchInput.value = '';
    if (resultsContainer) {
        resultsContainer.innerHTML = '';
        resultsContainer.style.display = 'none';
    }
};

/**
 * Removes an instance from the matrix and revokes all its permissions.
 */
function removeInstanceFromMatrix(targetPk, instancePk) {
    if (!instancePk) {
        console.error("removeInstanceFromMatrix: instancePk is required.");
        return;
    }
    const permissionsContainer = document.getElementById(`permissions-container_${instancePk}`);
    if (!permissionsContainer) {
        console.error(`Permissions container for instance ${instancePk} not found.`);
        return;
    }

    const row = permissionsContainer.querySelector(`#perm-row-${targetPk}_${instancePk}`);
    if (row) row.remove();

    const tableBody = permissionsContainer.querySelector(`#permissions-matrix-table_${instancePk} tbody`);
    if (tableBody && tableBody.rows.length === 0) {
        const emptyState = permissionsContainer.querySelector(`#permissions-empty-state_${instancePk}`);
        if (emptyState) emptyState.style.display = 'block';
    }

    // Send an update to revoke both permissions.
    sendPermissionUpdate(targetPk, 'can_send', false, instancePk);
    sendPermissionUpdate(targetPk, 'can_receive', false, instancePk);
};

/**
 * Handles the checkbox change event to grant or revoke a specific permission.
 */
function handlePermissionChange(checkbox, instancePk) {
    if (!instancePk) {
        console.error("handlePermissionChange: instancePk is required.");
        return;
    }
    const targetPk = checkbox.dataset.targetPk;
    const permissionType = checkbox.dataset.permissionType; // 'can_send' or 'can_receive'
    const isEnabled = checkbox.checked;
    sendPermissionUpdate(targetPk, permissionType, isEnabled, instancePk);
};

/**
 * Sends the specific permission update to the server.
 */
function sendPermissionUpdate(targetPk, permissionType, isEnabled, instancePk) {
    if (!instancePk) {
        console.error("sendPermissionUpdate: instancePk is required.");
        return;
    }
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        const payload = {
            instance_pk: instancePk,
            target_instance_pk: parseInt(targetPk, 10),
        };
        payload[permissionType] = isEnabled; // Dynamically set can_send or can_receive

        websocket.send(JSON.stringify({
            type: 'set_instance_permission',
            payload: payload
        }));
        addToConsoleArea(`Client: Updated permission for instance ${instancePk} to target ${targetPk}: ${permissionType} = ${isEnabled}.`, 'info');
    } else {
        addToConsoleArea("WebSocket is not connected. Cannot set permission.", 'error');
    }
}


