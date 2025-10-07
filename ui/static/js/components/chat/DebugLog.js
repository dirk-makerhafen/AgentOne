// This file manages the rendering of debug log messages.

function renderDebugLogMessage(payload) {
    const debugLogMessageTemplate = getTemplate('DebugLogTemplate');
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = debugLogMessageTemplate({
        message: payload,
        formattedTimestamp: new Date(payload.created_at).toLocaleTimeString(),
        data: JSON.stringify(payload.data, null, 2)
    }).trim();
    const newElement = tempDiv.firstChild;

    const existingElement = document.getElementById(newElement.id);
    if (existingElement) {
        // Capture the expanded state of the details view
        const detailsView = existingElement.querySelector('.message-content');
        const isExpanded = detailsView && !detailsView.classList.contains('hidden');

        // Apply captured state to the NEW element before it replaces the old one
        if (isExpanded) {
            const newDetailsView = newElement.querySelector('.message-content');
            if (newDetailsView) {
                newDetailsView.classList.remove('hidden');
            }
        }
        newElement.classList.add('no-animate'); // Prevent re-animation on update
        existingElement.replaceWith(newElement);
    } else {
        addToChatArea(newElement, payload.agentInstance_id);
    }
};