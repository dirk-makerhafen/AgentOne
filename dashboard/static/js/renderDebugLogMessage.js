const debugLogMessageTemplate = Handlebars.compile(`
<div id="debug_log_message_{{message.id}}" class="conversation-log-item log-type-debug debug-log-item"
     data-id="{{message.id}}" data-created-at="{{message.created_at}}">
    <div class="message-header">
        <strong>[{{formattedTimestamp}}]</strong> {{message.id}} <strong>Debug Log ({{message.event}}):</strong>
        <button class="btn btn-xs btn-default log-btn" onclick="event.preventDefault(); toggleElementVisibility('debug_log_full_{{message.id}}')"><i class="fa fa-plus"></i> More </button>
    </div>
    <div id="debug_log_full_{{message.id}}" class="debug-log-full message-content hidden">
        <pre>{{data}}</pre>
        <button class="btn btn-xs btn-default log-btn" onclick="event.preventDefault(); toggleElementVisibility('debug_log_full_{{message.id}}')"><i class="fa fa-minus"></i> Hide </button>
    </div>
</div>`);

function renderDebugLogMessage(payload) {
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = debugLogMessageTemplate({
        message: payload,
        formattedTimestamp: new Date(payload.created_at).toLocaleTimeString(),
        data: JSON.stringify(payload.data, null, 2)
    }).trim();
    const newElement = tempDiv.firstChild;

    const existingElement = document.getElementById(newElement.id);
    if (existingElement) {
        const parentLogArea = existingElement.closest(`#logArea_${payload.agentInstance_id}`);
        const detailsView = existingElement.querySelector('.message-content');
        const isExpanded = detailsView && !detailsView.classList.contains('hidden');
        if (isExpanded) {
            const newDetailsView = newElement.querySelector('.message-content');
            if (newDetailsView) {
                newDetailsView.classList.remove('hidden');
            }
        }
        newElement.classList.add('no-animate');
        parentLogArea.replaceChild(newElement, existingElement);
    } else {
        appendLog(newElement, payload.agentInstance_id);
    }
};
