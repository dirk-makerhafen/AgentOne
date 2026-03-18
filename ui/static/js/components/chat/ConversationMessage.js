// This file manages the rendering of conversation messages (user, assistant, etc.) in the log.

const partTemplate = document.getElementById('MessagePartTemplate');
    Handlebars.registerPartial('MessagePartTemplate', partTemplate.innerHTML);

function renderMessage(payload) {    
    const conversationMessageTemplate = getTemplate('MessageTemplate');
    
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = conversationMessageTemplate({
        message: payload,
        formattedTimestamp: new Date(payload.created_at).toLocaleTimeString(),
    }).trim();
    const newElement = tempDiv.firstChild;
    
    const existingElement = document.getElementById(newElement.id);

    if (existingElement) {
        const expandedToolCallIds = new Set();
        existingElement.querySelectorAll('.toolcall-full:not(.hidden)').forEach(detailsView => {
            const toolCallId = detailsView.id.replace('tool_call_full_', '');
            if (toolCallId) expandedToolCallIds.add(toolCallId);
        });

        newElement.querySelectorAll('.toolcall-full').forEach(newDetailsView => {
            const toolCallId = newDetailsView.id.replace('tool_call_full_', '');
            if (expandedToolCallIds.has(toolCallId)) newDetailsView.classList.remove('hidden');
        });

        newElement.classList.add('no-animate'); 
        existingElement.replaceWith(newElement);
    } else {
        addToChatArea(newElement, payload.agentInstance_id);
    }
};

function renderMessagePart(payload) {
    const partTemplate = getTemplate('MessagePartTemplate');
    if (!partTemplate) {
        console.error("MessagePartTemplate not found!");
        return;
    }

    const parentContainer = document.getElementById(`message_parts_container_${payload.conversationMessage_id}`);
    if (!parentContainer) {
        // The parent message might not have been rendered yet.
        // This can happen in high-frequency streaming scenarios.
        // We will rely on the full Message re-render to catch up.
        return;
    }

    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = partTemplate(payload).trim();
    const newPartElement = tempDiv.firstChild;
    
    const existingPartElement = document.getElementById(`message_part_${payload.id}`);
    
    if (existingPartElement) {
        // Preserve tool call expanded state if it exists
        const oldToolCall = existingPartElement.querySelector('.toolcall-full');
        if (oldToolCall && !oldToolCall.classList.contains('hidden')) {
            const newToolCall = newPartElement.querySelector('.toolcall-full');
            if (newToolCall) {
                newToolCall.classList.remove('hidden');
            }
        }
        existingPartElement.replaceWith(newPartElement);
    } else {
        // To ensure parts are always in the correct order, we find the right place to insert.
        const existingParts = parentContainer.querySelectorAll('.message-part');
        let inserted = false;
        for (let i = 0; i < existingParts.length; i++) {
            const partIndex = parseInt(existingParts[i].getAttribute('data-part-index'), 10);
            if (payload.index < partIndex) {
                parentContainer.insertBefore(newPartElement, existingParts[i]);
                inserted = true;
                break;
            }
        }
        if (!inserted) {
            parentContainer.appendChild(newPartElement);
        }
    }
}


function togglePinToContext(messageId, instancePk) {
    const pinIcon = document.querySelector(`.pin-icon[data-message-id="${messageId}"]`);
    if (pinIcon) {
        const isPinned = pinIcon.classList.contains('pinned');
        const newPinnedState = !isPinned;
        conversationApi.updateMessageFlags(instancePk, messageId, newPinnedState, null);
    }
};

function toggleHideFromContext(messageId, instancePk) {
    const hideIcon = document.querySelector(`.hide-icon[data-message-id="${messageId}"]`);
    if (hideIcon) {
        const isHidden = hideIcon.classList.contains('hide_from_context');
        const newHiddenState = !isHidden;
        conversationApi.updateMessageFlags(instancePk, messageId, null, newHiddenState);
    }
};
