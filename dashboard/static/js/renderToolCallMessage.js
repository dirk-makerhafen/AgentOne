
const toolCallMessageTemplate = Handlebars.compile(`
<div id="tool_call_message_{{message.id}}" class="conversation-log-item log-type-tool tool-log-item"
     data-id="{{message.id}}" data-created-at="{{message.created_at}}">
    <div class="message-header">
        <strong>[{{formattedTimestamp}}]</strong> {{message.id}} <strong>Tool Call ({{message.function_name}}):</strong> Status: <strong class="status-{{message.status}}">{{message.status}}</strong>
        <button class="btn btn-xs btn-default log-btn" onclick="event.preventDefault(); toggleElementVisibility('tool_call_full_message_{{message.id}}')" title="Show Details"><i class="fa fa-plus"></i> More </button>
    </div>
    <div id="tool_call_full_message_{{message.id}}" class="toolcall-full message-content hidden">
        <pre>Arguments:
{{arguments_json}}</pre>
        {{#if result_json}}
        <pre>Result:
{{result_json}}</pre>
        {{/if}}
    </div>
</div>`);

function renderToolCallMessage(payload) {
    // First, handle updates to tool calls that might be embedded inside a ConversationMessage.
    // This allows live status/result updates without re-rendering the whole conversation message.
    const statusContainer = document.getElementById(`tool_call_status_${payload.id}`);
    if (statusContainer) {
        statusContainer.innerHTML = payload.status;
        statusContainer.className = `status-${payload.status}`; // Update class for styling
    }
    const resultContainer = document.getElementById(`tool_call_result_${payload.id}`);
    if (resultContainer) {
        resultContainer.textContent = `Response:
${JSON.stringify(payload.result, null, 2)}`;
    }
    
    const renderedHtml = toolCallMessageTemplate({
        message: payload,
        formattedTimestamp: new Date(payload.created_at).toLocaleTimeString(),
        arguments_json: JSON.stringify(payload.arguments, null, 2),
        result_json: payload.result ? JSON.stringify(payload.result, null, 2) : null
    });
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = renderedHtml.trim();
    const newElement = tempDiv.firstChild;
    
    const existingElement = document.getElementById(newElement.id);
    if (existingElement) {
        const parentLogArea = existingElement.closest(`#logArea_${payload.agentInstance_id}`);
        const detailsView = existingElement.querySelector('.toolcall-full');
        const isExpanded = detailsView && !detailsView.classList.contains('hidden');
        if (isExpanded) {
            const newDetailsView = newElement.querySelector('.toolcall-full');
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
