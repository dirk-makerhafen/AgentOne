

const filesystemMessageTemplate = Handlebars.compile(`
<div id="filesystem_message_{{message.object}}_{{message.id}}" class="conversation-log-item log-type-fs filesystem-log-item"
     data-id="{{message.id}}"
     data-created-at="{{message.created_at}}"
     data-object="{{message.object}}"
     data-action="{{message.action}}"
     data-path="{{message.path}}"
     data-load-mode="{{message.load_mode}}" {{!-- Added for load mode tracking --}}
     {{#unless (isUndefined message.content)}}
     data-content="{{escape message.content}}"
     data-prev-content="{{escape message.prev_content}}"
     data-summary="{{escape message.summary}}" {{!-- Added for summary content --}}
     {{/unless}}
     data-is-directory="{{message.is_directory}}">
    <div class="message-header">
        <strong>[{{formattedTimestamp}}]</strong> <strong>{{message.object}} {{message.action}}:</strong> {{message.path}}
        {{#if (eq message.load_mode "summary")}}
            <button class="btn btn-xs btn-default log-btn log-btn-right" onclick="event.preventDefault(); toggleFilesystemSummary('filesystem_message_{{message.object}}_{{message.id}}', '{{message.agentInstance_id}}');"><i class="fa fa-list-ul"></i> Summary</button>
        {{/if}}
        
        {{#if (eq message.action "unload")}}
            <button class="btn btn-xs btn-default log-btn log-btn-right" onclick="event.stopPropagation(); loadFileFromLog('{{message.path}}', {{message.agentInstance_id}}); " title="Load this file again"><i class="fa fa-upload"></i> Load </button>
        {{else}}
            <button class="btn btn-xs btn-default log-btn" onclick="event.preventDefault(); toggleFilesystemDetails('filesystem_message_{{message.object}}_{{message.id}}', '{{message.agentInstance_id}}');"><i class="fa fa-plus"></i> Details </button>
            {{#unless (eq message.action "load")}}
                <button class="btn btn-xs btn-default log-btn log-btn-right" onclick="event.stopPropagation(); showRevertAllDialog('{{message.id}}', '{{message.path}}', '{{formattedTimestamp}}', {{message.agentInstance_id}}); " title="Revert ALL filesystem changes to this point"><i class="fa fa-history"></i>Undo all</button>
                <button class="btn btn-xs btn-default log-btn log-btn-right" onclick="event.stopPropagation(); showRevertDialog('{{message.id}}', '{{message.action}}', '{{message.path}}', {{message.agentInstance_id}}); " title="Restore previous version of this file"><i class="fa fa-undo"></i> Undo </button>
            {{/unless}}
        {{/if}}
    </div>
    <div class="message-content">
        <div id="filesystem_full_{{message.object}}_{{message.id}}" class="filesystem-content hidden">
            <!-- Diff or content will be loaded here dynamically -->
            <pre>Loading details...</pre>
        </div>
    </div>
</div>`);

function renderFilesystemMessage(payload) {
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = filesystemMessageTemplate({
        formattedTimestamp: new Date(payload.created_at).toLocaleTimeString(),
        message: payload,
    }).trim();
    const newElement = tempDiv.firstChild;

    const existingElement = document.getElementById(newElement.id);
    if (existingElement) {
        const parentLogArea = existingElement.closest(`#logArea_${payload.agentInstance_id}`);
        const detailsView = existingElement.querySelector('.filesystem-content');
        const isExpanded = detailsView && !detailsView.classList.contains('hidden');
        newElement.classList.add('no-animate');
        parentLogArea.replaceChild(newElement, existingElement);
        if (isExpanded) {
            const newItem = document.getElementById(newElement.id); // Get the newly inserted element
            const newDetailsView = newItem.querySelector('.filesystem-content');
            if (newDetailsView) {
                newDetailsView.classList.remove('hidden');
                // If content is now available, render it.
                if (newItem.dataset.content !== undefined) {
                    generateAndInjectFsContent(newItem, newDetailsView);
                }
            }
        }
    } else {
        appendLog(newElement, payload.agentInstance_id);
    }
}

// Global function to toggle and load filesystem details on-demand
function toggleFilesystemDetails(logItemId, instancePk, displayMode = 'full') { // instancePk is now correctly passed
    const item = document.getElementById(logItemId);
    const detailsDiv = item.querySelector('.filesystem-content');
    if (!detailsDiv) return;

    const isCurrentlyHidden = detailsDiv.classList.contains('hidden');
    // If the div is currently hidden, or if we're changing modes, show it.
    // If it's already visible and we're requesting the same mode, toggle it off.
    if (isCurrentlyHidden || detailsDiv.dataset.currentDisplayMode !== displayMode) {
        detailsDiv.classList.remove('hidden');
        detailsDiv.dataset.currentDisplayMode = displayMode; // Store the mode currently displayed
    } else {
        detailsDiv.classList.add('hidden');
        detailsDiv.dataset.currentDisplayMode = '';
        return; // If we just hid it, stop here
    }

    // ...and content hasn't been loaded yet (the data attribute is missing)
    if (item.dataset.content === undefined) {
        const logEntryPk = item.dataset.id;
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'request_fs_content',
                payload: {
                    instance_pk: instancePk, // Use passed instancePk
                    log_entry_pk: logEntryPk
                }
            }));
        } else {
            detailsDiv.innerHTML = '<pre>Error: WebSocket not connected.</pre>';
        }
    } else {
        // Content is already present, render it
        generateAndInjectFsContent(item, detailsDiv, instancePk, displayMode);
    }
};

function toggleFilesystemSummary(logItemId, instancePk) {
    toggleFilesystemDetails(logItemId, instancePk, 'summary');
}


function generateAndInjectFsContent(item, detailsDiv, instancePk, displayMode) {
    // Defensive check: ensure content is loaded before trying to render it.
    if (item.dataset.content === undefined && displayMode !== 'summary') { // Summary might be present even if full content isn't requested/available
        detailsDiv.innerHTML = '<pre>Content not yet loaded.</pre>';
        return;
    }
    
    const path = item.dataset.path;
    const action = item.dataset.action;
    const isDirectory = item.dataset.isDirectory === 'true';

    // Unescape content from data attributes, ensuring newlines are handled correctly.
    const unescape = (str) => {
        if (typeof str !== 'string') {
            return '';
        }
        // Unescape content for the diff library.
        // We normalize both &#10; (LF) and &#13; (CR) to a single '\n'.
        // This handles content from both the old buggy escaper and the new correct one.
        return str.replace(/&apos;/g, "'")
                  .replace(/&quot;/g, '"')
                  .replace(/&#96;/g, '`')
                  .replace(/&#10;/g, '\n')
                  .replace(/&#13;/g, '\n');
    };
    const content = unescape(item.dataset.content);
    const prevContent = unescape(item.dataset.prevContent);
    const summaryContent = unescape(item.dataset.summary); // Always get summary content


    let generatedHtml = '';

    if (action === 'delete') {
        generatedHtml = `<pre>${isDirectory ? 'Directory' : 'File'} '${path}' deleted.</pre>`;
    } else if (displayMode === 'summary') { // If summary mode is explicitly requested
        generatedHtml = `<pre>${summaryContent || 'No summary available.'}</pre>`;
    } else if (content !== prevContent && content) {
        // There is a change, or it's a first load (prevContent is empty). Generate a diff.
        const diff = Diff.createTwoFilesPatch(path, path, prevContent, content);
        generatedHtml = Diff2Html.html(diff, {
            drawFileList: false,
            matching: "lines",
            outputFormat: "side-by-side"
        });
    } else if (content !== undefined && content !== '') {
        // No change, but there is content to display, so show the content.
        if (isDirectory) {
            generatedHtml = `Directory listing unchanged:<br><pre>${content}</pre>`;
        } else {
            generatedHtml = `<pre>${content}</pre>`; // Show content directly
        }
    } else { // content is empty or undefined
        if (isDirectory) {
             generatedHtml = `Directory is empty.`;
        } else {
            generatedHtml = `File is empty or content not available.`;
        }
    }

    // Add hide button
    generatedHtml += '<button class="btn btn-xs btn-default log-btn" onclick="event.preventDefault(); toggleFilesystemDetails(\'' + item.id + '\', \'' + instancePk + '\');"><i class="fa fa-minus"></i>Hide Details</button>';

    detailsDiv.innerHTML = generatedHtml;
}

/**
 * Sends a WebSocket request to perform a direct fs_load tool call.
 * This is triggered from the 'Load' button on 'unload' FsLog entries.
 * @param {string} path The file path to load.
 * @param {number} instancePk The instance PK for scoping.
 */
function loadFileFromLog(path, instancePk) {
    if (!instancePk) {
        addToConsoleArea("Cannot load file: No agent instance selected.", 'warning');
        return;
    }
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        addToConsoleArea(`Client: Requesting to load file: ${path}`, 'info');
        websocket.send(JSON.stringify({
            type: 'direct_tool_call',
            payload: {
                tool_calls: [{ function_name: 'fs_load', arguments: { path: path } }],
                instance_pk: instancePk
            }
        }));



    } else {
        addToConsoleArea("Cannot load file: WebSocket not connected.", 'error');
    }
};



// Global storage for revert modal contexts, keyed by instancePk
window.instanceRevertStates = {};

function showRevertDialog(logEntryId, action, path, instancePk) {
    // Initialize instance-specific state if it doesn't exist
    if (!window.instanceRevertStates[instancePk]) {
        window.instanceRevertStates[instancePk] = {};
    }
    window.instanceRevertStates[instancePk].revertLogEntryId = logEntryId;

    const modal = document.getElementById('revertFileModal');
    const filePathElement = document.getElementById('revertFilePath');
    const commentInput = document.getElementById('revertComment');

    if (modal && filePathElement && commentInput) {
        filePathElement.textContent = path;
        commentInput.value = ''; // Clear previous comment

        // Dynamically set the onclick handlers for the modal buttons to include the instancePk
        const confirmBtn = modal.querySelector('.btn-primary');
        const cancelBtn = modal.querySelector('.btn-secondary');
        const closeBtn = modal.querySelector('.close-button');

        confirmBtn.onclick = () => confirmRevert(instancePk);
        cancelBtn.onclick = () => cancelRevert(instancePk);
        closeBtn.onclick = () => cancelRevert(instancePk);

        modal.style.display = 'flex'; // Show the modal
    } else {
        console.error("Revert modal elements not found.");
        alert("Error: Revert modal not fully initialized.");
    }
};

function confirmRevert(instancePk) { // instancePk needs to be passed here from the modal's confirm button
    const commentInput = document.getElementById('revertComment');
    const revertComment = commentInput.value.trim();

    const instanceState = window.instanceRevertStates[instancePk];

    if (instanceState && instanceState.revertLogEntryId && websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'revert_filesystem_changes',
            payload: {
                instance_pk: instancePk,
                log_entry_pk: instanceState.revertLogEntryId,
                comment: revertComment
            }
        }));
        //console.log(`Sent revert request for log entry ID: ${instanceState.revertLogEntryId} with comment: "${revertComment}" for instance ${instancePk}`);
        cancelRevert(instancePk);
    } else {
        console.error("Failed to send revert request. Missing context or WebSocket not connected for instance", instancePk);
        alert("Failed to revert: Connection lost or missing data.");
    }
};

function cancelRevert(instancePk) {
    const modal = document.getElementById('revertFileModal');
    const commentInput = document.getElementById('revertComment');
    if (modal) {
        modal.style.display = 'none';
        commentInput.value = '';
    }
    if (window.instanceRevertStates[instancePk]) {
        window.instanceRevertStates[instancePk].revertLogEntryId = null;
    }
};

// Global variables to hold context for the revert all FS modal
function showRevertAllDialog(logEntryId, path, timestamp, instancePk) {
    if (!window.instanceRevertStates[instancePk]) {
        window.instanceRevertStates[instancePk] = {};
    }
    window.instanceRevertStates[instancePk].revertAllLogEntryId = logEntryId;

    const modal = document.getElementById('revertAllFsModal');
    const filePathElement = document.getElementById('revertAllFsFilePath');
    const timestampElement = document.getElementById('revertAllFsTimestamp');
    const commentInput = document.getElementById('revertAllFsComment');

    if (modal && filePathElement && timestampElement && commentInput) {
        filePathElement.textContent = path;
        timestampElement.textContent = timestamp;
        commentInput.value = '';

        // Dynamically set the onclick handlers for the modal buttons
        const confirmBtn = modal.querySelector('.btn-primary');
        const cancelBtn = modal.querySelector('.btn-secondary');
        const closeBtn = modal.querySelector('.close-button');

        confirmBtn.onclick = () => confirmRevertAll(instancePk);
        cancelBtn.onclick = () => cancelRevertAll(instancePk);
        closeBtn.onclick = () => cancelRevertAll(instancePk);

        modal.style.display = 'flex';
    } else {
        console.error("Revert All FS modal elements not found.");
        alert("Error: Revert All FS modal not fully initialized.");
    }
};

function confirmRevertAll(instancePk) { // instancePk needs to be passed here
    const commentInput = document.getElementById('revertAllFsComment');
    const revertComment = commentInput.value.trim();

    const instanceState = window.instanceRevertStates[instancePk];

    if (instanceState && instanceState.revertAllLogEntryId && websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'revert_all_filesystem_changes',
            payload: {
                instance_pk: instancePk,
                log_entry_pk: instanceState.revertAllLogEntryId,
                comment: revertComment
            }
        }));
        //console.log(`Sent revert ALL FS request for log entry ID: ${instanceState.revertAllLogEntryId} with comment: "${revertComment}" for instance ${instancePk}`);
        cancelRevertAll(instancePk);
    } else {
        console.error("Failed to send revert ALL FS request. Missing context or WebSocket not connected for instance", instancePk);
        alert("Failed to revert ALL FS: Connection lost or missing data.");
    }
};

function cancelRevertAll(instancePk) {
    const modal = document.getElementById('revertAllFsModal');
    const commentInput = document.getElementById('revertAllFsComment');
    if (modal) {
        modal.style.display = 'none';
        commentInput.value = '';
    }
    if (window.instanceRevertStates[instancePk]) {
        window.instanceRevertStates[instancePk].revertAllLogEntryId = null;
    }
};






