let websocket;
let wsPath;

// --- Global Caches ---
window.allAgents = {};
window.allAgentInstances = {};
window.allAvailableModels = {};
window.allAvailableSystems = {};
window.allToolInstallations = {};
window.allToolDefinitions = {};
window.globalPromptCache = [];
window.agentPromptCache = {}; // Keyed by agent_id

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
        window.allAgents = {}; 
        payload.agents.forEach(agentData => {
            addOrUpdateAgentInSidebar(agentData);
        });
    },
    'AgentDeleted': (payload) => {
        removeAgentFromSidebar(payload.agent_pk);
    },
    'AgentCreated': (payload) => {
        // This handler provides a seamless and robust create-to-edit workflow.
        
        // 1. Immediately update the sidebar and global cache with the new agent data.
        // This makes this handler self-sufficient and removes the race condition with
        // the generic 'Agent' broadcast message.
        addOrUpdateAgentInSidebar(payload);

        // 2. Close the 'Create Agent' tab.
        closeMainTab('tabContent_add_agent');
        
        // 3. Open the 'Edit' tab for the new agent, which can now reliably find the
        // agent's data in the global cache.
        openAgentEditTab(null, payload.id);
    },
    'AgentInstance': (payload) => {
        window.allAgentInstances[payload.id] = payload;
        renderAgentInstance(payload);
        renderAgentInstanceHeader(payload, payload.id);
        renderSidebarSettings(payload);
        renderSidebarFilesystemHeader(payload);
        if (payload.agent_id && window.allAgents[payload.agent_id]) {
            addOrUpdateAgentInSidebar(window.allAgents[payload.agent_id]);
        }
    },
    'AgentInstanceDeleted': (payload) => {
        const instanceElement = document.getElementById(`agent_instance_${payload.instance_pk}`);
        if (instanceElement) instanceElement.remove();
        delete window.allAgentInstances[payload.instance_pk];
        if (payload.agent_pk && window.allAgents[payload.agent_pk]) {
            addOrUpdateAgentInSidebar(window.allAgents[payload.agent_pk]);
        }
    },
    'AgentInstanceFork': (payload) => renderAgentInstanceForkMessage(payload),
    'AgentInstanceView': (payload) => renderInstanceView(payload),
    'AgentInstanceList': (payload) => {
        window.allAgentInstances = {};
        payload.instances.forEach(instanceData => {
            window.allAgentInstances[instanceData.id] = instanceData;
        });
        Object.values(window.allAgents).forEach(agentData => {
            addOrUpdateAgentInSidebar(agentData);
        });
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
    'PromptDefinitionList': (payload) => {
        // This is for the new hierarchical global Prompts Tab
        // It also populates the global cache used for default prompts in the Agent tab.
        window.globalPromptCache = payload.payload;
        renderPromptList(payload.payload); // Update main Prompts tab

        // Re-render relations for any agent whose relations have been loaded.
        // This ensures dropdowns in the Agent Edit tab are updated immediately.
        Object.keys(window.agentPromptCache).forEach(agentId => {
            const container = document.getElementById(`agent-prompt-relations-container-${agentId}`);
            if (container) {
                renderAgentPromptRelations(agentId, window.agentPromptCache[agentId]);
            }
        });
    },

    'PromptVariantList': (payload) => {
        // This is the new on-demand variant list
        renderPromptVariants(payload);
    },

    'PromptVariant': (payload) => {
        // When a single PromptVariant is updated or created, re-fetch the entire prompt list
        // to ensure the hierarchical view (PromptList) is fully refreshed with new counts and variants.
        promptsApi.list(); 
        
        // If the payload is for an agent-specific prompt, also refresh that agent's prompt list
        // This ensures the agent-specific prompt section in TabAgent.js also updates.
        if (payload.agent_id) {
            promptsApi.list(payload.agent_id); 
        }
    },
    'PromptDeleted': (payload) => {
        const promptRow = document.getElementById(`prompt-row-${payload.prompt_pk}`);
        const promptValueRow = document.getElementById(`prompt-value-row-${payload.prompt_pk}`);
        if (promptRow) promptRow.remove();
        if (promptValueRow) promptValueRow.remove();
    },
    'AgentPromptRelationList': (payload) => {
        // Cache the relations for this agent. This allows us to re-render the component
        // later if the global prompt list changes, ensuring the dropdown is always up-to-date.
        window.agentPromptCache[payload.agent_id] = payload.relations;
        renderAgentPromptRelations(payload.agent_id, payload.relations);
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
    'ToolDefinition': (payload) => handleToolDefinitionUpdate(payload),
    'ToolDefinitionDeleted': (payload) => handleToolDefinitionDelete(payload.tool_def_pk),
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
        delete window.allToolInstallations[payload.installation_pk];
        if (payload.system_pk) {
            const installationsForSystem = Object.values(window.allToolInstallations)
                                                .filter(inst => inst.system_id === payload.system_pk);
            renderToolInstallationList(installationsForSystem, payload.system_pk);
        }
    },
    'ToolInstanceDeleted': (payload) => {
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
    'ConversationMessagePart': (payload) => renderConversationMessagePart(payload),
    'ToolCall': (payload) => renderToolCallMessage(payload),
    'FsLogEntry': (payload) => {
        renderSidebarFilesystem(payload, payload.agentInstance_id);
        renderFilesystemMessage(payload);
    },
    'DebugLogEntry': (payload) => renderDebugLogMessage(payload),
    'LLMQuery': (payload) => renderLLMQueryMessage(payload, payload.agentInstance_id),
    'QueryMessage': (payload) => renderQueryMessage(payload),
    'QueryMessagePart': (payload) => renderQueryMessagePart(payload),

    'LLMResponse': (payload) => renderLLMResponseMessage(payload, payload.agentInstance_id),
    'AgentToAgentMessage': (payload) => renderInterAgentMessage(payload),
    'SubAgentLink': (payload) => {
        if (payload.supervisor_instance_id === window.currentAgentInstancePk) {
            // If the message is for the currently active instance, refresh its sub-agents
            agentInstanceApi.getSubAgents(payload.supervisor_instance_id);
        }
    },
    'SubAgentLinkList': (payload) => {
        renderSidebarSubagents(payload.sub_agents, payload.instance_pk);
    },
    'error': (payload) => addToClientLog(`Error: ${payload.message}`, 'error', null, payload.agentInstance_id),
    'info': (payload) => addToClientLog(`Info: ${payload.message}`, 'info', null, payload.agentInstance_id)
};
