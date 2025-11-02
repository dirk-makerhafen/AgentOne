// This function needs to be globally available so TabAgent.js can call it.
let allPrompts = window.globalPromptCache; // Directly reference global cache

// This function is responsible for ensuring the global prompt cache is up-to-date
// It should be called when renderAgentPromptRelations is invoked.
function fetchAllPrompts() {
    // This function just ensures the global prompt cache is populated.
    promptsApi.list();
}

function renderAgentPromptRelations(agentId, relations) {
    // This function is now called by the websocket handler when relations are fetched.
    
    // Ensure global prompts are available for the dropdown. This is usually fast as it's cached.
    

    const template = getTemplate("AgentPromptRelationsTemplate");
    const allPrompts = window.globalPromptCache || [];

    // Prepare data for rendering: enrich relations with full prompt details
    const relationsWithPrompts = relations.map(relation => {
        const promptDetails = allPrompts.find(p => p.id === relation.prompt_id);
        return { ...relation, prompt: promptDetails || { source: "Unknown", key: "Prompt" } };
    });

    const context = {
        agent_id: agentId,
        agent_prompt_relations: relationsWithPrompts,
        all_prompts: allPrompts,
    };

    const container = document.getElementById(`agent-prompt-relations-container-${agentId}`);
    if (container) {
        container.innerHTML = template(context);
    }
}

// --- Inline Event Handlers for Prompt Relations ---

function showAddPromptRelationForm(agentId) {
    const form = document.getElementById(`add-prompt-relation-form-${agentId}`);
    if (form) form.style.display = 'block';
}

function hideAddPromptRelationForm(agentId) {
    const form = document.getElementById(`add-prompt-relation-form-${agentId}`);
    if (form) form.style.display = 'none';
}

function saveNewPromptRelation(agentId) {
    const form = document.getElementById(`add-prompt-relation-form-${agentId}`);
    if (!form) return;

    const promptId = form.querySelector(`#new-relation-prompt-${agentId}`).value;
    const role = form.querySelector(`#new-relation-role-${agentId}`).value;
    const insertAt = form.querySelector(`#new-relation-insert-at-${agentId}`).value;
    const index = parseInt(form.querySelector(`#new-relation-index-${agentId}`).value);

    if (promptId) {
        sendRequest("create_agent_prompt_relation", {
            agent_id: agentId,
            prompt_pk: parseInt(promptId),
            role: role,
            insert_at: insertAt,
            index: index,
        });
        hideAddPromptRelationForm(agentId);
    } else {
        alert("Please select a prompt.");
    }
}

function deletePromptRelation(relationId) {
    if (confirm("Are you sure you want to delete this prompt relation?")) {
        sendRequest("delete_agent_prompt_relation", { relation_id: parseInt(relationId) });
    }
}
