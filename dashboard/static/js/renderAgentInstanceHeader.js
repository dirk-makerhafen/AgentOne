const agentInstanceHeaderTemplate = Handlebars.compile(`
<div class="instance-header-container">
    <div class="header-column">
        <div class="header-item"><i class="fa fa-user-circle header-icon" title="Agent"></i> <b>Agent:</b> <span class="header-value" id="instance-agent-name_{{message.id}}">{{message.agent_name}}</span></div>
                <div class="header-item instance-name-container" id="instance-name-container">
            <i class="fa fa-hashtag header-icon" title="Instance"></i> <b>Instance:</b>
            <span class="header-value instance-editable-name" contenteditable="true" onblur="handleInstanceNameEdit(this, '{{message.id}}')" data-original-value="{{message.name}}">
                {{#if message.name}}{{message.name}}{{else}}Unnamed Instance{{/if}}
            </span>
        </div>
        <div class="header-item" id="instance-model-container">
            <i class="fa fa-microchip header-icon" title="Model"></i> <b>Model:</b>
            <select id="instance-model-select_{{message.id}}" 
                    onchange="handleInstanceModelChange(this, '{{message.id}}')" 
                    onblur="handleInstanceModelChange(this, '{{message.id}}')" 
                    class="header-value edit-select">
                {{#each all_available_models}}
                    <option value="{{this.id}}" {{#if (eq this.id ../message.model_id)}}selected{{/if}}>{{this.name}}</option>
                {{/each}}
            </select>
        </div>
    </div>
    <div class="header-column">
                <div class="header-item" id="instance-autorun-container">
            <i class="fa fa-cogs header-icon" title="Auto-Run Steps"></i> <b>Auto-Run:</b>
            <span class="header-value" id="instance-autorun-count_{{message.id}}">{{message.automated_step_count}} / </span>
            <input type="number" 
                   id="limit-max-automated-steps-input_{{message.id}}" 
                   value="{{message.limit_max_automated_steps}}" 
                   onchange="handleAutoRunLimitChange(this, '{{message.id}}')" 
                   onblur="handleAutoRunLimitChange(this, '{{message.id}}')" 
                   class="edit-input"/>
        </div>
        <div class="header-item" id="instance-system-container">
            <i class="fa fa-server header-icon" title="System"></i> <b>System:</b>
            <select id="instance-system-select_{{message.id}}" 
                    onchange="handleInstanceSystemChange(this, '{{message.id}}')" 
                    onblur="handleInstanceSystemChange(this, '{{message.id}}')" 
                    class="header-value edit-select">
                {{#each all_available_systems}}
                    <option value="{{this.id}}" {{#if (eq this.id ../message.system_id)}}selected{{/if}}>{{this.name}}</option>
                {{/each}}
            </select>
        </div>
        <div class="header-item">
            <i class="fa fa-arrow-circle-o-up header-icon" title="Tokens Sent (Prompt)"></i> <span class="header-value" id="instance-tokens-sent_{{message.id}}">{{message.total_prompt_tokens}}</span>
            <i class="fa fa-arrow-circle-o-down header-icon" title="Tokens Received (Completion)" style="margin-left: 10px;"></i><span class="header-value" id="instance-tokens-received_{{message.id}}">{{message.total_completion_tokens}}</span>
        </div>
    </div>
    <div class="header-column">
        <div class="header-item full-width instance-description-container" id="instance-description-container">
            <div class="display-view instance-description-display-view">
                <span class="header-value instance-editable-description" contenteditable="true" onblur="handleInstanceDescriptionEdit(this, '{{message.id}}')" data-original-value="{{message.description}}">
                    {{#if message.description}}{{message.description}}{{else}}No description provided.{{/if}}
                    <span class="description-bottom-right">Description</span>
                </span>
            </div>
        </div>
    </div>
</div>`);

function renderAgentInstanceHeader(payload, instancePk) {
    const container = document.getElementById('agentInstanceHeader_' + instancePk);
    if (!container) {
        console.warn(`renderAgentInstanceHeader: Header container 'agentInstanceHeader_${instancePk}' not found.`);
        return;
    }

    // Helper to update text content of an element if it exists and value differs
    const updateText = (selector, newValue) => {
        const element = container.querySelector(selector);
        if (element && element.textContent !== String(newValue)) {
            element.textContent = newValue;
        }
    };

    // Helper to update input value if it exists and value differs
    const updateInputValue = (selector, newValue) => {
        const input = container.querySelector(selector);
        if (input && input.value !== String(newValue)) {
            input.value = newValue;
        }
    };

    // Helper to update select value and its options if changed
    const updateSelect = (selectId, newSelectedId, newOptionsList, type) => {
        const selectElement = document.getElementById(selectId);
        if (selectElement) {
            // Update selected value
            if (selectElement.value !== String(newSelectedId)) {
                selectElement.value = newSelectedId;
            }

            // Check if options list needs to be updated
            const currentOptions = Array.from(selectElement.options).map(opt => ({
                id: opt.value,
                name: opt.textContent
            }));
            const newOptions = newOptionsList.map(opt => ({
                id: String(opt.id), // Ensure string comparison
                name: opt.name
            }));
            
            // Simple comparison: check length and if all items match in order
            let optionsChanged = false;
            if (currentOptions.length !== newOptions.length) {
                optionsChanged = true;
            } else {
                for (let i = 0; i < currentOptions.length; i++) {
                    if (currentOptions[i].id !== newOptions[i].id || currentOptions[i].name !== newOptions[i].name) {
                        optionsChanged = true;
                        break;
                    }
                }
            }

            if (optionsChanged) {
                // If options changed, regenerate the select innerHTML
                let optionsHtml = '';
                newOptionsList.forEach(option => {
                    optionsHtml += `<option value="${option.id}" ${String(option.id) === String(newSelectedId) ? 'selected' : ''}>${option.name}</option>`;
                });
                selectElement.innerHTML = optionsHtml;
            }
        }
    };


    if (container.children.length === 0) {
        // Initial render: Container is empty, so render the full template
        container.innerHTML = agentInstanceHeaderTemplate({"message": payload, "all_available_models":window.allAvailableModels || [], "all_available_systems": window.allAvailableSystems || [] });
        //console.log(`renderAgentInstanceHeader: Initial render for instance ${instancePk}.`);
    } else {
        // Subsequent update: Container already has content, perform granular updates

        // Agent Name (Static span)
        updateText(`#instance-agent-name_${instancePk}`, payload.agent_name);

        // Instance Name (Contenteditable span) - Only update if not currently editing
        const instanceNameSpan = container.querySelector('#instance-name-container .instance-editable-name');
        if (instanceNameSpan && document.activeElement !== instanceNameSpan) {
            let newName = payload.name || 'Unnamed Instance';
            if (instanceNameSpan.textContent !== newName) {
                // Temporarily remove description label if present, update text, then re-add
                const nameLabel = instanceNameSpan.querySelector('.name-bottom-right'); // Assuming there might be a similar label
                if (nameLabel) nameLabel.remove();
                instanceNameSpan.textContent = newName;
                if (payload.name) { // Only add label back if there's actual content
                    if (!nameLabel) { // If label was removed or not present, re-create if needed
                        // Not sure what the name label is or if it needs to be put back.
                        // The template doesn't seem to have one for the instance name.
                    }
                }
            }
        }

        updateSelect(`instance-model-select_${instancePk}`, payload.model_id,  window.allAvailableModels || [], 'model');

        // Auto-Run Steps Count (Span)
        updateText(`#instance-autorun-count_${instancePk}`, `${payload.automated_step_count} / `);

        // Auto-Run Limit (Input number)
        updateInputValue(`#limit-max-automated-steps-input_${instancePk}`, payload.limit_max_automated_steps);

        // System Select
        updateSelect(`instance-system-select_${instancePk}`, payload.system_id, window.allAvailableSystems || [], 'system');

        // Tokens Sent (Span)
        updateText(`#instance-tokens-sent_${instancePk}`, payload.total_prompt_tokens);

        // Tokens Received (Span)
        updateText(`#instance-tokens-received_${instancePk}`, payload.total_completion_tokens);

        // Instance Description (Contenteditable span) - Only update if not currently editing
        const instanceDescriptionSpan = container.querySelector('#instance-description-container .instance-editable-description');
        if (instanceDescriptionSpan && document.activeElement !== instanceDescriptionSpan) {
            let newDescription = payload.description || 'No description provided.';
            if (instanceDescriptionSpan.textContent.trim() !== newDescription.trim()) {
                // Preserve the "Description" bottom-right label
                const descriptionLabel = instanceDescriptionSpan.querySelector('.description-bottom-right');
                if (descriptionLabel) descriptionLabel.remove(); // Remove to update text content easily
                instanceDescriptionSpan.textContent = newDescription;
                if (payload.description && !descriptionLabel) { // Only add label back if there's actual content and it was missing
                    const newLabel = document.createElement('span');
                    newLabel.className = 'description-bottom-right';
                    newLabel.textContent = 'Description';
                    instanceDescriptionSpan.appendChild(newLabel);
                } else if (descriptionLabel) { // Re-add existing label if it was present
                    instanceDescriptionSpan.appendChild(descriptionLabel);
                }
            }
        }
        //console.log(`renderAgentInstanceHeader: Granularly updated header for instance ${instancePk}.`);
    }

    //console.log(`renderAgentInstanceHeader: Granularly updated header for instance ${instancePk}.`);
}





function handleInstanceDescriptionEdit(element, instanceId) {
    // Clone the element to safely remove the helper span before extracting text
    const clone = element.cloneNode(true);
    const descriptionLabel = clone.querySelector('.description-bottom-right');
    if (descriptionLabel) {
        descriptionLabel.remove();
    }
    const newValue = clone.textContent.trim();
    const originalValue = element.dataset.originalValue || '';
    
    // If the new value is the placeholder, treat it as empty
    if (newValue === 'Unnamed Instance') {
        newValue = '';
    }

    // Only send update if the value has actually changed
    if (newValue !== originalValue) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'update_instance_data',
                payload: {
                    instance_pk: instanceId,
                    data: { description: newValue }
                }
            }));
            // Update the original value after successful send
            element.dataset.originalValue = newValue;
        } else {
            addToConsoleArea('WebSocket is not connected. Changes may not be saved.', 'error');
            // Revert to original value if WebSocket is not open
            element.textContent = originalValue;
        }
    }
}

function handleAutoRunLimitChange(inputElement, instanceId) {
    const newValue = parseInt(inputElement.value, 10);
    const originalValue = parseInt(inputElement.dataset.originalValue, 10); // Assume original value is stored, or fetch if needed

    if (isNaN(newValue) || newValue < 0) {
        addToConsoleArea('Invalid input for Auto-Run Steps. Must be a non-negative number.', 'error');
        // Optionally revert the input field to its original valid value
        inputElement.value = originalValue;
        return;
    }

    if (newValue !== originalValue) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'update_instance_data',
                payload: {
                    instance_pk: instanceId,
                    data: { limit_max_automated_steps: newValue }
                }
            }));
            // Update the data-original-value for consistency after sending the update
            inputElement.dataset.originalValue = newValue;
            addToConsoleArea(`Client: Auto-Run limit updated to ${newValue} for instance ${instanceId}.`, 'info');
        } else {
            addToConsoleArea('WebSocket is not connected. Auto-Run limit not saved.', 'error');
            // Revert the input field if WebSocket is not open
            inputElement.value = originalValue;
        }
    }
}

function handleInstanceModelChange(selectElement, instanceId) {
    const newModelId = selectElement.value;
    const originalModelId = selectElement.dataset.originalValue; // Assuming original value is stored
    
    if (newModelId !== originalModelId) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'update_instance_data',
                payload: {
                    instance_pk: instanceId,
                    data: { model_id: newModelId }
                }
            }));
            selectElement.dataset.originalValue = newModelId; // Update original value
            addToConsoleArea(`Client: Model updated to ${newModelId} for instance ${instanceId}.`, 'info');
        } else {
            addToConsoleArea('WebSocket is not connected. Model not saved.', 'error');
            // Revert the select field if WebSocket is not open
            selectElement.value = originalModelId;
        }
    }
}

function handleInstanceSystemChange(selectElement, instanceId) {
    const newSystemId = selectElement.value;
    const originalSystemId = selectElement.dataset.originalValue; // Assuming original value is stored

    if (newSystemId !== originalSystemId) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'update_instance_data',
                payload: {
                    instance_pk: instanceId,
                    data: { system_id: newSystemId }
                }
            }));
            selectElement.dataset.originalValue = newSystemId; // Update original value
            addToConsoleArea(`Client: System updated to ${newSystemId} for instance ${instanceId}.`, 'info');
        } else {
            addToConsoleArea('WebSocket is not connected. System not saved.', 'error');
            // Revert the select field if WebSocket is not open
            selectElement.value = originalSystemId;
        }
    }
}

function handleInstanceNameEdit(element, instanceId) {
    // Clone the element to safely remove the helper span before extracting text
    const clone = element.cloneNode(true);
    const nameLabel = clone.querySelector('.name-bottom-right');
    if (nameLabel) {
        nameLabel.remove();
    }
    let newValue = clone.textContent.trim(); // Use let for reassignment
    const originalValue = element.dataset.originalValue || '';
    
    // If the new value is the placeholder, treat it as empty
    if (newValue === 'Unnamed Instance') {
        newValue = '';
    }

    // Only send update if the value has actually changed
    if (newValue !== originalValue) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'update_instance_data',
                payload: {
                    instance_pk: instanceId,
                    data: { name: newValue }
                }
            }));
            // Update the original value after successful send
            element.dataset.originalValue = newValue;
        } else {
            addToConsoleArea('WebSocket is not connected. Changes may not be saved.', 'error');
            // Revert to original value if WebSocket is not open
            element.textContent = originalValue;
        }
    }
}
