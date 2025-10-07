// This file contains functions for logging messages to the sidebar client log area.

/**
 * Adds a message to the sidebar client log area.
 * @param {string} message The message content.
 * @param {string} type The type of log ('info', 'warning', 'error', 'client-status', etc.).
 * @param {string} timestamp Optional timestamp string.
 */
function addToClientLog(message, type = 'info', timestamp = null) {
    const consoleTargetElement = document.getElementById('sidebarConsoleOutputArea');

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

// Expose globally
window.addToClientLog = addToClientLog;

