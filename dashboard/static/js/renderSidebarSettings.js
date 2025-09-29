const sidebarSettingsTemplate = Handlebars.compile(`
<div class="sidebar-settings-container">
    <h5>Instance Limits</h5>
    <div class="setting-item">
        <label for="limit-convo-input_{{id}}">Conversation History Limit:</label>
        <div class="editable-setting">
            <span class="editable-limit" id="limit-convo-text_{{id}}" onclick="showLimitEdit('convo', '{{id}}')">{{limit_max_conversation_messages}}</span>
            <i class="fa fa-pencil-square-o" onclick="showLimitEdit('convo', '{{id}}')"></i>
            <input type="number" id="limit-convo-input_{{id}}" value="{{limit_max_conversation_messages}}" style="display:none; width: 70px;" onkeydown="handleLimitKeydown(event, 'convo', '{{id}}')" onblur="saveLimit('convo', '{{id}}')"/>
        </div>
    </div>
    <div class="setting-item">
        <label for="limit-mem-input_{{id}}">Memory Items per Track/Layer:</label>
        <div class="editable-setting">
            <span class="editable-limit" id="limit-mem-text_{{id}}" onclick="showLimitEdit('mem', '{{id}}')">{{limit_max_memory_items}}</span>
            <i class="fa fa-pencil-square-o" onclick="showLimitEdit('mem', '{{id}}')"></i>
            <input type="number" id="limit-mem-input_{{id}}" value="{{limit_max_memory_items}}" style="display:none; width: 70px;" onkeydown="handleLimitKeydown(event, 'mem', '{{id}}')" onblur="saveLimit('mem', '{{id}}')"/>
        </div>
    </div>
    <div class="setting-item">
        <label for="limit-steps-input_{{id}}">Max Automatic Steps:</label>
        <div class="editable-setting">
            <span class="editable-limit" id="limit-steps-text_{{id}}" onclick="showLimitEdit('steps', '{{id}}')">{{limit_max_automated_steps}}</span>
            <i class="fa fa-pencil-square-o" onclick="showLimitEdit('steps', '{{id}}')"></i>
            <input type="number" id="limit-steps-input_{{id}}" value="{{limit_max_automated_steps}}" style="display:none; width: 70px;" onkeydown="handleLimitKeydown(event, 'steps', '{{id}}')" onblur="saveLimit('steps', '{{id}}')"/>
            <span class="current-step-count">(Current: {{automated_step_count}})</span>
        </div>
    </div>
    <h5>History Limiting Rules <i class="fa fa-info-circle" title="Override default tool history limits. Empty fields will revert to the tool's default value."></i></h5>
    {{#each history_limiting_rules as |toolRules toolName|}}
    <div class="tool-history-rules-group">
        <h6>{{toolName}}</h6>
        <div class="history-limits-grid">
            <div class="history-limits-header">Rule</div>
            <div class="history-limits-header"></div> <!-- Header for reset button -->
            <div class="history-limits-header">Success</div>
            <div class="history-limits-header">Failed</div>
            <div class="history-limits-header">Pending</div>
            <div class="history-limits-header">Total(max)</div>
            
            {{#each toolRules}}
            <div class="history-limit-rule-name" title="{{this.description}}">
                {{this.display_name}}
            </div>
            <div class="history-limit-actions">          
                <i class="fa fa-undo reset-limit-btn  {{#if this.db_id}}{{else}}hidden{{/if}}" title="Reset to default" onclick="resetHistoryLimit('{{this.full_rule_name}}', '{{../../id}}')"></i>   
            </div>
            <div><input type="number" class="history-limit-input {{#unless this.db_id}}is-default-limit{{/unless}}" value="{{this.success}}" placeholder="-" data-rule-full-name="{{this.full_rule_name}}" data-limit-type="success" onchange="handleHistoryLimitChange(event, '{{../../id}}')"></div>
            <div><input type="number" class="history-limit-input {{#unless this.db_id}}is-default-limit{{/unless}}" value="{{this.failed}}" placeholder="-" data-rule-full-name="{{this.full_rule_name}}" data-limit-type="failed" onchange="handleHistoryLimitChange(event, '{{../../id}}')"></div>
            <div><input type="number" class="history-limit-input {{#unless this.db_id}}is-default-limit{{/unless}}" value="{{this.pending}}" placeholder="-" data-rule-full-name="{{this.full_rule_name}}" data-limit-type="pending" onchange="handleHistoryLimitChange(event, '{{../../id}}')"></div>
            <div><input type="number" class="history-limit-input {{#unless this.db_id}}is-default-limit{{/unless}}" value="{{this.max}}" placeholder="-" data-rule-full-name="{{this.full_rule_name}}" data-limit-type="max" onchange="handleHistoryLimitChange(event, '{{../../id}}')"></div>
            {{/each}}
        </div>
    </div>
    {{/each}}
</div>`);

function renderSidebarSettings(instancePayload) {
    const instancePk = instancePayload.id;
    const container = document.getElementById(`sidebar-tab-settings_${instancePk}`);
    if (!container) {
        return;
    }

    // Helper to update text content of a limit, but only if its input is not currently visible.
    const updateLimitText = (limitType, newValue) => {
        const textSpan = document.getElementById(`limit-${limitType}-text_${instancePk}`);
        const input = document.getElementById(`limit-${limitType}-input_${instancePk}`);
        if (textSpan && input && input.style.display === 'none') {
            if (textSpan.textContent !== String(newValue)) {
                textSpan.textContent = String(newValue);
            }
        }
    };

    // If the container is empty, perform the initial full render.
    if (container.children.length === 0) {
        container.innerHTML = sidebarSettingsTemplate(instancePayload);
    } else {
        // Otherwise, perform a granular update.
        updateLimitText('convo', instancePayload.limit_max_conversation_messages);
        updateLimitText('mem', instancePayload.limit_max_memory_items);
        updateLimitText('steps', instancePayload.limit_max_automated_steps);

        const currentStepSpan = container.querySelector('.current-step-count');
        if (currentStepSpan) {
            currentStepSpan.textContent = `(Current: ${instancePayload.automated_step_count})`;
        }
        if (instancePayload.history_limiting_rules) {
            Object.values(instancePayload.history_limiting_rules).forEach(toolRules => {
                toolRules.forEach(rule => {
                    const ruleName = rule.full_rule_name;
                    ['success', 'failed', 'pending', 'max'].forEach(limitType => {
                        const input = container.querySelector(`input[data-rule-full-name="${ruleName}"][data-limit-type="${limitType}"]`);
                        // Only update if the input exists and is not the currently focused element.
                        if (input && document.activeElement !== input) {
                            const newValue = rule[limitType] !== null && rule[limitType] !== undefined ? rule[limitType] : '';
                            if (input.value != newValue) { // Use != to handle number/string comparison
                                input.value = newValue;
                            }
                            if (rule.db_id) {
                                input.classList.remove('is-default-limit');
                            } else {
                                input.classList.add('is-default-limit');
                            }
                        }
                    });
                     // Granularly update the visibility of the reset button.
                    const resetButton = container.querySelector(`i.reset-limit-btn[onclick*="'${ruleName}'"]`);
                    if (resetButton) {
                        if(rule.db_id){
                            resetButton.classList.remove("hidden")
                        }else{
                            resetButton.classList.add("hidden")
                        }
                    }
                });
            });
        }
    }
};


function showLimitEdit(limitType, instanceId) {
    // Hide all other open edits within the same instance to prevent clutter
    ['convo', 'mem', 'steps'].forEach(type => {
        if (type !== limitType) {
            cancelLimitEdit(type, instanceId);
        }
    });

    document.getElementById(`limit-${limitType}-text_${instanceId}`).style.display = 'none';
    document.querySelector(`#limit-${limitType}-text_${instanceId} + .fa-pencil-square-o`).style.display = 'none';
    
    const input = document.getElementById(`limit-${limitType}-input_${instanceId}`);
    input.style.display = 'inline-block';
    input.focus();
    input.select();
}

function cancelLimitEdit(limitType, instanceId) {
    const textEl = document.getElementById(`limit-${limitType}-text_${instanceId}`);
    const iconEl = document.querySelector(`#limit-${limitType}-text_${instanceId} + .fa-pencil-square-o`);
    const inputEl = document.getElementById(`limit-${limitType}-input_${instanceId}`);

    if (inputEl) inputEl.style.display = 'none';
    if (textEl) textEl.style.display = 'inline-block';
    if (iconEl) iconEl.style.display = 'inline-block';
}

function saveLimit(limitType, instanceId) {
    const input = document.getElementById(`limit-${limitType}-input_${instanceId}`);
    const textSpan = document.getElementById(`limit-${limitType}-text_${instanceId}`);
    const newValue = input.value;
    const oldValue = textSpan.textContent;

    // Hide the input and show the text span immediately to finalize the edit action.
    cancelLimitEdit(limitType, instanceId);

    if (!/^\d+$/.test(newValue)) {
        console.error("Invalid input. Limit must be a non-negative integer.");
        return;
    }
    
    const newIntValue = parseInt(newValue, 10);
    if (newIntValue == oldValue) {
        return;
    }

    textSpan.textContent = newIntValue;

    let dataKey;
    switch(limitType) {
        case 'convo': dataKey = 'limit_max_conversation_messages'; break;
        case 'mem': dataKey = 'limit_max_memory_items'; break;
        case 'steps': dataKey = 'limit_max_automated_steps'; break;
        default:
            console.error('Unknown limit type:', limitType);
            textSpan.textContent = oldValue;
            return;
    }

    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'update_instance_data',
            payload: {
                instance_pk: instanceId,
                data: { [dataKey]: newIntValue }
            }
        }));
    } else {
        console.error("WebSocket is not connected. Reverting UI change.");
        alert("Failed to save: Connection lost.");
        textSpan.textContent = oldValue;
    }
}

function handleLimitKeydown(event, limitType, instanceId) {
    if (event.key === 'Enter') {
        saveLimit(limitType, instanceId);
    } else if (event.key === 'Escape') {
        cancelLimitEdit(limitType, instanceId);
    }
}


// History limits
function handleHistoryLimitChange(event, instanceId) {
    const input = event.target;
    const ruleName = input.dataset.ruleFullName;
    const limitType = input.dataset.limitType;
    // An empty string means 'revert to default' on the backend
    const newValue = input.value.trim(); 
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'update_history_limit',
            payload: {
                instance_pk: instanceId,
                rule_name: ruleName,
                limits: {
                    [limitType]: newValue
                }
            }
        }));
    } else {
        console.error("WebSocket is not connected. Cannot save history limit change.");
        alert("Failed to save: Connection lost.");
        // The UI will be corrected on the next successful render.
    }
}

function resetHistoryLimit(ruleName, instanceId) {
    if (!confirm(`Are you sure you want to reset the rule '${ruleName}' to its default values?`)) {
        return;
    }

    //console.log("resetHistoryLimit - instanceId:", instanceId, "ruleName:", ruleName);
    //console.log("resetHistoryLimit - input element (if applicable):", event.target.outerHTML); // Add this for context

    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'reset_history_limit',
            payload: {
                instance_pk: instanceId,
                rule_name: ruleName
            }
        }));
    } else {
        console.error("WebSocket is not connected. Cannot reset history limit.");
        alert("Failed to reset: Connection lost.");
    }
}
