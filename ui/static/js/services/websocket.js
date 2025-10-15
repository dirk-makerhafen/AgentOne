let websocket;
let wsPath;

window.allAgents = window.allAgents || {};
window.allAgentInstances = window.allAgentInstances || {};
window.allAvailableModels = window.allAvailableModels || {};
window.allAvailableSystems = window.allAvailableSystems || {};
window.allToolInstallations = window.allToolInstallations || {};
window.allToolDefinitions = window.allToolDefinitions || {};



function connectWebSocket(user_pk) {
    if (!user_pk) {
        addToClientLog("Invalid WebSocket user_pk.", 'error');
        return;
    }
    const protocol = window.location.protocol === "https:" ? "wss://" : "ws://";
    wsPath = protocol + window.location.host + `/ws/${user_pk}/`;
    websocket = new WebSocket(wsPath);

    websocket.onopen = () => {
        addToClientLog("WebSocket connection established.", 'success');
        agentApi.list();
    };

    websocket.onmessage = (e) => {
        const payload = JSON.parse(e.data);
        const handler = messageHandlers[payload.object];
        if (handler) {
            handler(payload);
        } else {
            addToClientLog(`Unknown Payload Object: ${JSON.stringify(payload)}`, 'error');
        }
    };

    websocket.onclose = (e) => {
        addToClientLog(`WebSocket connection closed. Code: ${e.code}, Reason: ${e.reason || 'N/A'}. Reconnecting...`, 'error');
        setTimeout(() => connectWebSocket(user_pk), 5000);
    };

    websocket.onerror = (e) => {
        addToClientLog("WebSocket Error", 'error');
        console.error("WebSocket Error:", e);
        websocket.close();
    };
}

const messageHandlers = {
    'Agent': (payload) => {
        addOrUpdateAgentInSidebar(payload);
        updateAgentEditTab(payload);
    },
    'AgentList': (payload) => {
        // Clear existing agents from cache before repopulating
        window.allAgents = {}; 
        payload.agents.forEach(agentData => {
            addOrUpdateAgentInSidebar(agentData);
        });
    },
    'AgentDeleted': (payload) => {
        removeAgentFromSidebar(payload.agent_pk);
    },
    'AgentInstance': (payload) => {
        window.allAgentInstances[payload.id] = payload;
        renderAgentInstance(payload); // Updates the sidebar list item
        renderAgentInstanceHeader(payload, payload.id); // Updates the tab header
        renderSidebarSettings(payload); // Updates the settings sidebar
        renderSidebarFilesystemHeader(payload); // Renders the filesystem header

        // After an instance update, refresh the parent agent's sidebar entry to update instance counts
        if (payload.agent_id && window.allAgents[payload.agent_id]) {
            addOrUpdateAgentInSidebar(window.allAgents[payload.agent_id]);
        }
    },
    'AgentInstanceDeleted': (payload) => {
        const instanceElement = document.getElementById(`agent_instance_${payload.instance_pk}`);
        if (instanceElement) instanceElement.remove();
        delete window.allAgentInstances[payload.instance_pk];

        // After an instance is deleted, refresh the parent agent's sidebar entry to update instance counts
        if (payload.agent_pk && window.allAgents[payload.agent_pk]) {
            addOrUpdateAgentInSidebar(window.allAgents[payload.agent_pk]);
        }
    },
    'AgentInstanceFork': (payload) => renderAgentInstanceForkMessage(payload),
    'AgentInstanceView': (payload) => renderInstanceView(payload),
    'AgentInstanceList': (payload) => {
        // Clear existing instances from cache before repopulating
        window.allAgentInstances = {};
        payload.instances.forEach(instanceData => {
            window.allAgentInstances[instanceData.id] = instanceData;
            // Note: We don't call renderAgentInstance here directly to avoid redundant renders if already present.
            // Individual AgentInstance messages will handle specific instance updates.
        });
        // After updating all agent instances, refresh all agent sidebar items to reflect new counts
        Object.values(window.allAgents).forEach(agentData => {
            addOrUpdateAgentInSidebar(agentData);
        });
        // Now, re-render all instances from the updated cache into their respective agent containers
        Object.values(window.allAgentInstances).forEach(instanceData => {
            renderAgentInstance(instanceData);
        });
    },
    'ModelList': (payload) => {
        window.allAvailableModels = payload.models;
        if (window.currentAgentInstancePk) {
            agentInstanceApi.get(window.currentAgentInstancePk);
        }
    },
    'SystemList': (payload) => {
        window.allAvailableSystems = payload.systems;
        renderSystemList(payload.systems);
        if (window.currentAgentInstancePk) {
            agentInstanceApi.get(window.currentAgentInstancePk);
        }
    },
    'PromptList': (payload) => renderPromptList(payload.payload),
    'PromptString': (payload) => renderSinglePrompt(payload),

    'PromptDeleted': (payload) => {
        const promptRow = document.getElementById(`prompt-row-${payload.prompt_pk}`);
        const promptValueRow = document.getElementById(`prompt-value-row-${payload.prompt_pk}`);
        if (promptRow) promptRow.remove();
        if (promptValueRow) promptValueRow.remove();
    },
    'ApiProviderList': (payload) => renderProviderList(payload.providers),
    'ApiProvider': (payload) => renderSingleProvider(payload, document.querySelector('#providers-list-body')),
    'ProviderDeleted': (payload) => {
        const providerEl = document.getElementById(`provider_${payload.provider_pk}`);
        if(providerEl) providerEl.remove();
    },
    'AiModel': (payload) => renderSingleAiModel(payload),
    'AiModelDeleted': (payload) => removeAiModel(payload),
    'ApiKey': (payload) => renderSingleApiKey(payload),
    'ApiKeyDeleted': (payload) => removeApiKey(payload),
    'System': (payload) => renderSystem(payload),
    'ToolDefinitionList': (payload) => {
        window.allToolDefinitions = {};
        payload.tool_definitions.forEach(td => { window.allToolDefinitions[td.id] = td; });
        renderToolDefinitionList(payload.tool_definitions);
    },
    'ToolDefinition': (payload) => {
        // This handler now only processes updates for existing ToolDefinitions
        handleToolDefinitionUpdate(payload);
    },
    'ToolDefinitionDeleted': (payload) => {
        // This new handler processes explicit deletion messages
        handleToolDefinitionDelete(payload.tool_def_pk);
    },
    'ToolInstallation': (payload) => {
        window.allToolInstallations[payload.id] = payload;
        if (payload.system_id) {
            renderToolInstallationList(Object.values(window.allToolInstallations).filter(inst => inst.system_id === payload.system_id), payload.system_id);
        }
    },
    'ToolInstallationList': (payload) => {
        const systemId = payload.tool_installations.length > 0 ? payload.tool_installations[0].system_id : null;
        if (systemId) {
            Object.keys(window.allToolInstallations).forEach(key => {
                if (window.allToolInstallations[key].system_id === systemId) delete window.allToolInstallations[key];
            });
        }
        payload.tool_installations.forEach(inst => { window.allToolInstallations[inst.id] = inst; });
        if (systemId) renderToolInstallationList(payload.tool_installations, systemId);
    },
    'ToolInstallationLogList': (payload) => renderToolInstallationLogsInline(payload.logs),
    'ToolInstallationDeleted': (payload) => {
        // Remove from global cache
        delete window.allToolInstallations[payload.installation_pk];
        // Re-render the list for the affected system
        if (payload.system_pk) {
            const installationsForSystem = Object.values(window.allToolInstallations)
                                                .filter(inst => inst.system_id === payload.system_pk);
            renderToolInstallationList(installationsForSystem, payload.system_pk);
        }
    },
    'ToolInstanceDeleted': (payload) => {
        // We don't remove the instance from a global cache directly,
        // but instead trigger a refresh of its parent installation's list
        // to correctly update the running instance count.
        const installation = window.allToolInstallations[payload.tool_installation_pk];
        if (installation) {
            toolInstallationApi.list(installation.system_id);
        }
    },
    'InstancePermissionList': (payload) => renderSidebarPermissions(payload),
    'HistoryLoadResult': (payload) => {
        const instancePk = payload.agentInstance_id;
        const state = getInstanceLogState(instancePk);
        const loadingIndicator = document.getElementById(`history-loading-indicator_${instancePk}`);
        if (loadingIndicator) loadingIndicator.remove();
        
        const logArea = document.getElementById(`logArea_${instancePk}`);
        if (state.scrollHeightBeforeHistoryLoad !== null && logArea) {
            logArea.scrollTop = logArea.scrollHeight - state.scrollHeightBeforeHistoryLoad;
            state.scrollHeightBeforeHistoryLoad = null;
        }
        applyActiveHighlight(instancePk);
        state.isLoadingHistory = false;
        if (payload.count === 0) state.hasMoreHistory = false;
    },
    'InitialFilesystemState': (payload) => {
        resetFilesystemState(payload.agentInstance_id);
        renderSidebarFilesystem(payload.items, payload.agentInstance_id);
    },
    'InitialMemoryState': (payload) => renderSidebarMemory(payload.items, payload.agentInstance_id),
    'InitialVarsState': (payload) => renderSidebarVars(payload.items, payload.agentInstance_id),
    'MemoryItem': (payload) => renderSidebarMemory(payload, payload.agentInstance_id),
    'PythonToolVar': (payload) => {
        renderPythonToolVarMessage(payload);
        updateSidebarVar(payload);
    },
    'ConversationMessage': (payload) => renderConversationMessage(payload),
    'ToolCall': (payload) => renderToolCallMessage(payload),
    'FsLogEntry': (payload) => {
        renderSidebarFilesystem(payload, payload.agentInstance_id);
        renderFilesystemMessage(payload);
    },
    'DebugLogEntry': (payload) => renderDebugLogMessage(payload),
    'LLMQuery': (payload) => renderLLMQueryMessage(payload, payload.agentInstance_id),
    'LLMResponse': (payload) => renderLLMResponseMessage(payload, payload.agentInstance_id),
    'AgentToAgentMessage': (payload) => renderInterAgentMessage(payload),
    'error': (payload) => addToClientLog(`Error: ${payload.message}`, 'error', null, payload.agentInstance_id),
    'info': (payload) => addToClientLog(`Info: ${payload.message}`, 'info', null, payload.agentInstance_id)
};
