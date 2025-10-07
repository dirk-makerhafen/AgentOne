// This file manages the rendering of PythonToolVar (VARS) update messages.

function renderPythonToolVarMessage(payload, instancePk) {
    const pythonToolVarGroupTemplate = getTemplate('PythonVarLogTemplate');

    if (!instancePk) {
        addToClientLog("renderPythonToolVarMessage: instancePk is required.", 'error');
        return;
    }

    const toolCallId = payload.toolCall_id;
    const instanceLogArea = document.getElementById(`logArea_${instancePk}`);
    if (!instanceLogArea) {
        addToClientLog(`Log area for instance ${instancePk} not found.`, 'error');
        return;
    }
    
    let groupContainer = instanceLogArea.querySelector(`#pyvar_group_${toolCallId}`);
    
    let nice_string;
    if (typeof payload.value === "string"){
        nice_string = payload.value;
    } else {
        nice_string = JSON.stringify(payload.value, null, 2);
    }

    if (groupContainer) {
        // --- Group already exists, just update it ---
        const header = groupContainer.querySelector('.message-header');
        const countSpan = header.querySelector('.pyvar-count');
        const keysSpan = header.querySelector('.pyvar-keys');
        const detailsContainer = groupContainer.querySelector('.pyvar-details-container');

        // Update count in header
        countSpan.textContent = parseInt(countSpan.textContent, 10) + 1;

        // Append new key to the summary in header
        keysSpan.insertAdjacentHTML('beforeend', `, <span>${payload.key}</span>`);

        // Create and append the new structured detail item to the body
        const detailItem = document.createElement('div');
        detailItem.className = 'pyvar-detail-item';
        detailItem.innerHTML = `
            <div class="pyvar-detail-key"><span>'${payload.key}'</span></div>
            <div class="pyvar-detail-value"><pre>${nice_string}</pre></div>
        `;
        detailsContainer.appendChild(detailItem);
        
        // Preserve expanded state
        const detailsView = groupContainer.querySelector('.message-content');
        if (!detailsView.classList.contains('hidden')) {
            instanceLogArea.scrollTop = instanceLogArea.scrollHeight; // Scroll to bottom if expanded
        }

    } else {
        // --- Group doesn't exist, create a new one ---
        payload.created_at_formatted_time = new Date(payload.created_at).toLocaleTimeString();
        payload.nice_string = nice_string;
        payload.instancePk = instancePk; // Pass instancePk to the template
        
        const html = pythonToolVarGroupTemplate(payload);
        
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html.trim();
        const newElement = tempDiv.firstChild;
        addToChatArea(newElement, instancePk);
    }
};