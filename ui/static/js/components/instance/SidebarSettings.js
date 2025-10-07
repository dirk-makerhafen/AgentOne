// This file manages the rendering and interactions for the Settings sidebar.

function renderSidebarSettings(instancePayload) {
    const sidebarSettingsTemplate = getTemplate('SidebarSettingsTemplate');
    const container = document.getElementById(`sidebar-tab-settings_${instancePayload.id}`);
    if (container) {
        container.innerHTML = sidebarSettingsTemplate(instancePayload);
    }
}

function showLimitEdit(limitType, instanceId) {
    document.getElementById(`limit-${limitType}-text_${instanceId}`).style.display = 'none';
    document.getElementById(`limit-${limitType}-input_${instanceId}`).style.display = 'inline-block';
    document.getElementById(`limit-${limitType}-input_${instanceId}`).focus();
}

function saveLimit(limitType, instanceId) {
    const input = document.getElementById(`limit-${limitType}-input_${instanceId}`);
    const value = parseInt(input.value);
    const keyMap = {
        'convo': 'limit_max_conversation_messages',
        'mem': 'limit_max_memory_items',
        'steps': 'limit_max_automated_steps'
    };
    if (keyMap[limitType]) {
        agentInstanceApi.update(instanceId, { [keyMap[limitType]]: value });
    }
    cancelLimitEdit(limitType, instanceId);
}

function cancelLimitEdit(limitType, instanceId) {
    document.getElementById(`limit-${limitType}-text_${instanceId}`).style.display = 'inline-block';
    document.getElementById(`limit-${limitType}-input_${instanceId}`).style.display = 'none';
}

function handleLimitKeydown(event, limitType, instanceId) {
    if (event.key === 'Enter') saveLimit(limitType, instanceId);
    if (event.key === 'Escape') cancelLimitEdit(limitType, instanceId);
}

function handleHistoryLimitChange(event, instanceId) {
    const input = event.target;
    const ruleName = input.dataset.ruleName;
    const limitType = input.dataset.limitType;
    const value = input.value === '' ? null : parseInt(input.value);
    const limits = { [limitType]: value };
    limitsApi.update(instanceId, ruleName, limits);
}

function resetHistoryLimit(ruleName, instanceId) {
    limitsApi.reset(instanceId, ruleName);
}
