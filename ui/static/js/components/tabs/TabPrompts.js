// This file manages the rendering and interactions for the hierarchical Prompts list tab using on-demand loading.

let templates = {};

function initializePromptTemplates() {
    templates.definitionRow = getTemplate('PromptDefinitionRowTemplate');
    templates.variantGroupRow = getTemplate('PromptVariantGroupRowTemplate');
    templates.variantRow = getTemplate('PromptVariantRowTemplate');
    Handlebars.registerPartial('PromptVariantRowTemplate', templates.variantRow);
}

function renderPromptDefinitionList(promptDefinitions) {
    const tableBody = document.getElementById('prompts-table-body');
    if (!tableBody) return;

    // Preserve expanded state
    const expandedDefIds = new Set();
    tableBody.querySelectorAll('.prompt-definition-row').forEach(row => {
        if (row.dataset.variantsLoaded === "true") {
            expandedDefIds.add(row.dataset.promptDefinitionId);
        }
    });

    tableBody.innerHTML = ''; // Clear existing content

    if (!promptDefinitions || promptDefinitions.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="5"><p class="log-info">No prompt templates with system variants found.</p></td></tr>';
        return;
    }

    promptDefinitions.forEach(def => {
        tableBody.insertAdjacentHTML('beforeend', templates.definitionRow(def));
    });

    // Restore expanded state by re-fetching variants
    expandedDefIds.forEach(id => {
        const row = tableBody.querySelector(`.prompt-definition-row[data-prompt-definition-id="${id}"]`);
        if (row) {
            const icon = row.querySelector('.expand-icon');
            icon.classList.remove('fa-chevron-right');
            icon.classList.add('fa-chevron-down');
            promptsApi.getVariants(id); 
        }
    });
}

function renderPromptVariants(promptPk, systemVariants, userVariants) {
    const container = document.getElementById('prompts-table-body');
    const definitionRow = container.querySelector(`.prompt-definition-row[data-prompt-definition-id="${promptPk}"]`);
    if (!definitionRow) return;

    // Mark as loaded to prevent re-fetching
    definitionRow.dataset.variantsLoaded = "true";

    const systemGroupHtml = templates.variantGroupRow({
        prompt_definition_id: promptPk,
        group_title: 'System Variants',
        variants: systemVariants,
        no_variants_message: 'No system variants found.'
    });
    const userGroupHtml = templates.variantGroupRow({
        prompt_definition_id: promptPk,
        group_title: 'Your Global Variants',
        variants: userVariants,
        no_variants_message: 'No global variants created by you. Click "Create" on a system version to start.'
    });

    // Insert the newly rendered HTML. User variants should come after system variants.
    definitionRow.insertAdjacentHTML('afterend', userGroupHtml);
    definitionRow.insertAdjacentHTML('afterend', systemGroupHtml);
}


// --- Inline Event Handlers ---

function togglePromptDefinition(rowElement) {
    const definitionId = rowElement.dataset.promptDefinitionId;
    const icon = rowElement.querySelector('.expand-icon');
    const container = rowElement.closest('tbody');
    const variantsLoaded = rowElement.dataset.variantsLoaded === "true";

    // Action: If icon is 'right' (closed), we want to open it.
    if (icon.classList.contains('fa-chevron-right')) {
        icon.classList.remove('fa-chevron-right');
        icon.classList.add('fa-chevron-down');

        if (variantsLoaded) {
            // Content is loaded but hidden, just show it.
            container.querySelectorAll(`.prompt-variant-group-row[data-parent-definition-id="${definitionId}"]`).forEach(row => row.classList.remove('hidden'));
        } else {
            // Content not loaded, fetch it.
            promptsApi.getVariants(definitionId);
            // The websocket handler will add it, and it will be visible by default.
        }
    } 
    // Action: If icon is 'down' (open), we want to close it.
    else {
        icon.classList.remove('fa-chevron-down');
        icon.classList.add('fa-chevron-right');
        // Just hide the content.
        container.querySelectorAll(`.prompt-variant-group-row[data-parent-definition-id="${definitionId}"]`).forEach(row => row.classList.add('hidden'));
    }
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
    const promptPk = checkbox.dataset.promptPk;
    const isEnabled = checkbox.checked;
    promptsApi.update(promptPk, undefined, isEnabled);
}

function showPromptEditActions(promptPk) {
    const editActions = document.getElementById(`prompt-edit-actions-${promptPk}`);
    const editable = document.querySelector(`.prompt-value-content[data-prompt-pk="${promptPk}"]`);
    if (editActions) {
        editActions.classList.remove('hidden');
        if (editable && !editable.dataset.originalValue) {
            editable.dataset.originalValue = editable.textContent;
        }
    }
}

function hidePromptEditActions(promptPk) {
    const editActions = document.getElementById(`prompt-edit-actions-${promptPk}`);
    setTimeout(() => {
        if (editActions && !editActions.contains(document.activeElement)) {
            editActions.classList.add('hidden');
        }
    }, 150);
}


// --- API Interaction Functions ---

function savePromptChanges(promptPk) {
    const editableValue = document.querySelector(`.prompt-value-content[data-prompt-pk="${promptPk}"]`);
    if (editableValue) {
        const newValue = editableValue.textContent;
        const originalValue = editableValue.dataset.originalValue;
        if (newValue !== originalValue) {
            promptsApi.update(promptPk, newValue);
        }
        editableValue.blur();
    }
}

function cancelPromptChanges(promptPk) {
    const editableValue = document.querySelector(`.prompt-value-content[data-prompt-pk="${promptPk}"]`);
    if (editableValue) {
        editableValue.textContent = editableValue.dataset.originalValue || editableValue.textContent;
        editableValue.blur();
    }
}

function deletePrompt(promptPk, promptKey) {
    if (confirm(`Are you sure you want to delete this version of prompt "${promptKey}"? This action cannot be undone.`)) {
        promptsApi.delete(promptPk);
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
