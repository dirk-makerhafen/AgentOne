// This file manages the interaction of the "Edit Agent" tab.

let agentUpdateTimers = {};
const corePromptKeys = [
    { source: 'agents', key: 'System' },
    { source: 'agents', key: 'Instructions' },
    { source: 'tools', key: 'Instructions' }
];

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
    closeMainTab('tabContent_add_agent');
}

// Main function to render the core prompts section for an agent
function renderAgentCorePrompts(agentId, agentPrompts) {
    const container = document.getElementById(`core-prompts-container-${agentId}`);
    if (!container) return;

    container.innerHTML = ''; // Clear previous content
    const corePromptTemplate = getTemplate('AgentCorePromptTemplate');

    corePromptKeys.forEach(coreKey => {
        // Find if this agent has a custom override for this core prompt
        const agentOverride = agentPrompts.find(p => p.source === coreKey.source && p.key === coreKey.key);

        let context;
        if (agentOverride) {
            // Agent has a custom version
            context = {
                prompt: agentOverride,
                is_override: true,
                agent_id: agentId
            };
        } else {
            // Agent uses the global default, find it in the cache
            const globalDefault = window.globalPromptCache.find(p => p.source === coreKey.source && p.key === coreKey.key && p.owner_username === 'System');
            if (globalDefault) {
                context = {
                    prompt: globalDefault,
                    is_override: false,
                    agent_id: agentId
                };
            } else {
                // Could not find a global default to base the override on
                console.warn(`Could not find global default for ${coreKey.source}/${coreKey.key}`);
                return; // Skip rendering this card
            }
        }
        
        container.insertAdjacentHTML('beforeend', corePromptTemplate(context));
        // Attach event listeners for the new card
        attachAgentPromptEventListeners(container.lastElementChild.querySelector('.core-prompt-body'));
    });
}


function attachAgentPromptEventListeners(container) {
    const editableElement = container.querySelector('.prompt-value-content[contenteditable="true"]');
    if (editableElement) {
        const promptPk = editableElement.dataset.promptPk;
        const editActions = document.getElementById(`prompt-edit-actions-${promptPk}`);
        
        editableElement.addEventListener('focus', function() {
            if (editActions) {
                editActions.classList.remove('hidden');
                this.dataset.originalValue = this.textContent;
            }
        });

        editableElement.addEventListener('blur', function() {
            setTimeout(() => {
                if (editActions && !editActions.contains(document.activeElement)) {
                    editActions.classList.add('hidden');
                }
            }, 150);
        });
    }

    // Attach listener for the enabled toggle switch
    const toggle = container.parentElement.querySelector(`.prompt-enabled-toggle`);
    if (toggle) {
        const promptPk = toggle.dataset.promptPk;
        toggle.addEventListener('change', function(event) {
            event.stopPropagation();
            const isEnabled = this.checked;
            promptsApi.update(promptPk, undefined, isEnabled);
        });
    }
}


function updateAgentEditTab(updatedAgent) {
    const agentId = updatedAgent.id;
    const tabContent = document.getElementById(`tabContent_edit_agent_${agentId}`);

    if (tabContent) {
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
    }
}

// This function now replaces the old renderAgentPromptList
// It will be called when an agent's prompt list is received
function handleAgentPromptList(agentId, prompts) {
    renderAgentCorePrompts(agentId, prompts);
}
