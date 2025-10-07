const pythonToolVarGroupTemplate = Handlebars.compile(`
<div id="pyvar_group_{{toolCall_id}}" class="conversation-log-item log-type-pyvar" data-toolcall-id="{{toolCall_id}}"
     data-id="{{toolCall_id}}" data-created-at="{{created_at}}">
    <div class="message-header">
        <strong>[{{created_at_formatted_time}}]</strong>
        <strong><span class="pyvar-count">1</span> VARS Update:</strong>
        <span class="pyvar-keys"><span>{{key}}</span></span>
        <button class="btn btn-xs btn-default log-btn" onclick="event.preventDefault(); toggleElementVisibility('pyvar_full_{{toolCall_id}}', {{instancePk}})">
            <i class="fa fa-plus"></i> More
        </button>
    </div>
    <div id="pyvar_full_{{toolCall_id}}" class="message-content hidden">
        <div class="pyvar-details-container">
            <!-- First item is rendered here, subsequent items are appended by JS -->
            <div class="pyvar-detail-item">
                <div class="pyvar-detail-key"><p>{{key}}</p></div>
                <div class="pyvar-detail-value"><pre>{{nice_string}}</pre></div>
            </div>
        </div>
        <button class="btn btn-xs btn-default log-btn" onclick="event.preventDefault(); toggleElementVisibility('pyvar_full_{{toolCall_id}}', {{instancePk}})">
            <i class="fa fa-minus"></i> Hide
        </button>
    </div>
</div>`);

function renderPythonToolVarMessage(payload, instancePk) {
    if (!instancePk) {
        console.error("renderPythonToolVarMessage: instancePk is required.");
        return;
    }

    const toolCallId = payload.toolCall_id;
    const instanceLogArea = document.getElementById(`logArea_${instancePk}`);
    if (!instanceLogArea) {
        console.error(`Log area for instance ${instancePk} not found.`);
        return;
    }
    
    let groupContainer = instanceLogArea.querySelector(`#pyvar_group_${toolCallId}`);
    
    let nice_string;
    if (typeof payload.value === "string"){
            nice_string = payload.value;
    }else{
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

    } else {
        // --- Group doesn't exist, create a new one ---
        payload.created_at_formatted_time = new Date(payload.created_at).toLocaleTimeString();
        payload.nice_string = nice_string;
        payload.instancePk = instancePk; // Pass instancePk to the template
        
        const html = pythonToolVarGroupTemplate(payload);
        
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html.trim();
        const newElement = tempDiv.firstChild;
        appendLog(newElement, instancePk);
    }
};
