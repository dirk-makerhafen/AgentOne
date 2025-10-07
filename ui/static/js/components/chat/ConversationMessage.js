// This file manages the rendering of conversation messages (user, assistant, etc.) in the log.

function renderConversationMessage(payload) {    
    const conversationMessageTemplate = getTemplate('ConversationMessageTemplate');
    
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
