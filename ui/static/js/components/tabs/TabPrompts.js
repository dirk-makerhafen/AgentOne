// This file manages the rendering and interactions for the Prompts list tab.

let promptItemTemplate;

function initializePromptTemplates() {
    promptItemTemplate = getTemplate('TabPromptsListItemTemplate');
    Handlebars.registerPartial('PromptListItemTemplate', promptItemTemplate);
}

function renderPromptList(prompts) {
    const promptsTableBody = document.getElementById('prompts-table-body');
    if (!promptsTableBody) return;

    promptsTableBody.innerHTML = ''; 

    if (!prompts || prompts.length === 0) {
        promptsTableBody.innerHTML = '<tr><td colspan="5"><p class="log-info">No prompt templates found.</p></td></tr>';
        return;
    }

    const systemPrompts = prompts.filter(p => p.owner_username === 'system');
    const userPrompts = prompts.filter(p => p.owner_username !== 'system');

    const userPromptsByParent = userPrompts.reduce((acc, prompt) => {
        const parentId = prompt.system_parent_id;
        if (parentId) {
            if (!acc[parentId]) {
                acc[parentId] = [];
            }
            acc[parentId].push(prompt);
        }
        return acc;
    }, {});
    
    const renderedUserPromptIds = new Set();

    systemPrompts.sort((a, b) => `${a.source}-${a.key}`.localeCompare(`${b.source}-${b.key}`));

    systemPrompts.forEach(sysPrompt => {
        promptsTableBody.insertAdjacentHTML('beforeend', promptItemTemplate(sysPrompt));
        if (userPromptsByParent[sysPrompt.id]) {
            const children = userPromptsByParent[sysPrompt.id];
            children.sort((a,b) => new Date(a.created_at) - new Date(b.created_at));
            children.forEach(userPrompt => {
                promptsTableBody.insertAdjacentHTML('beforeend', promptItemTemplate(userPrompt));
                renderedUserPromptIds.add(userPrompt.id);
            });
        }
    });

    const orphanUserPrompts = userPrompts.filter(p => !renderedUserPromptIds.has(p.id));
    orphanUserPrompts.sort((a, b) => `${a.source}-${a.key}`.localeCompare(`${b.source}-${b.key}`));
    orphanUserPrompts.forEach(userPrompt => {
        promptsTableBody.insertAdjacentHTML('beforeend', promptItemTemplate(userPrompt));
    });
    
    attachAllPromptEventListeners(promptsTableBody);
}

function renderSinglePrompt(prompt) {
    const promptsTableBody = document.getElementById('prompts-table-body');
    if (!promptsTableBody) return;

    const newHtml = promptItemTemplate(prompt);
    const tempContainer = document.createElement('tbody');
    tempContainer.innerHTML = newHtml;
    const newPromptRow = tempContainer.firstElementChild;
    const newPromptValueRow = tempContainer.lastElementChild;

    // Case 1: Replace a previous version
    if (prompt.prev_version_id) {
        const oldRow = document.getElementById(`prompt-row-${prompt.prev_version_id}`);
        const oldValueRow = document.getElementById(`prompt-value-row-${prompt.prev_version_id}`);
        if (oldRow && oldValueRow) {
            oldRow.replaceWith(newPromptRow);
            oldValueRow.replaceWith(newPromptValueRow);
            attachPromptEventListeners(newPromptRow);
            return;
        }
    }

    // Case 2: Insert a custom prompt below its system parent
    if (prompt.system_parent_id) {
        const parentValueRow = document.getElementById(`prompt-value-row-${prompt.system_parent_id}`);
        if (parentValueRow) {
            parentValueRow.insertAdjacentElement('afterend', newPromptRow);
            newPromptRow.insertAdjacentElement('afterend', newPromptValueRow);
            attachPromptEventListeners(newPromptRow);
            return;
        }
    }

    // Case 3: Fallback - append to the end
    promptsTableBody.appendChild(newPromptRow);
    promptsTableBody.appendChild(newPromptValueRow);
    attachPromptEventListeners(newPromptRow);
}

function attachAllPromptEventListeners(container) {
    container.querySelectorAll('.prompt-item-row').forEach(row => {
        attachPromptEventListeners(row);
    });
}

function attachPromptEventListeners(promptRow) {
    const promptPk = promptRow.dataset.promptPk;
    const valueRow = document.getElementById(`prompt-value-row-${promptPk}`);
    if (!valueRow) return;

    const editableElement = valueRow.querySelector('.prompt-value-content[contenteditable="true"]');
    if (editableElement) {
        const editActions = document.getElementById(`prompt-edit-actions-${promptPk}`);

        editableElement.addEventListener('focus', function() {
            if (editActions) {
                editActions.classList.remove('hidden');
                this.dataset.originalValue = this.textContent;
            }
        });

        editableElement.addEventListener('blur', function() {
            // Delay hiding to allow click events on save/cancel buttons
            setTimeout(() => {
                if (editActions && !editActions.contains(document.activeElement)) {
                    editActions.classList.add('hidden');
                }
            }, 150);
        });
    }
}


function createCustomPromptVersion(promptPk) {
    promptsApi.create(promptPk);
}

function savePromptChanges(promptPk) {
    const editableValue = document.getElementById(`prompt-value-editable-${promptPk}`);
    const editActions = document.getElementById(`prompt-edit-actions-${promptPk}`);

    if (editableValue && editActions) {
        const newValue = editableValue.textContent;
        const originalValue = editableValue.dataset.originalValue;

        if (newValue !== originalValue) {
            promptsApi.update(promptPk, newValue);
        }
        editableValue.blur();
        editActions.classList.add('hidden');
    }
}

function cancelPromptChanges(promptPk) {
    const editableValue = document.getElementById(`prompt-value-editable-${promptPk}`);
    const editActions = document.getElementById(`prompt-edit-actions-${promptPk}`);
    if (editableValue && editActions) {
        editableValue.textContent = editableValue.dataset.originalValue || editableValue.textContent;
        editableValue.blur();
        editActions.classList.add('hidden');
    }
}

function deletePrompt(promptPk, promptKey) {
    if (confirm(`Are you sure you want to delete your custom version of prompt "${promptKey}"?`)) {
        promptsApi.delete(promptPk);
    }
}

function togglePromptValueRow(clickedRow, pk, event) {
    if (event.target.closest('.prompt-actions button') || event.target.closest('[contenteditable="true"]')) {
        return; 
    }
    const valueRow = document.getElementById(`prompt-value-row-${pk}`);
    const icon = document.getElementById(`expand-icon-${pk}`);
    if (valueRow && icon) {
        valueRow.classList.toggle('hidden');
        icon.classList.toggle('fa-chevron-down');
        icon.classList.toggle('fa-chevron-up');
    }
};

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
    promptsApi.list();
}
