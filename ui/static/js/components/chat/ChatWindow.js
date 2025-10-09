
/**
 * Appends a log entry (HTMLElement) to the appropriate instance's log area.
 * @param {HTMLElement} newElement The content to append.
 * @param {number} instancePk The primary key of the agent instance.
 */
function addToChatArea(newElement, instancePk) {
    const logArea = document.getElementById(`logArea_${instancePk}`);
    if (!logArea) {
        //console.error(`Log area for instance ${instancePk} not found.`);
        return;
    }

    // Check if the user is near the bottom of this specific logArea BEFORE adding the new element.
    const scrollThreshold = 50; // Pixels from bottom
    const isScrolledToBottom = logArea.scrollHeight - logArea.clientHeight <= logArea.scrollTop + scrollThreshold;

    // Ensure the element has the necessary data attributes for sorting
    if (!newElement.dataset.createdAt || !newElement.dataset.id) {
        //console.error("appendLog requires elements with data-created-at and data-id attributes.", newElement);
        // Fallback to just appending at the end before the ribbon
        const status_ribbon = logArea.querySelector(`#agent-status-ribbon_${instancePk}`); // Instance specific ribbon
        if (status_ribbon && logArea.contains(status_ribbon)) {
            logArea.insertBefore(newElement, status_ribbon);
        } else {
            logArea.appendChild(newElement);
        }
        if (isScrolledToBottom) {
            setTimeout(() => { logArea.scrollTop = logArea.scrollHeight; }, 0);
        }
        return;
    }

    const newTimestamp = new Date(newElement.dataset.createdAt);
    const newId = parseInt(newElement.dataset.id, 10);

    let inserted = false;
    const children = logArea.children;
    for (let i = 0; i < children.length; i++) {
        const child = children[i];
        // Ensure child is a valid log item before comparison
        if (!child.dataset.createdAt || !child.dataset.id) {
            continue;
        }

        const childTimestamp = new Date(child.dataset.createdAt);
        const childId = parseInt(child.dataset.id, 10); // Use dataset.id for consistency

        if (newTimestamp < childTimestamp || (newTimestamp.getTime() === childTimestamp.getTime() && newId < childId)) {
            logArea.insertBefore(newElement, child);
            inserted = true;
            break;
        }
    }

    if (!inserted) {
        // If not inserted anywhere, append it at the end, before an instance-specific status ribbon if it exists
        const status_ribbon = logArea.querySelector(`#agent-status-ribbon_${instancePk}`); // Instance specific ribbon
        if (status_ribbon && logArea.contains(status_ribbon)) {
            logArea.insertBefore(newElement, status_ribbon);
        } else {
            logArea.appendChild(newElement);
        }
    }

    // If the user was at the bottom, scroll to keep them there.
    if (isScrolledToBottom) {
        setTimeout(() => { logArea.scrollTop = logArea.scrollHeight; }, 0);
    }
}


document.addEventListener('DOMContentLoaded', () => {
    // Global lists for dropdowns
    window.allAvailableModels = [];
    window.allAvailableSystems = [];

/**
 * Attaches a scroll event listener to a specific logArea element
 * to handle loading more history when the user scrolls to the top.
 * @param {HTMLElement} logArea The logArea DOM element.
 * @param {number} instancePk The primary key of the agent instance.
 */
function attachLogAreaScrollListener(logArea, instancePk) {
    logArea.addEventListener('scroll', function() {
        const instanceLogState = getInstanceLogState(instancePk);
        //console.log(`[Scroll Listener - ${instancePk}] Scroll event. ScrollTop: ${logArea.scrollTop}, IsLoading: ${instanceLogState.isLoadingHistory}, HasMore: ${instanceLogState.hasMoreHistory}`);

        // Trigger only if at the top, not already loading, and more history is expected
        if (logArea.scrollTop === 0 && !instanceLogState.isLoadingHistory && instanceLogState.hasMoreHistory) {
            instanceLogState.isLoadingHistory = true; // Prevent multiple requests

            // Dynamically find the oldest message ID within this specific logArea
            const filterControls = logArea.querySelector('.log-filter-controls');
            const statusRibbon = logArea.querySelector(`#agent-status-ribbon_${instancePk}`);

            let firstLogItem = null;
            for (let i = 0; i < logArea.children.length; i++) {
                const child = logArea.children[i];
                // Skip non-message elements like filter controls, status ribbon, or loading indicator
                if (child.classList.contains('log-type-conversation')) {
                    firstLogItem = child;
                    break;
                }
            }

            if (!firstLogItem || !firstLogItem.dataset || !firstLogItem.dataset.id) {
                instanceLogState.isLoadingHistory = false;
                return;
            }
            const oldestVisibleId = firstLogItem.dataset.id;
            
            if (websocket && websocket.readyState === WebSocket.OPEN) {
                // Show loading indicator in the specific logArea
                const loadingIndicator = document.createElement('div');
                loadingIndicator.id = `history-loading-indicator_${instancePk}`;
                loadingIndicator.textContent = 'loading chat history';
                logArea.insertBefore(loadingIndicator, filterControls ? filterControls.nextSibling : logArea.firstChild);

                // Record the scroll height *before* we add new content
                instanceLogState.scrollHeightBeforeHistoryLoad = logArea.scrollHeight; 
                conversationApi.listMessages(instancePk=instancePk, max_id=oldestVisibleId, limit=20);
                addToClientLog(`Client: Loading more history for instance ${instancePk}`, 'info');
            } else {
                addToClientLog("Cannot load history. WebSocket not open.", 'warning');
                instanceLogState.isLoadingHistory = false;
            }
        }
    });
}
window.attachLogAreaScrollListener = attachLogAreaScrollListener; // Expose globally

});



let activeHighlightParts = null; 

/**
 * Applies the currently active highlight to all relevant DOM elements.
 * It clears previous highlights before applying the new ones.
 * @param {number} instancePk The instance PK to scope the highlights.
 */
function applyActiveHighlight(instancePk) {
    //console.log('applyActiveHighlight called for instance:', instancePk);
    const highlightClass = 'source-highlighted';
    const tokenDisplayClass = 'token-count-display';

    const currentInstanceTabContent = document.getElementById(`tabContent_agentInstance_${instancePk}`);
    if (!currentInstanceTabContent) {
        console.error(`Instance tab content for ${instancePk} not found for highlighting.`);
        return;
    }

    // Clear all existing highlights and token counts within this specific instance's tab
    currentInstanceTabContent.querySelectorAll(`.${highlightClass}`).forEach(el => el.classList.remove(highlightClass));
    currentInstanceTabContent.querySelectorAll(`.${tokenDisplayClass}`).forEach(el => el.remove());

    if (activeHighlightParts && Array.isArray(activeHighlightParts)) {
        //console.log('Active highlight parts:', activeHighlightParts);
        activeHighlightParts.forEach(part => {
            let elementToHighlight = null;

            if (part.type === 'conversation') {
                const messageContainer = currentInstanceTabContent.querySelector(`#message_id_${part.msgId}`);
                if (messageContainer) {
                    elementToHighlight = messageContainer.querySelector(`#message_${part.msgId}_part_${part.partIndex}`);
                }
            } else if (part.type === 'fs') {
                elementToHighlight = currentInstanceTabContent.querySelector(`#filesystem_message_FsLogEntry_${part.fsId}`);
            }

            if (elementToHighlight) {
                //console.log('Element to highlight found:', elementToHighlight.id || elementToHighlight.tagName, elementToHighlight.classList);
                let actualContentElement = elementToHighlight; // Default to the main element
                if (part.type === 'conversation') {
                    // For conversation parts, apply the highlight directly to the message-part div
                    //console.log('Targeting conversation message-part div:', actualContentElement.id || actualContentElement.tagName, actualContentElement.classList);
                } else if (part.type === 'fs') {
                    //console.log('Targeting FS log entry:', actualContentElement.id || actualContentElement.tagName, actualContentElement.classList);
                }
                actualContentElement.classList.add(highlightClass);

                // If token data is available, create and prepend the display span
                if (part.tokens && part.tokens > 0) {
                    const tokenSpan = document.createElement('span');
                    tokenSpan.className = tokenDisplayClass;
                    tokenSpan.textContent = `[${part.tokens}]`;

                    let targetForSpan = null;
                    if (part.type === 'conversation') {
                        const toolCallHeader = elementToHighlight.querySelector('.toolcall-header');
                        if (toolCallHeader) {
                            // For tool calls, prepend to the header for correct alignment
                            targetForSpan = toolCallHeader;
                        } else {
                            // For regular messages, find the <p> tag and prepend there for proper text flow
                            const pElement = elementToHighlight.querySelector('p[style*="white-space: pre"]');
                            if (pElement) {
                                targetForSpan = pElement;
                            } else {
                                // Fallback for safety
                                targetForSpan = elementToHighlight.querySelector('.message-header'); // Prepend to the overall message header
                            }
                        }
                    } else if (part.type === 'fs') {
                        // For FS entries, prepend to the header for better visibility
                        targetForSpan = elementToHighlight.querySelector('.message-header');
                    }

                    if (targetForSpan) {
                        targetForSpan.prepend(tokenSpan);
                        //console.log('Token span prepended to:', targetForSpan.tagName, targetForSpan.classList);
                    } else {
                        //console.warn('Could not find target for token span for part:', part);
                    }
                }
            } else {
                //console.warn('Could not find element to highlight for part:', part);
            }
        });
    } else {
        //console.log('No active highlight parts to apply.');
    }
}




/**
 * Toggles the 'hidden' class on a DOM element.
 * @param {string} elementId The ID of the element to toggle.
 */
function toggleElementVisibility(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.classList.toggle('hidden');
    }
}


// Instance-specific state management for chat areas
let instanceLogStates = {};
function getInstanceLogState(instancePk) {
    if (!instanceLogStates[instancePk]) {
        instanceLogStates[instancePk] = {
            isLoadingHistory: false,
            hasMoreHistory: true,
            scrollHeightBeforeHistoryLoad: null,
            latestDisplayedLogTimestamp: null, // Track the timestamp of the oldest message for this instance
        };
    }
    return instanceLogStates[instancePk];
}



