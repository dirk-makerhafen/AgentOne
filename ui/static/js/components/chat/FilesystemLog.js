// This file manages the rendering of filesystem log messages and their interactions.

function renderFilesystemMessage(payload) {
    const filesystemMessageTemplate = getTemplate('FilesystemLogTemplate');
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = filesystemMessageTemplate({
        formattedTimestamp: new Date(payload.created_at).toLocaleTimeString(),
        message: payload,
    }).trim();
    const newElement = tempDiv.firstChild;

    const existingElement = document.getElementById(newElement.id);
    if (existingElement) {
        const detailsView = existingElement.querySelector('.filesystem-content');
        const isExpanded = detailsView && !detailsView.classList.contains('hidden');
        newElement.classList.add('no-animate');
        existingElement.replaceWith(newElement);
        if (isExpanded) {
            const newItem = document.getElementById(newElement.id);
            const newDetailsView = newItem.querySelector('.filesystem-content');
            if (newDetailsView) {
                newDetailsView.classList.remove('hidden');
                if (newItem.dataset.content !== undefined) {
                    generateAndInjectFsContent(newItem, newDetailsView, payload.agentInstance_id, newItem.dataset.loadMode || 'full');
                }
            }
        }
    } else {
        addToChatArea(newElement, payload.agentInstance_id);
    }
}

function toggleFilesystemDetails(logItemId, instancePk, displayMode = 'full') {
    const item = document.getElementById(logItemId);
    const detailsDiv = item.querySelector('.filesystem-content');
    if (!detailsDiv) return;

    const isCurrentlyHidden = detailsDiv.classList.contains('hidden');
    if (isCurrentlyHidden || detailsDiv.dataset.currentDisplayMode !== displayMode) {
        detailsDiv.classList.remove('hidden');
        detailsDiv.dataset.currentDisplayMode = displayMode;
    } else {
        detailsDiv.classList.add('hidden');
        detailsDiv.dataset.currentDisplayMode = '';
        return;
    }

    if (item.dataset.content === undefined && displayMode !== 'summary') {
        const logEntryPk = item.dataset.id;
        filesystemApi.getContent(instancePk, logEntryPk);
    } else {
        generateAndInjectFsContent(item, detailsDiv, instancePk, displayMode);
    }
}

function toggleFilesystemSummary(logItemId, instancePk) {
    toggleFilesystemDetails(logItemId, instancePk, 'summary');
}

function generateAndInjectFsContent(item, detailsDiv, instancePk, displayMode) {
    if (item.dataset.content === undefined && displayMode !== 'summary') {
        detailsDiv.innerHTML = '<pre>Content not yet loaded.</pre>';
        return;
    }
    
    const path = item.dataset.path;
    const action = item.dataset.action;
    const isDirectory = item.dataset.isDirectory === 'true';

    const unescape = (str) => str ? String(str).replace(/&apos;/g, "'").replace(/&quot;/g, '"').replace(/&#96;/g, '`').replace(/&#10;/g, '\n').replace(/&#13;/g, '\r') : '';
    const content = unescape(item.dataset.content);
    const prevContent = unescape(item.dataset.prevContent);
    const summaryContent = unescape(item.dataset.summary);

    let generatedHtml = '';
    if (action === 'delete') {
        generatedHtml = `<pre>${isDirectory ? 'Directory' : 'File'} '${path}' deleted.</pre>`;
    } else if (displayMode === 'summary') {
        generatedHtml = `<pre>${summaryContent || 'No summary available.'}</pre>`;
    } else if (content !== prevContent && content) {
        const diff = Diff.createTwoFilesPatch(path, path, prevContent, content);
        generatedHtml = Diff2Html.html(diff, { drawFileList: false, matching: "lines", outputFormat: "side-by-side" });
    } else if (content) {
        generatedHtml = isDirectory ? `Directory listing unchanged:<br><pre>${content}</pre>` : `<pre>${content}</pre>`;
    } else {
        generatedHtml = isDirectory ? `Directory is empty.` : `File is empty or content not available.`;
    }
    generatedHtml += `<button class="btn btn-xs btn-default log-btn" onclick="event.preventDefault(); toggleFilesystemDetails('${item.id}', ${instancePk});"><i class="fa fa-minus"></i>Hide Details</button>`;
    detailsDiv.innerHTML = generatedHtml;
}

function loadFileFromLog(path, instancePk) {
    directToolCallApi.call(instancePk, [{ function_name: 'fs_load', arguments: { path: path } }]);
};

window.instanceRevertStates = window.instanceRevertStates || {};

function showRevertDialog(logEntryId, action, path, instancePk) {
    window.instanceRevertStates[instancePk] = { revertLogEntryId: logEntryId };
    const modal = document.getElementById('revertFileModal');
    if (modal) {
        modal.querySelector('#revertFilePath').textContent = path;
        modal.querySelector('#revertComment').value = '';
        modal.querySelector('.btn-primary').onclick = () => confirmRevert(instancePk);
        modal.querySelector('.btn-secondary').onclick = () => cancelRevert(instancePk);
        modal.querySelector('.close-button').onclick = () => cancelRevert(instancePk);
        modal.style.display = 'flex';
    }
};

function confirmRevert(instancePk) {
    const revertComment = document.getElementById('revertComment').value.trim();
    const { revertLogEntryId } = window.instanceRevertStates[instancePk];
    if (revertLogEntryId) {
        filesystemApi.undo(instancePk, revertLogEntryId, revertComment);
        cancelRevert(instancePk);
    }
};

function cancelRevert(instancePk) {
    const modal = document.getElementById('revertFileModal');
    if (modal) modal.style.display = 'none';
    if (window.instanceRevertStates[instancePk]) window.instanceRevertStates[instancePk].revertLogEntryId = null;
};

function showRevertAllDialog(logEntryId, path, timestamp, instancePk) {
    window.instanceRevertStates[instancePk] = { revertAllLogEntryId: logEntryId };
    const modal = document.getElementById('revertAllFsModal');
    if (modal) {
        modal.querySelector('#revertAllFsFilePath').textContent = path;
        modal.querySelector('#revertAllFsTimestamp').textContent = timestamp;
        modal.querySelector('#revertAllFsComment').value = '';
        modal.querySelector('.btn-primary').onclick = () => confirmRevertAll(instancePk);
        modal.querySelector('.btn-secondary').onclick = () => cancelRevertAll(instancePk);
        modal.querySelector('.close-button').onclick = () => cancelRevertAll(instancePk);
        modal.style.display = 'flex';
    }
};

function confirmRevertAll(instancePk) {
    const revertComment = document.getElementById('revertAllFsComment').value.trim();
    const { revertAllLogEntryId } = window.instanceRevertStates[instancePk];
    if (revertAllLogEntryId) {
        filesystemApi.undoAll(instancePk, revertAllLogEntryId, revertComment);
        cancelRevertAll(instancePk);
    }
};

function cancelRevertAll(instancePk) {
    const modal = document.getElementById('revertAllFsModal');
    if (modal) modal.style.display = 'none';
    if (window.instanceRevertStates[instancePk]) window.instanceRevertStates[instancePk].revertAllLogEntryId = null;
};
