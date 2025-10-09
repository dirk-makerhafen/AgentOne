// This file manages the rendering and interactions for the Providers list tab.

let providerListItemTemplate;

function initializeProviderTemplates() {
    providerListItemTemplate = getTemplate('TabProvidersListItemTemplate');
    Handlebars.registerPartial('ProviderListItemTemplate', providerListItemTemplate);
    Handlebars.registerPartial('AddProviderModalTemplate', getTemplate('TabProvidersAddProviderModal'));
    Handlebars.registerPartial('AddApiKeyModalTemplate', getTemplate('TabProvidersAddApiKey'));
    // Register new partials for individual items
    Handlebars.registerPartial('TabProvidersModelItemTemplate', getTemplate('TabProvidersModelItemTemplate'));
    Handlebars.registerPartial('TabProvidersApiKeyItemTemplate', getTemplate('TabProvidersApiKeyItemTemplate'));
}

function renderProviderList(providers) {
    const container = document.getElementById('tabContent_providers'); 
    if (!container) return;

    const body = container.querySelector('#providers-list-body');
    if (!body) return;
    body.innerHTML = '';

    if (!providers || providers.length === 0) {
        body.innerHTML = '<div class="alert alert-info" role="alert">No API providers found. Click the "+" button to add one.</div>';
        window.allAvailableModels = [];
        return;
    }

    window.allAvailableModels = [];
    providers.forEach(provider => {
        if(provider.models) {
            provider.models.forEach(model => {
                window.allAvailableModels.push(model);
            });
        }
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

function renderSingleAiModel(model) {
    const providerBlock = document.getElementById(`provider_${model.apiProvider_id}`);
    if (!providerBlock) return;

    const modelList = providerBlock.querySelector('.provider-section:first-of-type .provider-detail-list');
    if (!modelList) return;

    const existingModelItem = modelList.querySelector(`li[data-model-id="${model.id}"]`);
    const modelItemTemplate = getTemplate('TabProvidersModelItemTemplate');
    const modelHtml = modelItemTemplate(model);

    const noItemsMsg = modelList.querySelector('.no-items-message');
    if (noItemsMsg) noItemsMsg.remove();

    if (existingModelItem) {
        existingModelItem.outerHTML = modelHtml;
    } else {
        modelList.insertAdjacentHTML('beforeend', modelHtml);
    }
}

function removeAiModel(payload) {
    const providerBlock = document.getElementById(`provider_${payload.provider_pk}`);
    if (!providerBlock) return;

    const modelItem = providerBlock.querySelector(`li[data-model-id="${payload.model_pk}"]`);
    if (modelItem) {
        modelItem.remove();
    }

    const modelList = providerBlock.querySelector('.provider-section:first-of-type .provider-detail-list');
    if (modelList && modelList.children.length === 0) {
        modelList.innerHTML = '<li class="no-items-message">No models configured.</li>';
    }
}

function renderSingleApiKey(apiKey) {
    const providerBlock = document.getElementById(`provider_${apiKey.apiProvider_id}`);
    if (!providerBlock) return;

    const apiKeyList = providerBlock.querySelector('.provider-section:last-of-type .provider-detail-list');
    if (!apiKeyList) return;

    const existingApiKeyItem = apiKeyList.querySelector(`li[data-key-id="${apiKey.id}"]`);
    const apiKeyItemTemplate = getTemplate('TabProvidersApiKeyItemTemplate');
    const apiKeyHtml = apiKeyItemTemplate(apiKey);

    const noItemsMsg = apiKeyList.querySelector('.no-items-message');
    if (noItemsMsg) noItemsMsg.remove();

    if (existingApiKeyItem) {
        existingApiKeyItem.outerHTML = apiKeyHtml;
    } else {
        apiKeyList.insertAdjacentHTML('beforeend', apiKeyHtml);
    }
}

function removeApiKey(payload) {
    const providerBlock = document.getElementById(`provider_${payload.provider_pk}`);
    if (!providerBlock) return;
    
    const apiKeyItem = providerBlock.querySelector(`li[data-key-id="${payload.key_pk}"]`);
    if (apiKeyItem) {
        apiKeyItem.remove();
    }

    const apiKeyList = providerBlock.querySelector('.provider-section:last-of-type .provider-detail-list');
    if (apiKeyList && apiKeyList.children.length === 0) {
        apiKeyList.innerHTML = '<li class="no-items-message">No API keys configured.</li>';
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
        
        const addProviderModalTemplate = getTemplate('TabProvidersAddProviderModal');
        const addApiKeyModalTemplate = getTemplate('TabProvidersAddApiKey');
        document.body.insertAdjacentHTML('beforeend', addProviderModalTemplate({}));
        document.body.insertAdjacentHTML('beforeend', addApiKeyModalTemplate({}));
    }
    apiProviderApi.list();
}

// --- Provider Actions ---

function providerOpenAddModal(event) {
    event.stopPropagation();
    const addProviderModal = document.getElementById('addProviderModal');
    if (addProviderModal) {
        addProviderModal.querySelector('#addProviderForm').reset();
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
    apiProviderApi.create(providerName, providerUrl || null);
    providerCloseAddModal(event);
}

function providerDelete(event, providerId, providerName) {
    event.stopPropagation();
    if (confirm(`Are you sure you want to delete the provider "${providerName}"?`)) {
        apiProviderApi.delete(providerId);
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
    aiModelApi.create(providerId, modelName);
    modelInput.value = ''; // Clear the input after adding
}

function modelAddKeypress(event, providerId) {
    if (event.key === 'Enter') {
        event.preventDefault();
        modelAdd(event, providerId);
    }
}

function modelDelete(event, providerId, modelId, modelName) {
    event.stopPropagation();
    if (confirm(`Are you sure you want to delete the model "${modelName}"?`)) {
        aiModelApi.delete(providerId, modelId);
    }
}

// --- API Key Actions ---

function apiKeyOpenAddModal(event, providerId, providerName) {
    event.stopPropagation();
    const addApiKeyModal = document.getElementById('addApiKeyModal'); 
    if (addApiKeyModal) {
        addApiKeyModal.querySelector('#addApiKeyProviderId').value = providerId;
        addApiKeyModal.querySelector('#addApiKeyProviderName').textContent = providerName;
        addApiKeyModal.querySelector('#addApiKeyForm').reset();
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
    apiKeyApi.create(providerId, apiKey, comment || null);
    apiKeyCloseAddModal(event);
}

function apiKeyDelete(event, providerId, keyId, keyComment) {
    event.stopPropagation();
    if (confirm(`Are you sure you want to delete the API key "${keyComment || 'this key'}"?`)) {
        apiKeyApi.delete(providerId, keyId);
    }
}
