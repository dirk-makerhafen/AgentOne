// This file manages the rendering of inter-agent communication messages.

function renderInterAgentMessage(payload) {
    const interAgentMessageTemplate = getTemplate('InterAgentLogTemplate');
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = interAgentMessageTemplate({
        message: payload,
        formattedTimestamp: new Date(payload.created_at).toLocaleTimeString(),
        data: JSON.stringify(payload.data, null, 2), // Assuming payload.data contains the relevant content
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
        // ReplaceChild is safer than replaceWith if the element is part of a live NodeList
        parentLogArea.replaceChild(newElement, existingElement);
    } else {
        addToChatArea(newElement, payload.agentInstance_id);
    }
};