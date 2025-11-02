// This file manages the rendering and interaction of the main tab content for an agent instance.

function renderAgentInstanceTabContent(instancePk, parentPanelId) {
    const agentInstanceTabContentTemplate = getTemplate('TabInstanceTemplate');
    const container = document.getElementById(parentPanelId);
    const tabContentId = `tabContent_agentInstance_${instancePk}`;
    
    if (document.getElementById(tabContentId)) return; 

    const html = agentInstanceTabContentTemplate({ instancePk: instancePk });
    container.insertAdjacentHTML('beforeend', html);
    
    const newTabContentElement = document.getElementById(tabContentId);
    if (newTabContentElement && typeof initializeSplitForContainer === 'function') {
        initializeSplitForContainer(newTabContentElement);
    }
    
    initializeLogFilterControlsForInstance(instancePk, newTabContentElement);
    showSidebarTabForInstance('filesystem', newTabContentElement.querySelector(`.sidebar-tab-btn[data-tab-name="filesystem"]`), instancePk);

    const newLogArea = newTabContentElement.querySelector(`#logArea_${instancePk}`);
    if (newLogArea && typeof attachLogAreaScrollListener === 'function') {
        attachLogAreaScrollListener(newLogArea, instancePk);
    }

    // Attach event listeners for the new rich-text input
    const messageInput = newTabContentElement.querySelector(`#messageInput_${instancePk}`);
    if (messageInput) {
        messageInput.addEventListener('paste', handlePaste);
        messageInput.addEventListener('drop', handleDrop);
        messageInput.addEventListener('dragover', (e) => e.preventDefault()); // Necessary to allow drop
    }
}

function selectAgentInstanceTab(instancePk, instanceName, targetPanelId = 'mainTabPanel') {
    document.querySelectorAll('.sidebar-instance').forEach(el => el.classList.remove('selected-instance'));
    const sidebarItem = document.getElementById(`agent_instance_${instancePk}`);
    if (sidebarItem) sidebarItem.classList.add('selected-instance');

    const tabButtonId = `tabButton_agentInstance_${instancePk}`;
    const tabContentId = `tabContent_agentInstance_${instancePk}`;
    
    if (document.getElementById(tabButtonId)) {
        const existingParentPanelId = document.getElementById(tabButtonId).closest('.resizable-panel.flex-column').id;
        openMainTab(null, tabContentId, existingParentPanelId);
    } else {
        const targetPanel = document.getElementById(targetPanelId);
        if (!targetPanel) return;

        const newTabButton = document.createElement('button');
        newTabButton.id = tabButtonId;
        newTabButton.className = 'tab-button';
        newTabButton.setAttribute('draggable', 'true');
        newTabButton.ondragstart = (event) => dragTab(event, tabButtonId, tabContentId);
        newTabButton.innerHTML = `<span><i class="fa fa-user-circle-o"></i> ${instanceName}</span><i class="fa fa-times close-tab-btn" onclick="event.stopPropagation(); closeMainTab('${tabContentId}')"></i>`;
        newTabButton.setAttribute('onclick', `openMainTab(event, '${tabContentId}', '${targetPanelId}'); window.currentAgentInstancePk = ${instancePk};`);

        const targetTabBar = targetPanel.querySelector('.tab-bar');
        const splitControls = targetTabBar.querySelector('.split-controls-container');
        targetTabBar.insertBefore(newTabButton, splitControls);

        renderAgentInstanceTabContent(instancePk, targetPanelId);
        openMainTab(null, tabContentId, targetPanelId);
        window.currentAgentInstancePk = instancePk;

        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({ type: 'subscribe', payload: { instance_pk: instancePk } }));
            conversationApi.listMessages(instancePk, null, 20);
            agentInstanceApi.get(instancePk);
            agentInstanceApi.getSubAgents(instancePk);
        }
    }
}

// --- Multi-modal Input Handlers ---

function handlePaste(event) {
    // Prevent the default paste action to stop rich text from being inserted.
    event.preventDefault();

    const items = (event.clipboardData || window.clipboardData).items;
    let foundImage = false;

    // First, check for images and handle them.
    for (let i = 0; i < items.length; i++) {
        if (items[i].type.indexOf('image') !== -1) {
            const file = items[i].getAsFile();
            if (file) {
                insertImageFile(file, event.target);
                foundImage = true;
            }
        }
    }

    // If no image was pasted, handle plain text.
    if (!foundImage) {
        const text = (event.clipboardData || window.clipboardData).getData('text/plain');
        if (text) {
            // Use execCommand to insert text at the cursor position. This is a widely supported
            // method for inserting plain text into a contenteditable element.
            document.execCommand('insertText', false, text);
        }
    }
}

function handleDrop(event) {
    event.preventDefault();
    const files = event.dataTransfer.files;
    for (let i = 0; i < files.length; i++) {
        if (files[i].type.indexOf('image') !== -1) {
            insertImageFile(files[i], event.target);
        }
    }
}

function insertImageFile(file, targetEditor) {
    const reader = new FileReader();
    reader.onload = function(event) {
        const img = document.createElement('img');
        img.src = event.target.result;
        targetEditor.focus();
        const selection = window.getSelection();
        const range = selection.getRangeAt(0);
        range.deleteContents();
        range.insertNode(img);
        range.collapse(false); // Move cursor after the image
    };
    reader.readAsDataURL(file);
}

// --- Sending Logic ---

function sendMessage(event, instancePk) {
    event.preventDefault();
    const messageInput = document.querySelector(`#messageInput_${instancePk}`);
    if (!messageInput) return;

    const parts = [];
    messageInput.childNodes.forEach(node => {
        if (node.nodeType === Node.TEXT_NODE) {
            const text = node.textContent.trim();
            if (text) {
                parts.push({ type: "TEXT", content: text });
            }
        } else if (node.nodeType === Node.ELEMENT_NODE && node.tagName === 'IMG') {
            parts.push({ type: 'image', content: node.src }); // src is the Base64 data URL
        } else if (node.nodeType === Node.ELEMENT_NODE && node.tagName === 'DIV') {
            // Handle text within divs (from pressing enter)
             const text = node.textContent.trim();
            if (text) {
                parts.push({ type: "TEXT", content: text });
            }
        }
    });

    conversationApi.addMessage(instancePk, parts);
    if (parts.length > 0) {
        messageInput.innerHTML = ''; // Clear the input
        messageInput.focus();
    }
}

function handleMessageInputKeydown(event, instancePk) {
    // Submit on Ctrl+Enter
    if (event.key === 'Enter' && event.ctrlKey) {
        event.preventDefault();
        sendMessage(event, instancePk);
    }
}


// --- Other Functions ---

function initializeLogFilterControlsForInstance(instancePk, tabContentElement) {
    const logAreaContainer = tabContentElement.querySelector(`#logArea_${instancePk}`);
    if (!logAreaContainer) return;

    let filterControls = logAreaContainer.querySelector('.log-filter-controls');
    if (!filterControls) {
        filterControls = document.createElement('div');
        filterControls.id = `log-filter-controls_${instancePk}`;
        filterControls.className = 'log-filter-container';
        logAreaContainer.prepend(filterControls);
    }

    filterControls.innerHTML = `
        <button class="log-filter-btn active" data-log-type="conversation" title="Toggle User/Agent Messages"><i class="fa fa-comments-o"></i></button>
        <button class="log-filter-btn" data-log-type="tool" title="Toggle Tool Calls & Responses"><i class="fa fa-wrench"></i></button>
        <button class="log-filter-btn active" data-log-type="fs" title="Toggle Filesystem Logs"><i class="fa fa-folder-open-o"></i></button>
        <button class="log-filter-btn active" data-log-type="llm" title="Toggle LLM Queries/Responses"><i class="fa fa-cogs"></i></button>
        <button class="log-filter-btn active" data-log-type="debug" title="Toggle Debug Logs"><i class="fa fa-bug"></i></button>
        <button class="log-filter-btn active" data-log-type="pyvar" title="Toggle VARS Updates"><i class="fa fa-code"></i></button>
    `;

    filterControls.querySelectorAll('.log-filter-btn').forEach(button => {
        const logType = button.dataset.logType;
        button.onclick = (event) => {
            event.preventDefault();
            button.classList.toggle('active');
            logAreaContainer.classList.toggle(`hide-${logType}`);
        };
    });
}

function showSidebarTabForInstance(tabName, clickedButton, instancePk) {
    const sidebarRight = document.getElementById(`sidebar-right_${instancePk}`);
    if (!sidebarRight) return;

    sidebarRight.querySelectorAll('.sidebar-tab-content').forEach(tab => tab.style.display = 'none');
    sidebarRight.querySelectorAll('.sidebar-tab-btn').forEach(btn => btn.classList.remove('active'));

    const tabContent = document.getElementById(`sidebar-tab-${tabName}_${instancePk}`);
    if (tabContent) tabContent.style.display = 'flex';
    if (clickedButton) clickedButton.classList.add('active');

    switch (tabName) {
        case 'filesystem': filesystemApi.list(instancePk); break;
        case 'memory': memoryApi.list(instancePk); break;
        case 'vars': agentInstanceApi.getVars(instancePk); break;
        case 'permissions': a2aPermissionsApi.list(instancePk); break;
        case 'settings': agentInstanceApi.get(instancePk); break;
        case 'subagents': agentInstanceApi.getSubAgents(instancePk); break;
    }
}

function updateAgentInstanceStatusBar(instancePk, payload) {
    const statusBar = document.querySelector(`#agent-status-bar_${instancePk}`);
    const statusText = document.querySelector(`#agent-status-text_${instancePk}`);
    if (statusBar && statusText) {
        statusText.textContent = payload.status_display;
        statusBar.className = `agent-status-bar status-bg-${payload.status}`;
    }
}

function requestAgentInstanceDeletion(event, instancePk, instanceName) {
    event.preventDefault();
    event.stopPropagation();
    if (confirm(`Are you sure you want to delete agent instance "${instanceName}" (ID: ${instancePk})?`)) {
        agentInstanceApi.delete(instancePk);
        closeMainTab(`tabContent_agentInstance_${instancePk}`);
    }
}
