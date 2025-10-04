// renderToolDefinitionList.js

var toolDefinitionListTemplate = `
    {{#each this}}
        <div class="tool-definition-item" data-id="{{this.id}}">
            <div class="tool-definition-header">
                <span class="tool-definition-name">{{this.display_name}}</span>
                <span class="tool-definition-type">{{#if this.is_builtin}}Built-in{{else}}External MCP{{/if}}</span>
                <div class="tool-definition-actions">
                    <button class="btn btn-xs btn-default edit-tool-definition-btn" title="Edit Tool Definition" data-id="{{this.id}}">
                        <i class="fa fa-pencil"></i>
                    </button>
                    <button class="btn btn-xs btn-danger delete-tool-definition-btn" title="Delete Tool Definition" data-id="{{this.id}}">
                        <i class="fa fa-trash"></i>
                    </button>
                </div>
            </div>
            <div class="tool-definition-details">
                <p><strong>Name (Internal):</strong> {{this.name}}</p>
                <p><strong>Description:</strong> {{this.description}}</p>
                {{#if this.repository_url}}
                    <p><strong>Repository:</strong> <a href="{{this.repository_url}}" target="_blank">{{this.repository_url}}</a></p>
                {{/if}}
                {{#with this.manifest}}
                    {{#if this.server.mcp_config.transport_type}}
                        <p><strong>Transport:</strong> <span class="transport-type-{{this.server.mcp_config.transport_type}}">{{this.server.mcp_config.transport_type}}</span></p>
                    {{/if}}
                    {{#if this.command}}
                        <p><strong>Command:</strong> <code>{{this.command}}</code></p>
                    {{/if}}
                    {{#if this.args}}
                        <p><strong>Args:</strong> <code>{{jsonStringify this.args}}</code></p>
                    {{/if}}
                    {{#if this.platforms}}
                        <p><strong>Platforms:</strong> {{join this.platforms ", "}}</p>
                    {{/if}}
                {{/with}}
                {{#if this.is_builtin}}
                    <p>This is a built-in tool and cannot be uninstalled or modified directly here.</p>
                {{else}}
                    <!-- Placeholder for installation status and actions -->
                {{/if}}
            </div>
        </div>
    {{/each}}
`;

// Register Handlebars helpers
Handlebars.registerHelper('jsonStringify', function(obj) {
    return JSON.stringify(obj);
});
Handlebars.registerHelper('join', function(arr, separator) {
    return arr.join(separator);
});

var compiledToolDefinitionListTemplate = Handlebars.compile(toolDefinitionListTemplate);

function renderToolDefinitionList(toolDefinitions) {
    console.log("renderToolDefinitionList called with data:", toolDefinitions); // Debug log
    const toolRegistryListBody = $('#tool-registry-list-body');
    
    if (!toolDefinitions) {
        console.error("renderToolDefinitionList: Invalid data received.", toolDefinitions);
        toolRegistryListBody.html('<p>Error: Could not load tool definitions.</p>');
        return;
    }

    try {
        toolRegistryListBody.html(compiledToolDefinitionListTemplate(toolDefinitions));
        console.log("Tool definitions rendered successfully.");
    } catch (e) {
        console.error("Error rendering tool definitions with Handlebars:", e, toolDefinitions);
        toolRegistryListBody.html('<p>Error rendering tool definitions.</p>');
    }

    toolRegistryListBody.find('.edit-tool-definition-btn').on('click', function() {
        const toolDefId = $(this).data('id');
        openEditToolDefinitionModal(toolDefId);
    });

    toolRegistryListBody.find('.delete-tool-definition-btn').on('click', function() {
        const toolDefId = $(this).data('id');
        confirmDeleteToolDefinition(toolDefId);
    });
}

function openAddToolDefinitionModal() {
    $('#addToolDefinitionForm')[0].reset();
    $('.external-tool-fields').show(); // Show fields for external tools by default for add
    $('#addToolDefinitionIsBuiltin').prop('checked', false).prop('disabled', true); // Default to external, built-in disabled
    $('#addToolDefinitionDisplayName').val(''); // Clear display name
    $('#saveToolDefinitionBtn').off('click').on('click', function() {
        saveToolDefinition();
    });
    $('#addToolDefinitionModal').show();
}

function openEditToolDefinitionModal(toolDefId) {
    const toolDefinition = window.allToolDefinitions[toolDefId];
    if (!toolDefinition) {
        addToConsoleArea('Tool Definition not found in cache for editing: ' + toolDefId, 'error');
        return;
    }

    $('#editToolDefinitionId').val(toolDefinition.id);
    $('#editToolDefinitionName').val(toolDefinition.name);
    $('#editToolDefinitionDisplayName').val(toolDefinition.display_name); // Populate display name
    $('#editToolDefinitionDescription').val(toolDefinition.description);
    $('#editToolDefinitionIsBuiltin').prop('checked', toolDefinition.is_builtin).prop('disabled', true); // Built-in disabled for edit
    $('#editToolDefinitionTransportType').val(toolDefinition.transport_type || 'tcp'); // Populate transport type

    if (toolDefinition.is_builtin) {
        $('.external-tool-fields').hide();
        // Clear manifest-related fields for built-in tools
        $('#editToolDefinitionRepoUrl').val('');
        $('#editToolDefinitionCommand').val('');
        $('#editToolDefinitionArgs').val('');
        $('#editToolDefinitionPlatforms').val('');
    } else {
        $('.external-tool-fields').show();
        $('#editToolDefinitionRepoUrl').val(toolDefinition.repository_url || '');
        // Populate manifest fields
        if (toolDefinition.manifest) {
            $('#editToolDefinitionCommand').val(toolDefinition.manifest.command || '');
            // Convert array to JSON string for args input field
            $('#editToolDefinitionArgs').val(toolDefinition.manifest.args ? JSON.stringify(toolDefinition.manifest.args) : '');
            // Join array with comma for platforms input field
            $('#editToolDefinitionPlatforms').val(toolDefinition.manifest.platforms ? toolDefinition.manifest.platforms.join(', ') : '');
        } else {
            // Clear if no manifest
            $('#editToolDefinitionCommand').val('');
            $('#editToolDefinitionArgs').val('');
            $('#editToolDefinitionPlatforms').val('');
        }
    }

    $('#updateToolDefinitionBtn').off('click').on('click', function() {
        updateToolDefinition();
    });
    $('#editToolDefinitionModal').show();
}

function closeToolDefinitionModal() {
    $('#addToolDefinitionModal').hide();
    $('#editToolDefinitionModal').hide();
}

function saveToolDefinition() {
    const display_name = $('#addToolDefinitionDisplayName').val();
    const name = $('#addToolDefinitionName').val();
    const description = $('#addToolDefinitionDescription').val();
    const is_builtin = $('#addToolDefinitionIsBuiltin').prop('checked');
    const repository_url = $('#addToolDefinitionRepoUrl').val();
    const command = $('#addToolDefinitionCommand').val();
    let args = $('#addToolDefinitionArgs').val();
    const platforms = $('#addToolDefinitionPlatforms').val();

    if (!display_name) {
        alert('Display Name is required.');
        return;
    }
    if (!name) {
        alert('Internal Name is required.');
        return;
    }

    // Attempt to parse args if not empty
    if (args) {
        try {
            JSON.parse(args);
        } catch (e) {
            alert('Arguments must be valid JSON (e.g., ["--port", "8080"]).');
            return;
        }
    }

    websocket.send(JSON.stringify({
        'type': 'create_tool_definition',
        'payload': { // Wrap data in 'payload' object
            'display_name': display_name,
            'name': name,
            'description': description,
            'is_builtin': is_builtin,
            'transport_type': $('#addToolDefinitionTransportType').val(), // Get value from new dropdown
            'repository_url': repository_url,
            'command': command,
            'args': args, // Send as string, backend will parse
            'platforms': platforms
        }
    }));
    closeToolDefinitionModal();
}

function updateToolDefinition() {
    const id = $('#editToolDefinitionId').val();
    const display_name = $('#editToolDefinitionDisplayName').val();
    const name = $('#editToolDefinitionName').val();
    const description = $('#editToolDefinitionDescription').val();
    const repository_url = $('#editToolDefinitionRepoUrl').val();
    const command = $('#editToolDefinitionCommand').val();
    let args = $('#editToolDefinitionArgs').val();
    const platforms = $('#editToolDefinitionPlatforms').val();

    if (!display_name) {
        alert('Display Name is required.');
        return;
    }
    if (!name) {
        alert('Internal Name is required.');
        return;
    }

    // Attempt to parse args if not empty
    if (args) {
        try {
            JSON.parse(args);
        } catch (e) {
            alert('Arguments must be valid JSON (e.g., ["--port", "8080"]).');
            return;
        }
    }

    websocket.send(JSON.stringify({
        'type': 'update_tool_definition',
        'payload': { // Wrap data in 'payload' object
            'id': id,
            'display_name': display_name,
            'name': name,
            'description': description,
            'transport_type': $('#editToolDefinitionTransportType').val(), // Get value from new dropdown
            'repository_url': repository_url,
            'command': command,
            'args': args, // Send as string, backend will parse
            'platforms': platforms
        }
    }));
    closeToolDefinitionModal();
}

function confirmDeleteToolDefinition(toolDefId) {
    const toolDefinition = window.allToolDefinitions[toolDefId];
    if (!toolDefinition) {
        addToConsoleArea('Tool Definition not found in cache for deletion: ' + toolDefId, 'error');
        return;
    }
    if (confirm(`Are you sure you want to delete tool definition "${toolDefinition.name}"? This cannot be undone.`)) {
        websocket.send(JSON.stringify({
            'type': 'delete_tool_definition',
            'id': toolDefId
        }));
    }
}

$(document).ready(function() {
    $('#add-tool-definition-btn').on('click', function() {
        openAddToolDefinitionModal();
    });
});

