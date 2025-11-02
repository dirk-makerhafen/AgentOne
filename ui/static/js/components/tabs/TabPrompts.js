// This file manages the rendering and interactions for the hierarchical Prompts tab.

let templates = {};
Handlebars.registerPartial('PromptVariantRowTemplate', document.getElementById('PromptVariantRowTemplate').innerHTML);

function initializePromptTemplates() {
    templates.definitionRow = getTemplate('PromptDefinitionRowTemplate');
    templates.variantGroupRow = getTemplate('PromptVariantGroupRowTemplate');
    // The PromptVariantRowTemplate is already registered as a partial
}

function renderPromptList(promptDefinitions) {
    const tableBody = document.getElementById('prompts-table-body');
    if (!tableBody) return;

    tableBody.innerHTML = ''; // Clear existing content

    if (!promptDefinitions || promptDefinitions.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="5"><p class="log-info">No prompt templates found.</p></td></tr>';
        return;
    }
    
    promptDefinitions.forEach(definition => {
        tableBody.insertAdjacentHTML('beforeend', templates.definitionRow(definition));
    });
}

function renderPromptVariants(payload) {
    const groupRow = document.querySelector(`.prompt-variant-group-row[data-parent-definition-id="${payload.prompt_pk}"]`);
    if (!groupRow) return;
    // Render both groups into the container
    const container = groupRow.querySelector('.variant-group-container');
    container.innerHTML = templates.variantGroupRow({
        prompt_definition_id: payload.prompt_pk,
        variants: payload.variants,
        no_variants_message: "No variants for this prompt."
    });
}


// --- Event Handlers ---

function togglePromptDefinition(rowElement) {
    const promptId = rowElement.dataset.promptDefinitionId;
    const variantRow = document.querySelector(`.prompt-variant-group-row[data-parent-definition-id="${promptId}"]`);
    const icon = rowElement.querySelector('.expand-icon');

    if (variantRow) {
        // Row already exists, just toggle visibility
        variantRow.classList.toggle('hidden');
    } else {
        // Row doesn't exist, create it and fetch data
        const newRowHtml = `<tr class="prompt-variant-group-row" data-parent-definition-id="${promptId}"><td colspan="5" class="variant-group-container"><div class="loader">Loading variants...</div></td></tr>`;
        rowElement.insertAdjacentHTML('afterend', newRowHtml);
        promptsApi.getVariants(promptId);
    }
    icon.classList.toggle('fa-chevron-right');
    icon.classList.toggle('fa-chevron-down');
}


function togglePromptVariantValue(rowElement, event) {
    if (event.target.closest('button, a, input, label')) {
        return; // Ignore clicks on interactive elements
    }
    const variantId = rowElement.dataset.promptVariantId;
    const valueRow = document.querySelector(`.prompt-value-row[data-parent-variant-id="${variantId}"]`);
    const icon = rowElement.querySelector('.expand-icon');

    if (valueRow) {
        valueRow.classList.toggle('hidden');
        icon.classList.toggle('fa-chevron-right');
        icon.classList.toggle('fa-chevron-down');
    }
}

function togglePromptEnabled(checkbox, event) {
    event.stopPropagation();
    const variantPk = checkbox.dataset.promptVariantPk;
    const isEnabled = checkbox.checked;
    promptsApi.update(variantPk, undefined, isEnabled);
}

function showPromptEditActions(variantPk) {
    const editActions = document.getElementById(`prompt-edit-actions-${variantPk}`);
    const editable = document.querySelector(`.prompt-value-content[data-prompt-variant-pk="${variantPk}"]`);
    if (editActions) {
        editActions.classList.remove('hidden');
        if (editable && !editable.dataset.originalValue) {
            editable.dataset.originalValue = editable.textContent;
        }
    }
}

function hidePromptEditActions(variantPk) {
    const editActions = document.getElementById(`prompt-edit-actions-${variantPk}`);
    setTimeout(() => {
        if (editActions && !editActions.contains(document.activeElement)) {
            editActions.classList.add('hidden');
        }
    }, 150);
}


// --- API Interaction ---

function savePromptChanges(variantPk) {
    const editableValue = document.querySelector(`.prompt-value-content[data-prompt-variant-pk="${variantPk}"]`);
    if (editableValue) {
        const newValue = editableValue.textContent;
        const originalValue = editableValue.dataset.originalValue;
        if (newValue !== originalValue) {
            promptsApi.update(variantPk, newValue);
        }
        editableValue.blur();
    }
}

function cancelPromptChanges(variantPk) {
    const editableValue = document.querySelector(`.prompt-value-content[data-prompt-variant-pk="${variantPk}"]`);
    if (editableValue) {
        editableValue.textContent = editableValue.dataset.originalValue || editableValue.textContent;
        editableValue.blur();
    }
}

function deletePromptVariant(variant_pk, promptKey) {
    if (confirm(`Are you sure you want to delete this version of prompt "${promptKey}"? This action cannot be undone.`)) {
        promptsApi.deleteVariant(variant_pk);
    }
}
function deletePrompt(prompt_pk, promptKey) {
    if (confirm(`Are you sure you want to delete prompt "${promptKey}"? This action cannot be undone.`)) {
        promptsApi.delete(prompt_pk);
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
    promptsApi.list();
}


function toggleAddPromptForm(show) {
    const formContainer = document.getElementById('add-prompt-form-container');
    if (formContainer) {
        formContainer.classList.toggle('hidden', !show);
        if (show) {
            document.getElementById('add-prompt-form').reset();
        }
    }
}

function saveNewPrompt() {
    const source = document.getElementById('new-prompt-source').value.trim();
    const key = document.getElementById('new-prompt-key').value.trim();
    const description = document.getElementById('new-prompt-description').value.trim();
    const data_lambda = document.getElementById('new-prompt-data-lambda').value.trim();
    const value = document.getElementById('new-prompt-value').value.trim();

    if (!source || !key || !value) {
        alert('Source, Key, and Initial Value are required fields.');
        return;
    }

    promptsApi.create(source, key, value, description, data_lambda);
    toggleAddPromptForm(false); // Hide form after submission
}

let promptDefinitionUpdateTimers = {};
function debouncePromptDefinitionUpdate(promptPk) {
    clearTimeout(promptDefinitionUpdateTimers[promptPk]);
    promptDefinitionUpdateTimers[promptPk] = setTimeout(() => {
        const descriptionEl = document.querySelector(`.editable-prompt-field[data-pk="${promptPk}"][data-field="description"]`);
        const dataLambdaEl = document.querySelector(`.editable-prompt-field[data-pk="${promptPk}"][data-field="data_lambda"]`);
        
        const description = descriptionEl ? descriptionEl.innerText : undefined;
        const data_lambda = dataLambdaEl ? dataLambdaEl.innerText : undefined;

        promptsApi.updateDefinition(promptPk, description, data_lambda);
    }, 750); // 750ms debounce delay
}

function handlePromptEditKeydown(event, promptPk) {
    // Prevent creating a new line in the contenteditable div, as it's for single-line text
    if (event.key === 'Enter') {
        event.preventDefault();
        event.target.blur(); // Remove focus
        debouncePromptDefinitionUpdate(promptPk); // Trigger save immediately
    }
}