// This file manages the rendering and interactions for the Prompts list tab.

// Assume getTemplate is provided globally by ui/static/js/core/utils.js
let promptItemTemplate;

function initializePromptTemplates() {
    promptItemTemplate = getTemplate('TabPromptsListItemTemplate');
}

function renderPromptList(prompts) {
    if (!promptItemTemplate) {
        initializePromptTemplates();
    }
    const promptsTableBody = document.getElementById('prompts-table-body');
    if (!promptsTableBody) {
        console.error("Prompts table body element not found.");
        return;
    }

    promptsTableBody.innerHTML = ''; // Clear existing content

    if (prompts.length === 0) {
        promptsTableBody.innerHTML = '<tr><td colspan="5"><p class="log-info">No prompt templates found.</p></td></tr>'; // Adjusted colspan
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

        editableElement.addEventListener('blur', function() {
            setTimeout(() => {
                if (editActions && !editActions.contains(document.activeElement)) {
                    editActions.classList.add('hidden');
                }
            }, 100); // Small delay to allow click event on buttons
        });
    });
}

function createCustomPromptVersion(promptPk) {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'create_custom_prompt_version',
            payload: {
                original_prompt_pk: promptPk
            }
        }));
        addToClientLog(`Client: Requesting custom version for prompt PK ${promptPk}`, 'info');
    } else {
        addToClientLog('WebSocket is not connected. Cannot create custom prompt version.', 'error');
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
                addToClientLog(`Client: Saving changes for prompt PK ${promptPk}`, 'info');
            } else {
                addToClientLog('WebSocket is not connected. Cannot save prompt changes.', 'error');
            }
        } else {
            addToClientLog(`Client: No changes detected for prompt PK ${promptPk}.`, 'info');
        }
        
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
        
        editableValue.blur();
        editActions.classList.add('hidden');
        addToClientLog(`Client: Canceled changes for prompt PK ${promptPk}.`, 'info');
    }
}

function deletePrompt(promptPk, promptKey) {
    if (confirm(`Are you sure you want to delete prompt "${promptKey}" (PK: ${promptPk}) and all its versions? This action cannot be undone.`)) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'delete_prompt',
                payload: {
                    prompt_pk: promptPk
                }
            }));
            addToClientLog(`Client: Requesting deletion for prompt PK ${promptPk}`, 'info');
        } else {
            addToClientLog('WebSocket is not connected. Cannot delete prompt.', 'error');
        }
    } else {
        addToClientLog(`Client: Deletion of prompt PK ${promptPk} canceled.`, 'info');
    }
}

function togglePromptValueRow(clickedRow, pk, event) {
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

// This function will be called by openMainTab when 'Prompts' tab is opened
function requestPromptList() {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: 'request_prompt_list', payload: {} }));
        addToClientLog("Client: Requesting prompt list.", 'info');
    } else {
        addToClientLog("WebSocket not connected. Cannot fetch prompt list.", 'error');
    }
}

function openPromptsTab(targetPanelId = 'mainTabPanel') {
    const tabContentId = 'tabContent_prompts';
    const tabName = 'Prompts';

    const existingTab = document.getElementById(tabContentId);
    if (existingTab) {
        openMainTab(null, tabContentId, targetPanelId);
    } else {
        initializePromptTemplates();
        const tabPromptsTemplate = getTemplate('TabPromptsTemplate');
        const tabContentHtml = tabPromptsTemplate({});
        openMainTab(null, tabContentId, targetPanelId, tabName, tabContentHtml);
    }
    requestPromptList();
}
