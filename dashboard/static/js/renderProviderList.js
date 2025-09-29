const singleProviderBlockTemplate = Handlebars.compile(`
<div class="provider-block" id="provider_{{id}}" data-provider-id="{{id}}">
    <div class="provider-summary">
        <div class="provider-info">
            <span class="provider-name">{{name}}</span>
            {{#if url}}<a href="{{url}}" target="_blank" class="provider-url">{{url}}</a>{{/if}}
        </div>
        <div class="provider-actions">
            <button class="btn btn-xs btn-danger delete-provider-btn" title="Delete Provider"><i class="fa fa-trash"></i></button>
        </div>
        <div class="provider-stats">
            <span title="Total LLM Queries">Queries: {{formatNumber total_llm_queries}}</span>
            <span title="Total Prompt Tokens">Prompt: {{formatNumber total_prompt_tokens}}</span>
            <span title="Total Completion Tokens">Completion: {{formatNumber total_completion_tokens}}</span>
        </div>
    </div>
    <div class="provider-details-content">
        <div class="provider-section">
            <h4>Models</h4>
            <ul class="provider-detail-list">
                {{#if models.length}}
                    {{#each models}}
                        <li class="provider-detail-item" data-model-id="{{this.id}}">
                            <span class="provider-detail-item-name">{{this.name}}</span>
                            <div class="table-item-actions">
                                <button class="btn btn-xs btn-danger delete-model-btn" title="Delete Model"><i class="fa fa-trash"></i></button>
                            </div>
                            <div class="model-stats">
                                <span title="Total LLM Queries">Q: {{formatNumber this.total_llm_queries}}</span>
                                <span title="Total Prompt Tokens">P: {{formatNumber this.total_prompt_tokens}}</span>
                                <span title="Total Completion Tokens">C: {{formatNumber this.total_completion_tokens}}</span>
                            </div>
                        </li>
                    {{/each}}
                {{else}}
                    <li class="no-items-message">No models configured.</li>
                {{/if}}
            </ul>
            <div class="add-item-container">
                <input type="text" class="form-control input-xs add-model-input" placeholder="Add model name...">
                <button class="btn btn-xs btn-default add-model-btn" title="Add Model"><i class="fa fa-plus"></i></button>
            </div>
        </div>
        <div class="provider-section">
            <h4>API Keys</h4>
            <ul class="provider-detail-list">
                {{#if apikeys.length}}
                    {{#each apikeys}}
                        <li class="provider-detail-item" data-key-id="{{this.id}}">
                            
                            <span class="provider-detail-item-name">{{defaultIfEmpty this.comment 'API Key'}}</span>
                            <div class="table-item-actions">
                                <button class="btn btn-xs btn-danger delete-apikey-btn" title="Delete API Key"><i class="fa fa-trash"></i></button>
                            </div>
                            <div class="apikey-stats">
                                <span title="Total LLM Queries">Q: {{formatNumber this.total_llm_queries}}</span>
                                <span title="Total Prompt Tokens">P: {{formatNumber this.total_prompt_tokens}}</span>
                                <span title="Total Completion Tokens">C: {{formatNumber this.total_completion_tokens}}</span>
                            </div>
                        </li>
                    {{/each}}
                {{else}}
                    <li class="no-items-message">No API keys configured.</li>
                {{/if}}
            </ul>
            <div class="add-item-container">
                <button class="btn btn-xs btn-default add-apikey-btn" title="Add API Key"><i class="fa fa-plus"></i> Add Key</button>
            </div>
        </div>
    </div>
</div>`);


function renderProviderList(providers) {
    const container = document.getElementById('tabContent_providers'); 
    if (!container) return;

    const body = container.querySelector('#providers-list-body');
    if (!body) return;
    body.innerHTML = ''; // Clear existing content

    // Ensure the add provider button in the new tab header is correctly wired
    const addProviderBtn = container.querySelector('#add-provider-btn');
    if (addProviderBtn) {
        addProviderBtn.onclick = function() {
            const addProviderModal = document.getElementById('addProviderModal');
            if (addProviderModal) {
                // Clear form before showing
                document.getElementById('providerName').value = '';
                document.getElementById('providerUrl').value = '';
                addProviderModal.style.display = 'block';
            }
        };
    }


    if (!providers || providers.length === 0) {
        body.innerHTML = '<div class="alert alert-info" role="alert">No API providers found. Click the "+" button to add one.</div>';
        window.allAvailableModels = []; // Clear models if no providers
        return;
    }

    // Aggregate all models into the global list
    window.allAvailableModels = [];
    providers.forEach(provider => {
        provider.models.forEach(model => {
            window.allAvailableModels.push(model);
        });
    });

    providers.forEach(provider => {
        renderSingleProvider(provider, body);
    });
}

function renderSingleProvider(provider, containerElement) {    
    const existingBlock = containerElement.querySelector(`.provider-block[data-provider-id="${provider.id}"]`);
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML =  singleProviderBlockTemplate(provider).trim();
    const newProviderBlock = tempDiv.firstElementChild;
    if (existingBlock) {
        existingBlock.replaceWith(newProviderBlock);
    } else {
        containerElement.appendChild(newProviderBlock);
    }
}

// Event delegation for the entire providers tab content
document.addEventListener('DOMContentLoaded', function() {
    const container = document.getElementById('tabContent_providers'); 
    if (!container) return;

    //console.log("Attaching click/keypress event listener to #tabContent_providers");
    container.addEventListener('click', function(event) {
        //console.log("Click event detected on #tabContent_providers. Target:", event.target);
        const target = event.target;
        const providerBlock = target.closest('.provider-block'); // Main provider block
        
        if (!providerBlock) return; // Not a click on a provider block

        const targetProviderId = providerBlock.dataset.providerId;

        // Edit Provider (now only via modal, if needed, not in list item directly)
        // This specific 'edit-provider-btn' logic is removed from click handler
        // If a global 'edit provider' button existed elsewhere, it would trigger a modal.

        // Delete Provider button
        if (target.closest('.delete-provider-btn')) {
            //console.log("Delete provider button clicked for provider ID:", targetProviderId);
            const providerId = targetProviderId;
            const providerName = providerBlock.querySelector('.provider-name').textContent;
            
            if (confirm(`Are you sure you want to delete the provider "${providerName}"?`)) {
                if (websocket && websocket.readyState === WebSocket.OPEN) {
                    websocket.send(JSON.stringify({
                        type: 'delete_provider',
                        payload: {
                            provider_pk: providerId
                        }
                    }));
                } else {
                    addToConsoleArea('WebSocket is not connected.', 'error');
                }
            }
        }

        // Add Model button
        if (target.closest('.add-model-btn')) {
            //console.log("Add model button clicked for provider ID:", targetProviderId);
            const modelInput = providerBlock.querySelector('.add-model-input');
            const modelName = modelInput.value.trim();
            if (!modelName) {
                addToConsoleArea('Model name cannot be empty.', 'error');
                return;
            }
            if (websocket && websocket.readyState === WebSocket.OPEN) {
                websocket.send(JSON.stringify({
                    type: 'create_provider_model',
                    payload: {
                        provider_pk: targetProviderId,
                        model_name: modelName
                    }
                }));
                modelInput.value = ''; // Clear input after sending
            } else {
                addToConsoleArea('WebSocket is not connected.', 'error');
            }
        }
        
        // Add API Key button
        if (target.closest('.add-apikey-btn')) {
            //console.log("Add API Key button clicked for provider ID:", targetProviderId);
            const addApiKeyModal = document.getElementById('addApiKeyModal');
            if (addApiKeyModal) {
                document.getElementById('addApiKeyProviderId').value = targetProviderId;
                document.getElementById('addApiKeyProviderName').textContent = providerBlock.querySelector('.provider-name').textContent;
                document.getElementById('apiKeyInput').value = '';
                document.getElementById('apiKeyComment').value = '';
                addApiKeyModal.style.display = 'block';
            }
        }

        // Delete API Key button
        if (target.closest('.delete-apikey-btn')) {
            //console.log("Delete API Key button clicked for provider ID:", targetProviderId);
            const apiKeyItem = target.closest('.provider-detail-item');
            const keyId = apiKeyItem.dataset.keyId;
            const keyComment = apiKeyItem.querySelector('.provider-detail-item-name').textContent;
            
            if (confirm(`Are you sure you want to delete the API key "${keyComment}"?`)) {
                if (websocket && websocket.readyState === WebSocket.OPEN) {
                    websocket.send(JSON.stringify({
                        type: 'delete_provider_apikey',
                        payload: {
                            provider_pk: targetProviderId,
                            apikey_pk: keyId
                        }
                    }));
                } else {
                    addToConsoleArea('WebSocket is not connected.', 'error');
                }
            }
        }

        // Delete Model button
        if (target.closest('.delete-model-btn')) {
            //console.log("Delete Model button clicked for provider ID:", targetProviderId);
            const modelItem = target.closest('.provider-detail-item');
            const modelId = modelItem.dataset.modelId;
            const modelName = modelItem.querySelector('.provider-detail-item-name').textContent;
            
            if (confirm(`Are you sure you want to delete the model "${modelName}"?`)) {
                if (websocket && websocket.readyState === WebSocket.OPEN) {
                    websocket.send(JSON.stringify({
                        type: 'delete_provider_model',
                        payload: {
                            provider_pk: targetProviderId,
                            model_pk: modelId
                        }
                    }));
                } else {
                    addToConsoleArea('WebSocket is not connected.', 'error');
                }
            }
        }
    });

    // Handle Enter key for Add Model Input using event delegation
    container.addEventListener('keypress', function(event) {
        const target = event.target;
        if (target.classList.contains('add-model-input') && event.key === 'Enter') {
            event.preventDefault(); // Prevent form submission
            const providerBlock = target.closest('.provider-block');
            if (!providerBlock) return;
            const targetProviderId = providerBlock.dataset.providerId;
            const modelName = target.value.trim();
            if (!modelName) {
                addToConsoleArea('Model name cannot be empty.', 'error');
                return;
            }
            if (websocket && websocket.readyState === WebSocket.OPEN) {
                websocket.send(JSON.stringify({
                    type: 'create_provider_model',
                    payload: {
                        provider_pk: targetProviderId,
                        model_name: modelName
                    }
                }));
                target.value = ''; // Clear input after sending
            } else {
                addToConsoleArea('WebSocket is not connected.', 'error');
            }
        }
    });
})