// This file manages the rendering and interactions for the VARS sidebar.
// Assume getTemplate is provided globally by ui/static/js/core/utils.js

let allAgentVarsStates = {};

function getInstanceVarsState(instancePk) {
    if (!allAgentVarsStates[instancePk]) {
        allAgentVarsStates[instancePk] = {};
    }
    return allAgentVarsStates[instancePk];
}

function renderSidebarVars(varsList, instancePk) {
    const sidebarVarsTemplate = getTemplate('SidebarVarsTemplate');
    const state = getInstanceVarsState(instancePk);
    Object.assign(state, varsList); // Update state

    const container = document.getElementById(`sidebar-tab-vars_${instancePk}`);
    if (container) {
        container.innerHTML = sidebarVarsTemplate({ vars: state });
    }
}

function updateSidebarVar(payload, instancePk) {
    const state = getInstanceVarsState(instancePk);
    if (payload.action === 'delete') {
        delete state[payload.key];
    } else {
        state[payload.key] = payload.value;
    }
    renderSidebarVars({}, instancePk); // Re-render with updated state
}