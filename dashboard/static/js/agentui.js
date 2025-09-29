Handlebars.registerHelper('eq', function(a, b) {return a === b});

Handlebars.registerHelper('formatArgsForHeader', function(arguments) {
    let argsStr = "";
    for (const argName in arguments) {
        if (arguments.hasOwnProperty(argName)) {
            let argValue = String(arguments[argName]);
            if (argValue.length > 20 && argName != "path") {
                argValue = argValue.substring(0, 17) + '...';
            }
            argsStr += `${argName}="${Handlebars.escapeExpression(argValue)}" `;
        }
    }
    return new Handlebars.SafeString(argsStr);
});

Handlebars.registerHelper('jsonStringify', function(context) {
    return JSON.stringify(context, null, 2);
});

Handlebars.registerHelper('isUndefined', function(value) {
    return value === undefined;
});

Handlebars.registerHelper('escape', function(value) {
    if (value === undefined || value === null) { return ''}
    // Normalize all line endings (CRLF, CR) to LF, then escape LF for the HTML attribute.
    return value.replace(/'/g, '&apos;').replace(/"/g, '&quot;').replace(/`/g, '&#96;').replace(/\r\n|\r/g, '\n').replace(/\n/g, '&#10;');
});

Handlebars.registerHelper('defaultIfEmpty', function(value, defaultValue) {
    return (value === null || value === undefined || value === '') ? defaultValue : value;
});

Handlebars.registerHelper('formatNumber', function(value) {
    if (value === null || value === undefined) {
        return 'N/A';
    }
    return new Intl.NumberFormat().format(value);
});

Handlebars.registerHelper('or', function() {
    return Array.prototype.slice.call(arguments, 0, arguments.length - 1).some(Boolean);
});

Handlebars.registerHelper('json', function(context) {
    if (typeof context === "string"){
       return context;
    }else{
         return JSON.stringify(context, null, 2);
    }
});
Handlebars.registerHelper('isEmpty', function(obj) {
    if (!obj) return true;
    return Object.keys(obj).length === 0;
});

Handlebars.registerHelper('formatDateTime', function(isoDateString) {
    if (!isoDateString) return '';
    const date = new Date(isoDateString);
    return date.toLocaleString(); // Adjust format as needed
});

Handlebars.registerHelper('not', function(value) {
    return !value;
});





// Instance-specific state management for log areas
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

document.addEventListener('DOMContentLoaded', () => {
    // Global lists for dropdowns
    window.allAvailableModels = [];
    window.allAvailableSystems = [];

    // Event listener for the global console output area (for system-wide messages)
    const globalConsoleOutputArea = document.getElementById('consoleOutputArea');
    if (!globalConsoleOutputArea) {
        //console.error("Error: Global 'consoleOutputArea' not found.");
    }
    
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
                
                websocket.send(JSON.stringify({
                    type: 'load_history',
                    payload: {
                        max_id: oldestVisibleId,
                        limit: 20,
                        instance_pk: instancePk
                    }
                })); 
                addToConsoleArea(`Client: Loading more history for instance ${instancePk}`, 'info');
            } else {
                addToConsoleArea("Cannot load history. WebSocket not open.", 'warning');
                instanceLogState.isLoadingHistory = false;
            }
        }
    });
}
window.attachLogAreaScrollListener = attachLogAreaScrollListener; // Expose globally

    // Send Message Button event listener will be attached dynamically per instance

    // Initialize log filter controls will be called per instance
});

/**
 * Appends a log entry (HTMLElement) to the appropriate instance's log area.
 * @param {HTMLElement} newElement The content to append.
 * @param {number} instancePk The primary key of the agent instance this message belongs to.
 */
function appendLog(newElement, instancePk) {
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

/**
 * Adds a message to either a specific instance's console output or the global console output.
 * @param {string} message The message content.
 * @param {string} type The type of log ('info', 'warning', 'error', etc.).
 * @param {string} timestamp Optional timestamp string.
 * @param {number|string} target Instance PK or 'global'.
 */
function addToConsoleArea(message, type = 'info', timestamp = null, target = 'global') {
    let consoleTargetElement;
    if (target === 'global') {
        consoleTargetElement = document.getElementById('consoleOutputArea');
    } else {
        consoleTargetElement = document.getElementById(`consoleOutputArea_${target}`);
    }

    if (!consoleTargetElement) {
        console.error(`Console output area for target "${target}" not found.`);
        // Fallback to global if instance-specific isn't found
        if (target !== 'global') {
            consoleTargetElement = document.getElementById('consoleOutputArea');
            if (!consoleTargetElement) {
                console.error("Global consoleOutputArea not found as fallback either.");
                return;
            }
        } else {
            return;
        }
    }

    const logEntry = document.createElement('div');
    logEntry.classList.add('log-entry');
    logEntry.classList.add(`log-${type}`);
    
    const displayTime = timestamp ? new Date(timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
    const timestampSpan = document.createElement('span');
    timestampSpan.className = 'log-timestamp';
    timestampSpan.textContent = `[${displayTime}] `;
    
    const messageSpan = document.createElement('span');
    messageSpan.className = 'log-message';
    messageSpan.textContent = message;

    logEntry.appendChild(timestampSpan);
    logEntry.appendChild(messageSpan);
    consoleTargetElement.appendChild(logEntry);

    // Scroll to bottom of the console target element
    consoleTargetElement.scrollTop = consoleTargetElement.scrollHeight;
}


// --- Generic Utility Functions ---

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


// --- LLM Query Highlighting ---
// Global state to track the currently active highlight
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




document.addEventListener('DOMContentLoaded', () => {
    const addProviderBtn = document.getElementById('add-provider-btn');
    const addProviderModal = document.getElementById('addProviderModal');
    const saveProviderBtn = document.getElementById('saveProviderBtn');
    const providerNameInput = document.getElementById('providerName');
    const providerUrlInput = document.getElementById('providerUrl');

    if (addProviderBtn) {
        addProviderBtn.addEventListener('click', () => {
            if (addProviderModal) {
                // Clear form before showing
                if(providerNameInput) providerNameInput.value = '';
                if(providerUrlInput) providerUrlInput.value = '';
                addProviderModal.style.display = 'block';
            }
        });
    }

    if (saveProviderBtn) {
        saveProviderBtn.addEventListener('click', () => {
            const name = providerNameInput.value.trim();
            const url = providerUrlInput.value.trim();

            if (!name) {
                addToConsoleArea('Provider name is required.', 'error');
                return;
            }

            if (websocket && websocket.readyState === WebSocket.OPEN) {
                websocket.send(JSON.stringify({
                    type: 'create_provider',
                    payload: {
                        name: name,
                        url: url
                    }
                }));
                if (addProviderModal) {
                    addProviderModal.style.display = 'none';
                }
            } else {
                addToConsoleArea('WebSocket is not connected.', 'error');
            }
        });
    }
});

// --- Event Listeners for Edit Provider Modal ---
document.addEventListener('DOMContentLoaded', () => {
    const editProviderModal = document.getElementById('editProviderModal');
    const updateProviderBtn = document.getElementById('updateProviderBtn');
    
    if (updateProviderBtn && editProviderModal) {
        updateProviderBtn.addEventListener('click', () => {
            const providerId = document.getElementById('editProviderId').value;
            const name = document.getElementById('editProviderName').value.trim();
            const url = document.getElementById('editProviderUrl').value.trim();

            if (!providerId || !name) {
                addToConsoleArea('Provider ID and Name are required to update.', 'error');
                return;
            }

            if (websocket && websocket.readyState === WebSocket.OPEN) {
                websocket.send(JSON.stringify({
                    type: 'update_provider',
                    payload: {
                        provider_pk: providerId,
                        name: name,
                        url: url
                    }
                }));
                editProviderModal.style.display = 'none';
            } else {
                addToConsoleArea('WebSocket is not connected.', 'error');
            }
        });
    }
});

// --- Event Listeners for Add API Key Modal ---
document.addEventListener('DOMContentLoaded', () => {
    const addApiKeyModal = document.getElementById('addApiKeyModal');
    const saveApiKeyBtn = document.getElementById('saveApiKeyBtn');

    if (saveApiKeyBtn && addApiKeyModal) {
        saveApiKeyBtn.addEventListener('click', () => {
            const providerId = document.getElementById('addApiKeyProviderId').value;
            const apiKey = document.getElementById('apiKeyInput').value.trim();
            const comment = document.getElementById('apiKeyComment').value.trim();

            if (!providerId || !apiKey) {
                addToConsoleArea('Provider ID and API Key are required.', 'error');
                return;
            }

            if (websocket && websocket.readyState === WebSocket.OPEN) {
                websocket.send(JSON.stringify({
                    type: 'create_provider_apikey',
                    payload: {
                        provider_pk: providerId,
                        key: apiKey,
                        comment: comment
                    }
                }));
                addApiKeyModal.style.display = 'none';
            } else {
                addToConsoleArea('WebSocket is not connected.', 'error');
            }
        });
    }
});

