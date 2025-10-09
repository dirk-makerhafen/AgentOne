// This file manages the rendering of standalone ToolCall messages, and also updates embedded tool call statuses.

function renderToolCallMessage(payload) {
    const toolCallMessageTemplate = getTemplate('ToolCallTemplate');

    // --- Part 1: Handle updates to tool calls that might be embedded inside a ConversationMessage. ---
    // This allows live status/result updates without re-rendering the whole conversation message.
    const statusContainer = document.getElementById(`tool_call_status_${payload.id}`);
    if (statusContainer) {
        statusContainer.innerHTML = payload.status;
        statusContainer.className = `status-${payload.status}`; // Update class for styling
    }
    const resultContainer = document.getElementById(`tool_call_result_${payload.id}`);
    if (resultContainer && payload.result) { // Only update result if payload.result is present
        resultContainer.textContent = `Response:
${JSON.stringify(payload.result, null, 2)}`;
    }
    
    // --- Part 2: Render/update the standalone ToolCall log entry ---
    const renderedHtml = toolCallMessageTemplate({
        message: payload,
        formattedTimestamp: new Date(payload.created_at).toLocaleTimeString(),
        arguments_json: JSON.stringify(payload.arguments, null, 2),
        result_json: payload.result ? JSON.stringify(payload.result, null, 2) : null,
        instancePk: payload.agentInstance_id, // Pass instancePk to the template
    });
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = renderedHtml.trim();
    const newElement = tempDiv.firstChild;
    
    const existingElement = document.getElementById(newElement.id);
    if (existingElement) {
        const parentLogArea = existingElement.closest(`#logArea_${ payload.agentInstance_id}`);
        const detailsView = existingElement.querySelector('.toolcall-full');
        const isExpanded = detailsView && !detailsView.classList.contains('hidden');
        if (isExpanded) {
            const newDetailsView = newElement.querySelector('.toolcall-full');
            if (newDetailsView) {
                newDetailsView.classList.remove('hidden');
            }
        }
        newElement.classList.add('no-animate');
        // ReplaceChild is safer than replaceWith if the element is part of a live NodeList
        parentLogArea.replaceChild(newElement, existingElement);
    } else {
        addToChatArea(newElement,  payload.agentInstance_id);
    }
};