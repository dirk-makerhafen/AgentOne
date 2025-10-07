const debounce = (func, delay) => {
    let timeoutId;
    return (...args) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
            func.apply(this, args);
        }, delay);
    };
};

const agentEditTabTemplate = Handlebars.compile(`
    <div class="agent-edit-container">
        <h3>Edit Agent: {{agent.name}}</h3>
        <form id="edit-agent-form-{{agent.id}}">
            <div class="form-group">
                <label for="agent-name-{{agent.id}}">Agent Name</label>
                <input type="text" class="form-control" id="agent-name-{{agent.id}}" value="{{agent.name}}">
            </div>
            <div class="form-group">
                <label for="agent-description-{{agent.id}}">Description</label>
                <textarea class="form-control" id="agent-description-{{agent.id}}" rows="3">{{agent.description}}</textarea>
            </div>
            <div class="form-group">
                <h4>Available Tools</h4>
                <div class="tool-selection-list">
                    {{#each tools}}
                    <div class="checkbox">
                        <label>
                            <input type="checkbox" name="available_tools" value="{{this.id}}" {{#if this.isSelected}}checked{{/if}}>
                            <strong>{{this.display_name}}</strong> ({{this.name}})
                            <p class="tool-description-help">{{this.description}}</p>
                        </label>
                    </div>
                    {{/each}}
                </div>
            </div>
            <div class="agent-edit-footer">
                <p class="last-updated-timestamp text-muted" id="last-updated-{{agent.id}}">Last updated: {{agent.updated_at_formatted}}</p>
            </div>
        </form>
    </div>
`);

function openAgentEditTab(agentId) {
    const agent = window.allAgents[agentId];
    if (!agent) {
        console.error(`Agent with ID ${agentId} not found in cache.`);
        return;
    }

    const tabId = `agent-edit-tab-${agentId}`;
    const tabContentId = `agent-edit-content-${agentId}`;
    const tabButtonId = `tabButton_${tabContentId}`; // Align with tabs.js's expected ID format

    // Check if tab is already open
    if (document.getElementById(tabButtonId)) {
        openMainTab(event, tabContentId, 'mainTabPanel');
        return;
    }

    // Prepare tool data for the template
    const allTools = Object.values(window.allToolDefinitions || {});
    const assignedToolIds = agent.available_tools || [];
    const toolsForTemplate = allTools.map(tool => ({
        ...tool,
        isSelected: assignedToolIds.includes(tool.id)
    })).sort((a, b) => a.display_name.localeCompare(b.display_name));

    const templateData = {
        agent: {
            ...agent,
            updated_at_formatted: new Date(agent.updated_at).toLocaleString()
        },
        tools: toolsForTemplate
    };

    // Create and append the new tab content
    const mainTabPanel = document.getElementById('mainTabPanel');
    const newTabContent = document.createElement('div');
    newTabContent.id = tabContentId;
    newTabContent.className = 'tab-content agent-edit-tab';
    newTabContent.style.display = 'none'; // Initially hidden
    newTabContent.innerHTML = agentEditTabTemplate(templateData);
    mainTabPanel.appendChild(newTabContent);

    // Create and append the new tab button
    const mainTabBar = document.getElementById('mainTabBar');
    const newTabButton = document.createElement('button');
    newTabButton.id = tabButtonId;
    newTabButton.className = 'tab-button';
    newTabButton.dataset.tabId = tabButtonId;
    newTabButton.dataset.tabContentId = tabContentId;
    newTabButton.setAttribute('draggable', 'true');
    newTabButton.ondragstart = (event) => dragTab(event, tabButtonId, tabContentId);
    newTabButton.innerHTML = `
        <span><i class="fa fa-user-circle-o"></i> ${agent.name}</span>
        <i class="fa fa-times close-tab-btn" onclick="event.stopPropagation(); closeMainTab('${tabContentId}')"></i>
    `;
    const spacer = mainTabBar.querySelector('.split-controls-container');
    mainTabBar.insertBefore(newTabButton, spacer);

    // Set the onclick attribute directly so it can be found by the tab switching logic
    newTabButton.setAttribute('onclick', `openMainTab(event, '${tabContentId}', 'mainTabPanel')`);

    // Auto-save logic
    const form = document.getElementById(`edit-agent-form-${agentId}`);
    
    const sendAgentUpdate = () => {
        const updatedName = document.getElementById(`agent-name-${agentId}`).value;
        const updatedDescription = document.getElementById(`agent-description-${agentId}`).value;
        const selectedTools = Array.from(form.querySelectorAll('input[name="available_tools"]:checked')).map(cb => parseInt(cb.value));
        const timestampEl = document.getElementById(`last-updated-${agentId}`);
        
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'update_agent',
                payload: {
                    agent_pk: agentId,
                    name: updatedName,
                    description: updatedDescription,
                    available_tool_ids: selectedTools
                }
            }));
            if (timestampEl) {
                timestampEl.textContent = 'Saving...';
            }
        }
    };

    const debouncedSendUpdate = debounce(sendAgentUpdate, 1000); // 1-second debounce
    form.addEventListener('input', debouncedSendUpdate);


    // Open the newly created tab
    openMainTab(event, tabContentId, 'mainTabPanel');
}
