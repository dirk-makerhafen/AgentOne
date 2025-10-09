// This file manages the rendering and interaction for the header within an agent instance tab.

function renderAgentInstanceHeader(payload, instancePk) {
    const agentInstanceHeaderTemplate = getTemplate('AgentInstanceHeaderTemplate');
    const headerContainer = document.getElementById(`agentInstanceHeader_${instancePk}`);
    if (!headerContainer) return;

    const context = {
        message: payload,
        all_available_models: Object.values(window.allAvailableModels || {}),
        all_available_systems: Object.values(window.allAvailableSystems || {})
    };
    headerContainer.innerHTML = agentInstanceHeaderTemplate(context);
}

function handleInstanceDescriptionTextEdit(element, instanceId) {
    const newDescriptionText = element.textContent.trim();
    if (newDescriptionText !== element.dataset.originalValue) {
        agentInstanceApi.update(instanceId, { "description_text": newDescriptionText });
        element.dataset.originalValue = newDescriptionText; // Update original value after successful save
    }
}

function handleAutoRunLimitChange(inputElement, instanceId) {
    const newValue = parseInt(inputElement.value, 10);
    if (!isNaN(newValue)) {
        agentInstanceApi.update(instanceId, { "limit_max_automated_steps": newValue });
    }
}

function handleInstanceModelChange(selectElement, instanceId) {
    agentInstanceApi.update(instanceId, { "model_id": selectElement.value });
}

function handleInstanceSystemChange(selectElement, instanceId) {
    agentInstanceApi.update(instanceId, { "system_id": selectElement.value });
}

function handleInstanceNameEdit(element, instanceId) {
    const newName = element.textContent.trim();
    if (newName !== element.dataset.originalValue) {
        agentInstanceApi.update(instanceId, { "name": newName });
    }
}
