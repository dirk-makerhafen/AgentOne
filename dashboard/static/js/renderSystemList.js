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

const executorModeOptionTemplate = Handlebars.compile(`
    <option value="{{value}}" {{#if isSelected}}selected{{/if}}>{{text}}</option>
`);
Handlebars.registerPartial('executorModeOptionTemplate', executorModeOptionTemplate);

const systemDetailsTemplate = Handlebars.compile(`
    <tr class="system-details-row {{#if isHidden}}hidden{{/if}}">
        <td colspan="6">
            <div class="system-details-content">
                <!-- Display View -->
                <div class="system-details-display" style="display: {{#if isEditing}}none{{else}}block{{/if}};">
                    <p>Description: <b>{{description_display}}</b></p>
                    <p>Is Remote Executor: <b>{{is_remote_executor_display}}</b></p>
                    <p>Executor URL: <b>{{executor_url_display}}</b></p>
                    <p>Executor API Key: <b>{{executor_api_key_display}}</b></p>
                    <p>Executor Mode: <b>{{executor_mode_display}}</b></p>
                    <button class="btn btn-xs btn-info edit-system-btn" style="margin-top: 10px;">Edit</button>
                </div>

                <!-- Edit View -->
                <div class="system-details-edit" style="display: {{#if isEditing}}block{{else}}none{{/if}};">
                    <div class="form-group"><label>Description:</label><textarea class="form-control" name="description">{{description}}</textarea></div>
                    <div class="form-group"><label>Is Remote Executor:</label><input type="checkbox" name="is_remote_executor" {{#if is_remote_executor}}checked{{/if}}></div>
                    <div class="form-group"><label>Executor URL:</label><input type="url" class="form-control" name="executor_url" value="{{executor_url}}"></div>
                    <div class="form-group"><label>Executor API Key:</label><input type="text" class="form-control" name="executor_api_key" value="{{executor_api_key}}"></div>
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
        description_display: system.description || 'N/A',
        is_remote_executor_display: system.is_remote_executor ? 'Yes' : 'No',
        executor_api_key_display: system.executor_api_key ? '********' : 'N/A',
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

document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('tabContent_systems');
    if (!container) return;

    container.addEventListener('click', function(event) {
        const target = $(event.target);
        let systemItemRow = null;
        let systemDetailsRow = null;

        // If click is on a main system item row or its children (excluding details row children)
        if (target.closest('.system-item').length) {
            systemItemRow = target.closest('.system-item');
            systemDetailsRow = systemItemRow.next('.system-details-row');
        } 
        // If click is on an element within a system-details-row (like Edit, Save, Cancel)
        else if (target.closest('.system-details-row').length) {
            systemDetailsRow = target.closest('.system-details-row');
            systemItemRow = systemDetailsRow.prev('.system-item'); // Find the preceding main row
        } else {
            return; // Not relevant click
        }

        // Ensure both are found, if not, it's not a relevant click for system rows
        if (systemItemRow.length === 0 || systemDetailsRow.length === 0) {
            return;
        }

        const systemId = systemItemRow.data('system-id'); 

        // Edit button
        if (target.closest('.edit-system-btn').length) {
            systemDetailsRow.find('.system-details-display').hide();
            systemDetailsRow.find('.system-details-edit').show();
        }

        // Cancel button
        if (target.closest('.cancel-edit-system-btn').length) {
            systemDetailsRow.find('.system-details-edit').hide();
            systemDetailsRow.find('.system-details-display').show();
        }

        // Save button
        if (target.closest('.save-system-btn').length) {
            const editForm = systemDetailsRow.find('.system-details-edit');
            
            const data = {
                description: editForm.find('textarea[name="description"]').val(),
                is_remote_executor: editForm.find('input[name="is_remote_executor"]').is(':checked'),
                executor_url: editForm.find('input[name="executor_url"]').val(),
                executor_api_key: editForm.find('input[name="executor_api_key"]').val(),
                executor_mode: editForm.find('select[name="executor_mode"]').val()
            };
            
            if (websocket && websocket.readyState === WebSocket.OPEN) {
                websocket.send(JSON.stringify({
                    type: 'update_system_details',
                    payload: { system_pk: systemId, data: data }
                }));
            } else {
                alert('Cannot save. WebSocket not connected.');
            }
            editForm.hide();
            systemDetailsRow.find('.system-details-display').show();
        }
        
        // Deploy button - Disabled as it seems to be for SSH deployment
        if (target.closest('.deploy-system-btn').length) {
            alert('Deployment via this UI is currently disabled for remote executor systems. Please manage deployment via other means.');
        }

        // Toggle details button
        if (target.closest('.toggle-details-btn').length) {
            const icon = target.closest('.toggle-details-btn').find('i');
            const isHidden = systemDetailsRow.hasClass('hidden');
            systemDetailsRow.toggleClass('hidden');
            icon.removeClass(isHidden ? 'fa-chevron-down' : 'fa-chevron-up')
                .addClass(isHidden ? 'fa-chevron-up' : 'fa-chevron-down');
        }
    });
});
