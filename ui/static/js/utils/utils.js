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
    return value.replace(/'/g, '&apos;').replace(/"/g, '&quot;').replace(/`/g, '&#96;').replace(/\n|/g, '\r').replace(/\r/g, '&#10;');
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

Handlebars.registerHelper('formatTimestamp', function(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    // Format to a more readable string like: YYYY-MM-DD HH:MM:SS
    const pad = (num) => num.toString().padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
});


/**
 * Helper to get and compile a Handlebars template from the DOM.
 * @param {string} id The ID of the script tag containing the Handlebars template.
 * @returns {Function} A compiled Handlebars template function.
 */
function getTemplate(id) {
    const source = document.getElementById(id).innerHTML;
    return Handlebars.compile(source);
}
window.getTemplate = getTemplate

/**
 * Debounce function to limit the rate at which a function can fire.
 * @param {Function} func The function to debounce.
 * @param {number} delay The debounce delay in milliseconds.
 * @returns {Function} The debounced function.
 */
const debounce = (func, delay) => {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), delay);
    };
};

/**
 * Toggles the 'hidden' class on a DOM element.
 * @param {Event} event The DOM event to stop propagation.
 * @param {string} elementId The ID of the element to toggle.
 */
function toggleElementVisibility(event, elementId) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
    const element = document.getElementById(elementId);
    if (element) {
        element.classList.toggle('hidden');
    }
}

// A generic function to send a message via WebSocket, handling connection checks.
function sendRequest(type, payload = {}) {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type, payload }));
    } else {
        const errorMessage = `WebSocket not connected. Cannot send request type: ${type}`;
        console.error(errorMessage);
        addToClientLog(`Client Error: ${errorMessage}`, 'error');
    }
}
