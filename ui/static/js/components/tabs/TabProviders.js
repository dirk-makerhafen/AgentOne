// This file manages the rendering and interactions for the Providers list tab.

let providerListItemTemplate;
let addProviderModalTemplate;
let editProviderModalTemplate;
let addApiKeyModalTemplate;

function initializeProviderTemplates() {
    providerListItemTemplate = getTemplate('TabProvidersListItemTemplate');
    addProviderModalTemplate = getTemplate('TabProvidersAddProviderModal');
    editProviderModalTemplate = getTemplate('TabProvidersEditProviderModal');
    addApiKeyModalTemplate = getTemplate('TabProvidersAddApiKey');
}

function renderProviderList(providers) {
    if (!providerListItemTemplate) {
        initializeProviderTemplates();
    }
    const container = document.getElementById('tabContent_providers'); 
    if (!container) return;

    const body = container.querySelector('#providers-list-body');
    if (!body) return;
    body.innerHTML = ''; // Clear existing content

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
    tempDiv.innerHTML =  providerListItemTemplate(provider).trim();
    const newProviderBlock = tempDiv.firstElementChild;
    if (existingBlock) {
        existingBlock.replaceWith(newProviderBlock);
    } else {
        containerElement.appendChild(newProviderBlock);
    }
}


function requestProviderList() {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: 'request_provider_list' }));
    }
}

function openProvidersTab(targetPanelId = 'mainTabPanel') {
    const tabContentId = 'tabContent_providers';
    const tabName = 'Providers';

    const existingTab = document.getElementById(tabContentId);
    if (existingTab) {
        openMainTab(null, tabContentId, targetPanelId);
    } else {
        initializeProviderTemplates();
        const tabProvidersTemplate = getTemplate('TabProvidersTemplate');
        const tabContentHtml = tabProvidersTemplate({});
        openMainTab(null, tabContentId, targetPanelId, tabName, tabContentHtml);
        
        // Modals need to be appended to the body to avoid stacking context issues
        const addProviderModalTemplate = getTemplate('TabProvidersAddProviderModal');
        const addApiKeyModalTemplate = getTemplate('TabProvidersAddApiKey');
        document.body.insertAdjacentHTML('beforeend', addProviderModalTemplate({}));
        document.body.insertAdjacentHTML('beforeend', addApiKeyModalTemplate({}));
    }
    requestProviderList();
}

// --- Provider Actions ---

function providerOpenAddModal(event) {
    event.stopPropagation();
    const addProviderModal = document.getElementById('addProviderModal');
    if (addProviderModal) {
        addProviderModal.querySelector('#addProviderForm').reset(); // Clear form before showing
        addProviderModal.style.display = 'block';
    }
}

function providerCloseAddModal(event) {
    event.stopPropagation();
    const addProviderModal = document.getElementById('addProviderModal');
    if (addProviderModal) {
        addProviderModal.style.display = 'none';
    }
}

function providerSave(event) {
    event.stopPropagation();
    const addProviderModal = document.getElementById('addProviderModal');
    const providerName = addProviderModal.querySelector('#providerName').value.trim();
    const providerUrl = addProviderModal.querySelector('#providerUrl').value.trim();

    if (!providerName) {
        addToClientLog('Provider Name is required.', 'error');
        return;
    }

    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'create_provider',
            payload: { name: providerName, url: providerUrl || null }
        }));
        addToClientLog(`Client: Requesting creation of provider "${providerName}".`, 'info');
    } else {
        addToClientLog('WebSocket not connected. Cannot create provider.', 'error');
    }
    providerCloseAddModal(event); // Close modal
}

function providerDelete(event, providerId, providerName) {
    event.stopPropagation();
    if (confirm(`Are you sure you want to delete the provider "${providerName}"?`)) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'delete_provider',
                payload: {
                    provider_pk: providerId
                }
            }));
            addToClientLog(`Client: Requesting deletion of provider ${providerId} ("${providerName}").`, 'info');
        } else {
            addToClientLog('WebSocket is not connected. Cannot delete provider.', 'error');
        }
    }
}

// --- Model Actions ---

function modelAdd(event, providerId) {
    event.stopPropagation();
    const providerBlock = event.currentTarget.closest('.provider-block');
    const modelInput = providerBlock.querySelector('.add-model-input');
    const modelName = modelInput.value.trim();
    if (!modelName) {
        addToClientLog('Model name cannot be empty.', 'error');
        return;
    }
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'create_provider_model',
            payload: {
                provider_pk: providerId,
                model_name: modelName
            }
        }));
        addToClientLog(`Client: Requesting creation of model "${modelName}" for provider ${providerId}.`, 'info');
        modelInput.value = ''; // Clear input after sending
    } else {
        addToClientLog('WebSocket is not connected. Cannot create model.', 'error');
    }
}

function modelAddKeypress(event, providerId) {
    if (event.key === 'Enter') {
        event.preventDefault(); // Prevent form submission
        modelAdd(event, providerId); // Call the modelAdd function
    }
}

function modelDelete(event, providerId, modelId, modelName) {
    event.stopPropagation();
    if (confirm(`Are you sure you want to delete the model "${modelName}"?`)) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'delete_provider_model',
                payload: {
                    provider_pk: providerId,
                    model_pk: modelId
                }
            }));
            addToClientLog(`Client: Requesting deletion of model ${modelId} ("${modelName}") for provider ${providerId}.`, 'info');
        } else {
            addToClientLog('WebSocket is not connected. Cannot delete model.', 'error');
        }
    }
}


// --- API Key Actions ---

function apiKeyOpenAddModal(event, providerId, providerName) {
    event.stopPropagation();
    const addApiKeyModal = document.getElementById('addApiKeyModal'); 
    if (addApiKeyModal) {
        addApiKeyModal.querySelector('#addApiKeyProviderId').value = providerId;
        addApiKeyModal.querySelector('#addApiKeyProviderName').textContent = providerName;
        addApiKeyModal.querySelector('#addApiKeyForm').reset(); // Clear form before showing
        addApiKeyModal.style.display = 'block';
    }
}

function apiKeyCloseAddModal(event) {
    event.stopPropagation();
    const addApiKeyModal = document.getElementById('addApiKeyModal');
    if (addApiKeyModal) {
        addApiKeyModal.style.display = 'none';
    }
}

function apiKeySave(event) {
    event.stopPropagation();
    const addApiKeyModal = document.getElementById('addApiKeyModal');
    const providerId = addApiKeyModal.querySelector('#addApiKeyProviderId').value;
    const apiKey = addApiKeyModal.querySelector('#apiKeyInput').value.trim();
    const comment = addApiKeyModal.querySelector('#apiKeyComment').value.trim();

    if (!apiKey) {
        addToClientLog('API Key is required.', 'error');
        return;
    }

    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'create_provider_apikey',
            payload: { provider_pk: providerId, key: apiKey, comment: comment || null }
        }));
        addToClientLog(`Client: Requesting creation of API key for provider ${providerId}.`, 'info');
    } else {
        addToClientLog('WebSocket is not connected. Cannot add API key.', 'error');
    }
    apiKeyCloseAddModal(event); // Close modal
}

function apiKeyDelete(event, providerId, keyId, keyComment) {
    event.stopPropagation();
    if (confirm(`Are you sure you want to delete the API key "${keyComment}"?`)) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'delete_provider_apikey',
                payload: {
                    provider_pk: providerId,
                    apikey_pk: keyId
                }
            }));
            addToClientLog(`Client: Requesting deletion of API key ${keyId} for provider ${providerId}.`, 'info');
        } else {
            addToClientLog('WebSocket is not connected. Cannot delete API key.', 'error');
        }
    }
}
