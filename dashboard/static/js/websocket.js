let websocket;
let wsPath;

// Function to connect WebSocket, now takes targetType ('user') and targetPk (user_pk)
function connectWebSocket(user_pk) {
    if (!user_pk) {
        addToConsoleArea("Invalid WebSocket user_pk. Cannot establish connection.", 'error');
        return;
    }

    const protocol = window.location.protocol === "https:" ? "wss://" : "ws://";
    // Connect to the user-specific WebSocket endpoint - Corrected path based on user's input
    wsPath = protocol + window.location.host + `/ws/${user_pk}/`;

    websocket = new WebSocket(wsPath);

    websocket.onopen = function(e) {
        addToConsoleArea("WebSocket connection established.", 'success');
        // Once connected, request the list of agents for this user
        // This will trigger renderAgent and renderAgentInstance when the data comes back
        if (websocket && websocket.readyState === WebSocket.OPEN) {
             websocket.send(JSON.stringify({
                 type: 'request_agent_list',
                 payload: {}
             }));
            requestProviderList();
            requestSystemList(); // Request systems list on WebSocket open
         }
    };

    websocket.onmessage = function(e) {
        const payload = JSON.parse(e.data);

        // All incoming messages from the user group will contain an agentInstance_pk if they pertain to an instance.
        // We need to check if this message is for the currently selected agent instance.
        //console.log("ON MESSAGE", payload)
        switch (payload.object) {
            
            case 'Agent': 
                renderAgent(payload);
                break;
                
            case 'AgentList':
                const agentListContainer = document.getElementById('agents-list-body');
                if (agentListContainer) {
                    // Clear the list before rendering to ensure any orphaned elements are removed.
                    agentListContainer.innerHTML = '';
                    payload.agents.forEach(agentData => {
                        if (typeof allAgents !== 'undefined') {
                            allAgents[agentData.id] = agentData;
                        }
                        renderAgent(agentData);
                    });
                }
                break;

            case 'AgentDeleted':
                const agentElement = document.getElementById(`agent_${payload.agent_pk}`);
                if (agentElement) {
                    agentElement.remove();
                }
                break;

            case 'AgentInstance':
                if (typeof allAgentInstances !== 'undefined') {
                    allAgentInstances[payload.id] = payload;
                }
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
                    if (typeof allAgentInstances !== 'undefined') {
                        allAgentInstances[instanceData.id] = instanceData;
                    }
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

            case 'ProviderDeleted':
                const providerElement = document.getElementById(`provider_${payload.provider_pk}`);
                if (providerElement) {
                    providerElement.remove();
                    addToConsoleArea(`Provider with ID ${payload.provider_pk} has been deleted.`, 'info');
                }
                const providersListBody = document.getElementById('providers-list-body');
                if (providersListBody && providersListBody.childElementCount === 0) {
                    providersListBody.innerHTML = '<div class="sidebar-item" id="no-providers-message"><p>No API providers found.</p></div>';
                }
                break;

            case 'System':
                renderSystem(payload); // Assuming payload.system holds the single system object
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
                    addToConsoleArea("No more history to load.", 'info', null, historyInstancePk);
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

            case 'InterAgentMessage':
                renderInterAgentMessage(payload); // Corrected field name
                break;

             case 'error': // Generic error, possibly sent directly from consumer
                // If an instance_pk is available, route to its console, else to global
                const errorTarget = payload.agentInstance_id ? payload.agentInstance_id : 'global'; // Corrected field name
                addToConsoleArea(`Error: ${payload.message}`, 'error', null, errorTarget);
                break;

             case 'info': // Generic error, possibly sent directly from consumer
                // If an instance_pk is available, route to its console, else to global
                const infoTarget = payload.agentInstance_id ? payload.agentInstance_id : 'global'; // Corrected field name
                addToConsoleArea(`Info: ${payload.message}`, 'info', null, infoTarget);
                break;

            default:
                addToConsoleArea(`Unknown Payload Object: ${JSON.stringify(payload)}`, 'error');
        }
    };

    websocket.onclose = function(e) {
        addToConsoleArea(`WebSocket connection closed. Code: ${e.code}, Reason: ${e.reason || 'No Reason'}`, 'error');
        // Reconnection logic, assuming targetType and targetPk are still valid
        setTimeout(() => connectWebSocket(user_pk), 5000); // Pass user_pk for reconnection
    };

    websocket.onerror = function(e) {
        addToConsoleArea("WebSocket Error: " + e.message, 'error');
        websocket.close();
    };
}


function sendSystemCreateRequest(name) {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'system_create',
            payload: { name: name }
        }));

    }
}

function requestProviderList() {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: 'request_provider_list' }));
    }
}

function requestSystemList() {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: 'request_system_list' }));
    }
}
