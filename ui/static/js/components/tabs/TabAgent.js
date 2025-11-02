// This file manages the interaction of the "Edit Agent" tab.



let agentUpdateTimers = {};


function agentUpdate(agentId) {
    clearTimeout(agentUpdateTimers[agentId]);
    agentUpdateTimers[agentId] = setTimeout(() => {
        const form = document.getElementById(`edit-agent-form-${agentId}`);
        if (!form) return;
        const name = form.querySelector(`#agent-name-${agentId}`).value;
        const description = form.querySelector(`#agent-description-${agentId}`).value;
        const available_tool_ids = Array.from(form.querySelectorAll('input[name="available_tools"]:checked')).map(cb => cb.value);
        const limit_max_conversation_messages = form.querySelector(`#agent-limit-conversation-${agentId}`).value;
        const limit_max_memory_items = form.querySelector(`#agent-limit-memory-${agentId}`).value;
        const limit_max_automated_steps = form.querySelector(`#agent-limit-steps-${agentId}`).value;
        agentApi.update(agentId, name, description, available_tool_ids, limit_max_conversation_messages, limit_max_memory_items, limit_max_automated_steps);
    }, 500);
}

function agentCreateFromTab(event) {
    event.preventDefault();
    event.stopPropagation();
    const form = document.getElementById('add-agent-form-tab');
    if (!form) return;

    const name = form.querySelector('#agent-name-new').value.trim();
    const description = form.querySelector('#agent-description-new').value.trim();
    const availableToolIds = Array.from(form.querySelectorAll('input[name="available_tools"]:checked')).map(cb => parseInt(cb.value));
    const limit_max_conversation_messages = form.querySelector('#agent-limit-conversation-new').value;
    const limit_max_memory_items = form.querySelector('#agent-limit-memory-new').value;
    const limit_max_automated_steps = form.querySelector('#agent-limit-steps-new').value;

    if (!name) { 
        alert('Agent name is required.'); 
        return; 
    }
    
    agentApi.create(name, description, availableToolIds, limit_max_conversation_messages, limit_max_memory_items, limit_max_automated_steps);
}


function updateAgentEditTab(updatedAgent) {
    const agentId = updatedAgent.id;
    const tabContent = document.getElementById(`tabContent_edit_agent_${agentId}`);

    if (tabContent) {
        // Ensure the global prompt cache is loaded before rendering prompt-related sections
        promptsApi.list();

        // Update timestamp
        const timestampElement = tabContent.querySelector(`#last-updated-${agentId}`);
        if (timestampElement) {
            const formattedTimestamp = new Date(updatedAgent.updated_at).toLocaleString();
            timestampElement.textContent = `Last updated: ${formattedTimestamp}`;
        }

        // Update tab button name
        const tabButton = document.querySelector(`#mainTabBar > .tab-button[data-tab-content-id='tabContent_edit_agent_${agentId}']`);
        if (tabButton) {
            const textNode = Array.from(tabButton.childNodes).find(node => node.nodeType === Node.TEXT_NODE);
            if(textNode) textNode.textContent = `Edit: ${updatedAgent.name} `;
        }
        
        // Fetch and render the prompt relations
        promptsApi.getRelations(agentId);
        fetchAllPrompts();
    }
}



function initializeAgentTab(agentId) {
    // This function is triggered by an onload event in the TabAgent.html template
    // when an existing agent's tab is rendered. It ensures that all necessary
    // dynamic data, like prompt relations, is fetched on tab open.
    promptsApi.getRelations(agentId);
    fetchAllPrompts();
}