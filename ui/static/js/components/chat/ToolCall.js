// This file manages the rendering of standalone ToolCall messages, and also updates embedded tool call statuses.

// Renders and manages the rendering of tool calls, both standalone (legacy) and embedded in ConversationMessageParts (standard).
function renderToolCallMessage(payload) {
    const toolCallId = payload.tool_call_id || payload.id;

    // --- Primary Update Logic: Target embedded tool calls first ---
    const statusContainer = document.getElementById(`tool_call_status_${toolCallId}`);
    if (statusContainer) {
        statusContainer.textContent = payload.status;
        statusContainer.className = `toolcall-status-${payload.status}`;
    }

    const resultContainer = document.getElementById(`tool_call_result_${toolCallId}`);
    if (resultContainer && payload.result) {
        const preElement = resultContainer.querySelector('pre');
        if (preElement) {
            preElement.textContent = JSON.stringify(payload.result, null, 2);
        }
    }

    // --- Fallback/Legacy Logic: Render standalone ToolCall log entry ---
    // This handles the old `@@@...@@@` style tool calls which are not part of a ConversationMessage.
    const toolCallMessageTemplate = getTemplate('ToolCallTemplate');
    const renderedHtml = toolCallMessageTemplate({
        message: payload,
        formattedTimestamp: new Date(payload.created_at).toLocaleTimeString(),
        arguments_json: JSON.stringify(payload.arguments, null, 2),
        result_json: payload.result ? JSON.stringify(payload.result, null, 2) : null,
        instancePk: payload.agentInstance_id,
        tool_call_id: toolCallId
    });
    
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = renderedHtml.trim();
    const newElement = tempDiv.firstChild;
    
    const existingElement = document.getElementById(`tool_call_log_${toolCallId}`);
    
    if (existingElement) {
        // This tool call is already rendered as a standalone log item. Update it.
        const parentLogArea = existingElement.closest(`#logArea_${payload.agentInstance_id}`);
        const detailsView = existingElement.querySelector('.toolcall-full');
        const isExpanded = detailsView && !detailsView.classList.contains('hidden');
        
        if (isExpanded) {
            const newDetailsView = newElement.querySelector('.toolcall-full');
            if (newDetailsView) newDetailsView.classList.remove('hidden');
        }
        
        newElement.classList.add('no-animate');
        parentLogArea.replaceChild(newElement, existingElement);
    } else if (!statusContainer) {
        // Only add as a new standalone log item if it wasn't found embedded in a message.
        addToChatArea(newElement, payload.agentInstance_id);
    }
}