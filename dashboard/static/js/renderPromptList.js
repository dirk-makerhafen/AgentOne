const promptItemTemplate = Handlebars.compile(`
<tr class="prompt-item-row" id="prompt-row-{{id}}" data-prompt-pk="{{id}}" onclick="event.preventDefault(); togglePromptValueRow(this, '{{id}}', event)">
    <td {{#if is_editable}}style="margin-left: 15px;display: flex;"{{/if}}>
        {{#if is_editable}}<b>{{/if}}
            {{owner_username}}
        {{#if is_editable}}</b>{{/if}}
    </td>
    <td>{{source}}</td>
    <td>{{key}}</td>
    <td>{{version_count}}</td>
    <td>
        <div class="prompt-actions">
            {{#if is_deleteable}}
            <button class="btn btn-xs btn-default delete-prompt-btn" data-prompt-pk="{{id}}" title="Delete prompt" onclick="event.stopPropagation(); deletePrompt('{{id}}', '{{key}}')">
                <i class="fa fa-trash"></i>
            </button>
            {{/if}}
            {{#if is_editable}}

            {{else}}
            <button class="btn btn-xs btn-default create-custom-version-btn" data-prompt-pk="{{id}}" title="Create a custom, editable version of this system prompt" onclick="event.stopPropagation(); createCustomPromptVersion('{{id}}')">
                <i class="fa fa-copy"></i> Copy
            </button>
            {{/if}}
            <i class="fa fa-chevron-down expand-icon" id="expand-icon-{{id}}" title="Toggle details"></i>

        </div>
    </td>
</tr>
<tr class="prompt-value-row hidden" id="prompt-value-row-{{id}}">
    <td colspan="5"  {{#if is_editable}}style="padding-left: 20px;"{{/if}}>
        <div class="prompt-value-editor-container">
            <pre class="prompt-value-content" {{#if is_editable}}contenteditable="true"{{/if}} data-prompt-pk="{{id}}" id="prompt-value-editable-{{id}}">{{value}}</pre>
            {{#if is_editable}}
            <div class="prompt-edit-actions hidden" id="prompt-edit-actions-{{id}}">
                <button class="btn btn-primary btn-xs save-prompt-value-btn" data-prompt-pk="{{id}}" onclick="event.stopPropagation(); savePromptChanges('{{id}}')"><i class="fa fa-check"></i> Save</button>
                <button class="btn btn-secondary btn-xs cancel-prompt-value-btn" data-prompt-pk="{{id}}" onclick="event.stopPropagation(); cancelPromptChanges('{{id}}')"><i class="fa fa-times"></i> Cancel</button>
            </div>
            {{/if}}
        </div>
        <div class="prompt-meta">
            <span class="prompt-timestamps">Created: {{formatDateTime created_at}}</span>
        </div>
    </td>
</tr>`);

function renderPromptList(prompts) {
    const promptsTableBody = document.getElementById('prompts-table-body');
    if (!promptsTableBody) {
        console.error("Prompts table body element not found.");
        return;
    }

    promptsTableBody.innerHTML = ''; // Clear existing content

    if (prompts.length === 0) {
        promptsTableBody.innerHTML = '<tr><td colspan="4"><p class="log-info">No prompt templates found.</p></td></tr>';
        return;
    }

    // Sort prompts by source and then by key for consistent display
    prompts.sort((a, b) => {
        if (a.source < b.source) return -1;
        if (a.source > b.source) return 1;
        if (a.key < b.key) return -1;
        if (a.key > b.key) return 1;
        return 0;
    });

    prompts.forEach(prompt => {
        const promptHtml = promptItemTemplate(prompt);
        promptsTableBody.insertAdjacentHTML('beforeend', promptHtml);
    });

    // Attach event listeners for the contenteditable fields
    promptsTableBody.querySelectorAll('.prompt-value-content[contenteditable="true"]').forEach(editableElement => {
        const promptPk = editableElement.dataset.promptPk;
        const editActions = document.getElementById(`prompt-edit-actions-${promptPk}`);

        editableElement.addEventListener('focus', function() {
            if (editActions) {
                editActions.classList.remove('hidden');
                this.dataset.originalValue = this.textContent; // Store original value on focus
            }
        });

        // Use 'blur' to hide buttons if focus leaves without saving/canceling
        // This is tricky because clicking save/cancel also causes a blur.
        // We need to delay hiding to allow button clicks to register.
        editableElement.addEventListener('blur', function() {
            setTimeout(() => {
                if (editActions && !editActions.contains(document.activeElement)) {
                    // Only hide if the new active element is not within the action buttons
                    editActions.classList.add('hidden');
                    // If not saved, revert changes on blur if desired. For now, we only revert on explicit cancel.
                    // This could be a user preference: auto-save on blur vs. explicit save.
                }
            }, 100); // Small delay to allow click event on buttons
        });
    });

}


// Function to handle creating a custom prompt version (frontend part)
function createCustomPromptVersion(promptPk) {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'create_custom_prompt_version',
            payload: {
                original_prompt_pk: promptPk
            }
        }));
        addToConsoleArea(`Client: Requesting custom version for prompt PK ${promptPk}`, 'info');
    } else {
        addToConsoleArea('WebSocket is not connected. Cannot create custom prompt version.', 'error');
    }
}

function savePromptChanges(promptPk) {
    const editableValue = document.getElementById(`prompt-value-editable-${promptPk}`);
    const editActions = document.getElementById(`prompt-edit-actions-${promptPk}`);

    if (editableValue && editActions) {
        const newValue = editableValue.textContent;
        const originalValue = editableValue.dataset.originalValue;

        if (newValue !== originalValue) {
            if (websocket && websocket.readyState === WebSocket.OPEN) {
                websocket.send(JSON.stringify({
                    type: 'update_prompt',
                    payload: {
                        prompt_pk: promptPk,
                        value: newValue
                    }
                }));
                addToConsoleArea(`Client: Saving changes for prompt PK ${promptPk}`, 'info');
            } else {
                addToConsoleArea('WebSocket is not connected. Cannot save prompt changes.', 'error');
            }
        } else {
            addToConsoleArea(`Client: No changes detected for prompt PK ${promptPk}.`, 'info');
        }
        
        // Hide actions and remove focus regardless of whether changes were saved
        editableValue.blur();
        editActions.classList.add('hidden');
    }
}

function cancelPromptChanges(promptPk) {
    const editableValue = document.getElementById(`prompt-value-editable-${promptPk}`);
    const editActions = document.getElementById(`prompt-edit-actions-${promptPk}`);

    if (editableValue && editActions) {
        // Revert to original value
        editableValue.textContent = editableValue.dataset.originalValue || editableValue.textContent;
        
        // Hide actions and remove focus
        editableValue.blur();
        editActions.classList.add('hidden');
        addToConsoleArea(`Client: Canceled changes for prompt PK ${promptPk}.`, 'info');
    }
}

// Function to handle deleting a prompt (frontend part)
function deletePrompt(promptPk, promptKey) {
    if (confirm(`Are you sure you want to delete prompt "${promptKey}" (PK: ${promptPk}) and all its versions? This action cannot be undone.`)) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'delete_prompt',
                payload: {
                    prompt_pk: promptPk
                }
            }));
            addToConsoleArea(`Client: Requesting deletion for prompt PK ${promptPk}`, 'info');
        } else {
            addToConsoleArea('WebSocket is not connected. Cannot delete prompt.', 'error');
        }
    } else {
        addToConsoleArea(`Client: Deletion of prompt PK ${promptPk} canceled.`, 'info');
    }
}

function togglePromptValueRow(clickedRow, pk, event) {
    // Check if the click originated from an action button or contenteditable to prevent toggling
    if (event.target.closest('.prompt-actions button') || 
        event.target.closest('[contenteditable="true"]')) {
        return; 
    }

    const valueRow = document.getElementById(`prompt-value-row-${pk}`);
    const icon = document.getElementById(`expand-icon-${pk}`);

    if (valueRow && icon) {
        if (valueRow.classList.contains('hidden')) {
            valueRow.classList.remove('hidden');
            icon.classList.remove('fa-chevron-down');
            icon.classList.add('fa-chevron-up');
        } else {
            valueRow.classList.add('hidden');
            icon.classList.remove('fa-chevron-up');
            icon.classList.add('fa-chevron-down');
        }
    }
};
