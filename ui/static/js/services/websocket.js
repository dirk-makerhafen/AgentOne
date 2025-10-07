let websocket;
let wsPath;

// Global caches for various objects, following the existing pattern
window.allAgents = window.allAgents || {};
window.allAgentInstances = window.allAgentInstances || {};
window.allAvailableModels = window.allAvailableModels || {};
window.allAvailableSystems = window.allAvailableSystems || {};
window.allToolInstallations = window.allToolInstallations || {};
window.allToolDefinitions = window.allToolDefinitions || {};

function connectWebSocket(user_pk) {
    if (!user_pk) {
        addToClientLog("Invalid WebSocket user_pk. Cannot establish connection.", 'error');
        return;
    }
    const protocol = window.location.protocol === "https:" ? "wss://" : "ws://";
    wsPath = protocol + window.location.host + `/ws/${user_pk}/`;
    websocket = new WebSocket(wsPath);

    websocket.onopen = function(e) {
        addToClientLog("WebSocket connection established.", 'success');
        // Once connected, request the list of agents for this user
        // This will trigger renderAgent and renderAgentInstance when the data comes back
        if (websocket && websocket.readyState === WebSocket.OPEN) {
             websocket.send(JSON.stringify({
                 type: 'request_agent_list',
                 payload: {}
             }));
            requestProviderList()             
            requestSystemList(); // Request systems list on WebSocket open
            requestMcpList(); // Request MCP servers list on WebSocket open
            requestToolDefinitionList();
            window.initializeAgentListTemplates(); // Initialize agent list templates
         }
    };
   

    websocket.onmessage = function(e) {
        const payload = JSON.parse(e.data);

        // All incoming messages from the user group will contain an agentInstance_pk if they pertain to an instance.
        // We need to check if this message is for the currently selected agent instance.
        //console.log("ON MESSAGE", payload)
        switch (payload.object) {
            
            case 'Agent': 
                window.renderAgent(payload);
                // After saving, the server sends back the updated agent object.
                // We need to find the open edit tab (if any) and update its UI.
                const agentNameInTab = document.querySelector(`#agent-edit-button-${payload.id} span`);
                if (agentNameInTab) {
                    agentNameInTab.innerHTML = `<i class="fa fa-user-circle-o"></i> ${payload.name}`;
                }
                const agentEditTabTitle = document.querySelector(`#agent-edit-button-${payload.id} span`);
                if (agentEditTabTitle) {
                    agentEditTabTitle.innerHTML = `<i class="fa fa-user-circle-o"></i> ${payload.name}`;
                }
                break;
                
            case 'AgentList':
                payload.agents.forEach(agentData => { 
                    window.allAgents[agentData.id] = agentData;
                    renderAgent(agentData)
                });
                //window.renderAgentList(payload.agents); // Delegate to AgentList.js
                break;

            case 'AgentDeleted':
                const agentElement = document.getElementById(`agent_${payload.agent_pk}`);
                if (agentElement) {
                    agentElement.remove();
                }
                break;

            case 'AgentInstance':
                window.allAgentInstances[payload.id] = payload;
                // renderAgentInstance now handles all UI updates for an instance payload,
                // including the header, settings, sidebar item, and instance-specific status bar.
                // This ensures that even non-active tabs receive updates.
                renderAgentInstance(payload);
                break;

            case 'AgentInstanceDeleted':
                const agentInstanceElement = document.getElementById(`agent_instance_${payload.agent_pk}`);
                if (agentInstanceElement) {
                    agentInstanceElement.remove();
                }
                break;

            case 'AgentInstanceList':
                payload.instances.forEach(instanceData => { 
                    window.allAgentInstances[instanceData.id] = instanceData;
                    renderAgentInstance(instanceData)
                });
                break;

            case 'ModelList':
                window.allAvailableModels = payload.models; // for dropdowns
                if (window.currentAgentInstancePk) {
                    //console.log("WebSocket: ModelList received, re-requesting instance details for:", window.currentAgentInstancePk);
                    websocket.send(JSON.stringify({
                        type: 'request_instance_details',
                        payload: { instance_pk: window.currentAgentInstancePk }
                    }));
                }
                break;
            
            case 'SystemList':
                window.allAvailableSystems = payload.systems; // for dropdowns
                renderSystemList(payload.systems); // This also triggers rendering of the Systems tab
                if (window.currentAgentInstancePk) {
                    //console.log("WebSocket: SystemList received, re-requesting instance details for:", window.currentAgentInstancePk);
                    websocket.send(JSON.stringify({
                        type: 'request_instance_details',
                        payload: { instance_pk: window.currentAgentInstancePk }
                    }));
                }
                break;
            case 'PromptList':
                renderPromptList(payload.payload);
                break;

            case 'ApiProviderList':
                renderProviderList(payload.providers);
                break;

            case 'ApiProvider':
                renderSingleProvider(payload, document.querySelector('#providers-list-body'));
                break;

            case 'ToolInstance':
                renderSingleMcpServer(payload);
                break;

            case 'list_mcp_servers': // This 'type' matches the message sent by consumer
                renderMcpList(payload.data);
                break;

            case 'ProviderDeleted':
                const providerElement = document.getElementById(`provider_${payload.provider_pk}`);
                if (providerElement) {
                    providerElement.remove();
                    addToClientLog(`Provider with ID ${payload.provider_pk} has been deleted.`, 'info');
                }
                const providersListBody = document.getElementById('providers-list-body');
                if (providersListBody && providersListBody.childElementCount === 0) {
                    providersListBody.innerHTML = '<div class="alert alert-info" role="alert">No API providers found. Click the "+" button to add one.</div>';
                }
                break;

            case 'MCPServerDeleted':
                const mcpServerElement = document.querySelector(`.mcp-server-item[data-id="${payload.mcp_server_pk}"]`);
                if (mcpServerElement) {
                    mcpServerElement.remove();
                    addToClientLog(`MCP Server with ID ${payload.mcp_server_pk} has been deleted.`, 'info');
                }
                const mcpListBody = document.getElementById('mcp-list-body');
                if (mcpListBody && mcpListBody.childElementCount === 0) {
                    mcpListBody.innerHTML = '<p>No MCP Servers configured.</p>';
                }
                break;

            case 'System':
                renderSystem(payload); // Assuming payload.system holds the single system object
                break;

            case 'ToolDefinitionList':
                window.allToolDefinitions = {}; // Clear existing cache
                payload.tool_definitions.forEach(td => {
                    window.allToolDefinitions[td.id] = td;
                });
                renderToolDefinitionList(payload.tool_definitions);
                break;

            case 'ToolDefinition':
                if (payload.action === 'deleted') {
                    // Handle deletion
                    if (window.handleToolDefinitionDelete) {
                        window.handleToolDefinitionDelete(payload.id);
                    }
                } else {
                    // This handles single object updates (e.g., after create or edit)
                    if (window.handleToolDefinitionUpdate) {
                        // Use the new in-place update handler which also updates the cache
                        window.handleToolDefinitionUpdate(payload);
                    } else {
                        // Fallback to full re-render if the new handler isn't available
                        window.allToolDefinitions[payload.id] = payload;
                        renderToolDefinitionList(Object.values(window.allToolDefinitions));
                    }
                }
                break;



            case 'ToolInstallation':
                // Update or add a single ToolInstallation
                window.allToolInstallations[payload.id] = payload;
                // Trigger re-rendering of the system that this installation belongs to
                // We need to re-render the specific system's tool list
                if (payload.system_id) {
                    renderToolInstallationList(Object.values(window.allToolInstallations).filter(inst => inst.system_id === payload.system_id), payload.system_id);
                }
                break;

            case 'ToolInstallationList':
                // Clear cache for installations belonging to the requested system to avoid stale data
                const systemIdForList = payload.tool_installations.length > 0 ? payload.tool_installations[0].system_id : null;
                if (systemIdForList) {
                    for (const key in window.allToolInstallations) {
                        if (window.allToolInstallations[key].system_id === systemIdForList) {
                            delete window.allToolInstallations[key];
                        }
                    }
                }
                payload.tool_installations.forEach(installation => {
                    window.allToolInstallations[installation.id] = installation;
                });
                // Now render the list for the specific system
                if (systemIdForList) {
                    renderToolInstallationList(payload.tool_installations, systemIdForList);
                }
                break;

            case 'ToolInstallationLogList':
                // This message is handled by the new renderer
                renderToolInstallationLogsInline(payload.logs);
                break;
           




            case 'InstancePermissionList':
                renderSidebarPermissions(payload);
                break;

            case 'InstancePermissionUpdate':
                updatePermissionCardUI(payload); // updatePermissionCardUI internally checks currentAgentInstancePk
                break;

            case 'HistoryLoadResult':
                const historyInstancePk = payload.agentInstance_id;
                const instanceLogState = getInstanceLogState(historyInstancePk);

                // Remove the loading indicator
                const loadingIndicator = document.getElementById(`history-loading-indicator_${historyInstancePk}`);
                if (loadingIndicator) {
                    loadingIndicator.remove();
                }

                // Adjust scroll position after all history messages have been prepended
                const logArea = document.getElementById(`logArea_${historyInstancePk}`);
                if (instanceLogState.scrollHeightBeforeHistoryLoad !== null && logArea) {
                    const newScrollHeight = logArea.scrollHeight;
                    logArea.scrollTop = newScrollHeight - instanceLogState.scrollHeightBeforeHistoryLoad;
                    instanceLogState.scrollHeightBeforeHistoryLoad = null; // Reset after use
                }
                applyActiveHighlight(historyInstancePk); 
                instanceLogState.isLoadingHistory = false;
                if (payload.count === 0) {
                    instanceLogState.hasMoreHistory = false;
                    addToClientLog("No more history to load.", 'info', null, historyInstancePk);
                }
                break;

            case 'InitialFilesystemState':
                resetFilesystemState(payload.agentInstance_id);
                // Then, render each item from the initial state
                payload.items.forEach(item => {
                    renderSidebarFilesystem(item, payload.agentInstance_id);
                });
                break;
            
            case 'InitialMemoryState':
                payload.items.forEach(item => {
                    renderSidebarMemory(item, payload.agentInstance_id); // Corrected field name
                });
                break;

            case 'InitialVarsState':
                renderSidebarVars(payload.items, payload.agentInstance_id); // Corrected field name
                break;

            case 'MemoryItem':
                renderSidebarMemory(payload, payload.agentInstance_id); // Corrected field name
                break;

            case 'PythonToolVar':
                renderPythonToolVarMessage(payload, payload.agentInstance_id); // Corrected field name
                updateSidebarVar(payload, payload.agentInstance_id); // Corrected field name
                break;

            case 'ConversationMessage':
                renderConversationMessage(payload); // Corrected field name
                break;
            case 'ToolCall':
                renderToolCallMessage(payload, payload.agentInstance_id); // Corrected field name
                break;

            case 'FsLogEntry':
                renderSidebarFilesystem(payload, payload.agentInstance_id); // Corrected field name
                renderFilesystemMessage(payload); // Corrected field name
                break;

            case 'DebugLogEntry':
                renderDebugLogMessage(payload); // Corrected field name
                break;
                
            case 'LLMQuery':
                renderLLMQueryMessage(payload, payload.agentInstance_id); // Corrected field name
                break;
            
            case 'LLMResponse':
                renderLLMResponseMessage(payload); // Corrected field name
                break;

            case 'AgentToAgentMessage':
                renderInterAgentMessage(payload); // Corrected field name
                break;

             case 'error': // Generic error, possibly sent directly from consumer
                // If an instance_pk is available, route to its console, else to global
                const errorTarget = payload.agentInstance_id; // Corrected field name
                if (errorTarget) {
                    addToClientLog(`Error: ${payload.message}`, 'error');
                } else {
                    addToClientLog(`Error: ${payload.message}`, 'error');
                }
                break;

             case 'info': // Generic info, possibly sent directly from consumer
                // If an instance_pk is available, route to its console, else to global
                const infoTarget = payload.agentInstance_id; // Corrected field name
                if (infoTarget) {
                    addToClientLog(`Info: ${payload.message}`, 'info');
                } else {
                    addToClientLog(`Info: ${payload.message}`, 'info');
                }
                break;

            default:
                addToClientLog(`Unknown Payload Object: ${JSON.stringify(payload)}`, 'error');
        }
        $(document).trigger('websocketMessage', [payload]);
    };

    websocket.onclose = function(e) {
        addToClientLog(`WebSocket connection closed. Code: ${e.code}, Reason: ${e.reason || 'No Reason'}`, 'error');
        // Reconnection logic, assuming targetType and targetPk are still valid
        setTimeout(() => connectWebSocket(user_pk), 5000); // Pass user_pk for reconnection
    };

    websocket.onerror = function(e) {
        addToClientLog("WebSocket Error: " + e.message, 'error');
        websocket.close();
    };
}

