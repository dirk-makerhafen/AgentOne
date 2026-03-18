// This file manages the rendering of Query log messages and their interactions (flame graphs, highlights).

function renderLLMQueryMessage(payload, instancePk) {
    const llmQueryMessageTemplate = getTemplate('LLMQueryTemplate');
    // --- Prepare Template Data ---
    const tokens_display = `~${payload.tokens} Tokens`;
    const partsToHighlight = [];
    if (payload.raw_data && payload.raw_data.messages) {
        payload.raw_data.messages.forEach(message => {
            if (message.parts) {
                message.parts.forEach(part => {
                    if (part.cmId) {
                        partsToHighlight.push({
                            type: 'conversation',
                            msgId: part.cmId,
                            partIndex: part.pnr,
                            tokens: part.tokens || 0
                        });
                    } else if (part.data && part.data.fs_content_type === 'FsLogEntry' && part.data.fs_content_id) {
                        partsToHighlight.push({
                            type: 'fs',
                            fsId: part.data.fs_content_id,
                            tokens: part.tokens || 0
                        });
                    }
                });
            }
        });
    }
    const hasPartsToHighlight = partsToHighlight.length > 0;
    const flamegraph_data_source = payload.raw_data && payload.raw_data.usage ? payload.raw_data.usage : null;
    const hasUsage = (payload.total_prompt_tokens > 0 || payload.total_completion_tokens > 0 || flamegraph_data_source !== null);

    const templateData = {
        formattedTimestamp: new Date(payload.created_at).toLocaleTimeString(),
        id: payload.id,
        created_at: payload.created_at,
        object: payload.object,
        tokens_display: tokens_display,
        hasUsage: hasUsage,
        hasPartsToHighlight: hasPartsToHighlight,
        partsJson: JSON.stringify(partsToHighlight), // Use JSON.stringify for data-attribute
        raw_json: JSON.stringify(payload, null, 2),
        total_prompt_tokens: payload.total_prompt_tokens || 0,
        total_completion_tokens: payload.total_completion_tokens || 0,
        flamegraph_data: flamegraph_data_source,
        instancePk: instancePk // Pass instancePk to the template
    };

    const renderedHtml = llmQueryMessageTemplate(templateData);
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = renderedHtml.trim();
    const newElement = tempDiv.firstChild;

    // --- Idempotency Check & State Preservation ---
    const existingElement = document.getElementById(`llm_query_message_${payload.id}`);
    if (existingElement) {
        const parentLogArea = existingElement.closest(`#logArea_${instancePk}`);
        const oldRawJsonView = existingElement.querySelector(`#raw_json_container_llm_query_${payload.id}`);
        const isRawJsonVisible = oldRawJsonView && !oldRawJsonView.classList.contains('hidden');
        const oldFlameGraphView = existingElement.querySelector(`#flame_graph_container_llm_query_${payload.id}`);
        const isFlameGraphVisible = oldFlameGraphView && !oldFlameGraphView.classList.contains('hidden');

        newElement.classList.add('no-animate');
        // ReplaceChild is safer than replaceWith if the element is part of a live NodeList
        parentLogArea.replaceChild(newElement, existingElement);

        // Reapply states to the newly inserted element
        if (isRawJsonVisible) {
            const newRawJsonView = newElement.querySelector(`#raw_json_container_llm_query_${payload.id}`);
            if (newRawJsonView) newRawJsonView.classList.remove('hidden');
        }
        if (isFlameGraphVisible) {
            const newFlameGraphView = newElement.querySelector(`#flame_graph_container_llm_query_${payload.id}`);
            if (newFlameGraphView) {
                newFlameGraphView.classList.remove('hidden');
                // Ensure flamegraph is re-rendered only if visible
                renderFlameGraph(`llm_query_${payload.id}`, instancePk); 
            }
        }
    } else {
        addToChatArea(newElement, instancePk);
    }
};


/**
 * Toggles the visibility of the flame graph for a given Query message.
 * If the flame graph is revealed, it attempts to render it.
 * @param {string} prefixedId The ID of the Query message container.
 * @param {number} instancePk The instance PK for scoping.
 */
function toggleFlameGraph(prefixedId, instancePk) {
    const numericId = prefixedId.split('_').pop();
    const messageElement = document.getElementById(`llm_query_message_${numericId}`);
    if (!messageElement) {
        console.error(`Could not find message element for flame graph with ID: ${numericId}`);
        return;
    }
    const flameGraphContainer = messageElement.querySelector(`#flame_graph_container_${prefixedId}`);
    if (!flameGraphContainer) {
        console.error(`Could not find flame graph container with prefixed ID: ${prefixedId}`);
        return;
    }

    flameGraphContainer.classList.toggle('hidden');
    if (!flameGraphContainer.classList.contains('hidden')) {
        renderFlameGraph(prefixedId, instancePk); // Pass the full prefixed ID and instancePk
    }
};


/**
 * Renders the D3 flame graph within its container.
 * This function now uses the data transformation logic from the old working function.
 * @param {string} prefixedId The ID of the Query message container.
 * @param {number} instancePk The instance PK for scoping.
 */
function renderFlameGraph(prefixedId, instancePk) {
    const numericId = prefixedId.split('_').pop();

    const messageElement = document.getElementById(`llm_query_message_${numericId}`);
    if (!messageElement) {
        console.error(`Could not find message element to render flame graph with ID: ${numericId}`);
        return;
    }

    const usageDataAttr = messageElement.getAttribute('data-flamegraph-data');
    if (!usageDataAttr) {
        console.warn(`No flamegraph usage data found for message ${numericId}`);
        return;
    }

    try {
        const usageData = JSON.parse(usageDataAttr);

        const flameGraphContainer = messageElement.querySelector(`#flame_graph_container_${prefixedId}`);
        if (!flameGraphContainer) return;

        // Clear previous graph
        flameGraphContainer.innerHTML = '';

        // --- Data Transformation for Flame Graph (from old working function) ---
        function transformData(node, name) {
            let children = [];
            if (typeof node === 'object' && node !== null) {
                for (const key in node) {
                    if (key !== 'tokens') { // 'tokens' is the value for the current node, not a child
                        children.push(...transformData(node[key], key));
                    }
                }
            }
            // Each transformed node should represent a branch or leaf with its own tokens
            return [{
                name: name,
                value: node.tokens || 0,
                children: children.length > 0 ? children : undefined // Only add children if they exist
            }];
        }

        const root = {
            name: "Total Prompt Tokens",
            value: Object.values(usageData).reduce((sum, item) => sum + (item.tokens || 0), 0),
            children: []
        };

        for (const key in usageData) {
            root.children.push(...transformData(usageData[key], key));
        }

        // Initialize and render flame graph
        const chart = flamegraph().width(flameGraphContainer.clientWidth - 10).cellHeight(18).selfValue(false).sort(true);

        d3.select(flameGraphContainer)
            .datum(root)
            .call(chart);

        // Debounced resize listener from old function, adapted for current scope
        let resizeTimer;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => {
                // Ensure container is still visible and has width
                if (flameGraphContainer.clientWidth > 0 && !flameGraphContainer.classList.contains('hidden')) {
                    chart.width(flameGraphContainer.clientWidth - 10);
                    d3.select(flameGraphContainer).datum(root).call(chart);
                }
            }, 250);
        });

    } catch (error) {
        console.error(`Error rendering flame graph for message ${prefixedId}:`, error);
        if (flameGraphContainer) {
            flameGraphContainer.innerHTML = '<p class="log-error">Error loading usage data for flamegraph.</p>';
        }
    }
}


/**
 * Toggles the highlight state based on which "eye" button was clicked.
 * Manages the global state and active button class.
 * @param {HTMLElement} button The button element that was clicked.
 * @param {number} instancePk The instance PK to scope the highlights.
 */
function toggleQueryHighlight(button, instancePk) {
    const partsJson = button.getAttribute('data-parts-json');
    if (!partsJson) return;

    const partsToHighlight = JSON.parse(partsJson);
    const activeClass = 'active-highlighter';

    // Check if the clicked button's highlight is already the active one
    const isCurrentlyActive = button.classList.contains(activeClass);

    // Deactivate all buttons first within this specific instance's tab content
    document.getElementById(`tabContent_agentInstance_${instancePk}`).querySelectorAll(`.${activeClass}`).forEach(btn => {
        btn.classList.remove(activeClass);
    });

    if (isCurrentlyActive) {
        // If the clicked button was already active, we are turning off highlighting
        window.activeHighlightParts = null; // Use window.activeHighlightParts for global state
    } else {
        // Otherwise, we are setting a new highlight and activating the button
        window.activeHighlightParts = partsToHighlight; // Use window.activeHighlightParts
        button.classList.add(activeClass);
    }

    // Apply the changes (either highlighting or clearing) to the DOM for this instance
    applyActiveHighlight(instancePk);
}



// This file provides render functions for nested QueryMessage and QueryMessagePart objects.

document.addEventListener('DOMContentLoaded', () => {
    const qmPartTemplate = document.getElementById('QueryMessagePartTemplate');
    if (qmPartTemplate) {
        Handlebars.registerPartial('QueryMessagePartTemplate', qmPartTemplate.innerHTML);
    } else {
        console.error("Could not find QueryMessagePartTemplate. Ensure it is loaded in ui.html.");
    }

    const qmTemplate = document.getElementById('QueryMessageTemplate');
    if(qmTemplate) {
        Handlebars.registerPartial('QueryMessageTemplate', qmTemplate.innerHTML);
    } else {
        console.error("Could not find QueryMessageTemplate. Ensure it is loaded in ui.html.");
    }
});

function renderQueryMessage(payload) {
    const parentContainer = document.querySelector(`#llm_query_message_${payload.query_id} #query_messages_container_${payload.query_id}`);
    if (!parentContainer) {
        return; // Parent Query not rendered yet. It will be handled by the full render.
    }

    const template = getTemplate('QueryMessageTemplate');
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = template(payload).trim();
    const newElement = tempDiv.firstChild;

    const existingElement = document.getElementById(newElement.id);
    if (existingElement) {
        const partsContainer = existingElement.querySelector('.query-message-parts-container');
        const isPartsVisible = partsContainer && !partsContainer.classList.contains('hidden');

        const newPartsContainer = newElement.querySelector('.query-message-parts-container');
        if (isPartsVisible && newPartsContainer) {
            newPartsContainer.classList.remove('hidden');
        }
        existingElement.replaceWith(newElement);
    } else {
        insertElementOrdered(parentContainer, newElement, (el) => parseInt(el.dataset.index, 10), payload.index);
    }
}

function renderQueryMessagePart(payload) {
    const parentContainer = document.getElementById(`query_message_parts_container_${payload.query_message_id}`);
    if (!parentContainer) {
        return; // Parent QueryMessage not rendered yet.
    }

    const template = getTemplate('QueryMessagePartTemplate');
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = template(payload).trim();
    const newElement = tempDiv.firstChild;

    const existingElement = document.getElementById(newElement.id);
    if (existingElement) {
        const contentContainer = existingElement.querySelector('.message-content');
        const isContentVisible = contentContainer && !contentContainer.classList.contains('hidden');

        const newContentContainer = newElement.querySelector('.message-content');
        if (isContentVisible && newContentContainer) {
            newContentContainer.classList.remove('hidden');
        }
        existingElement.replaceWith(newElement);
    } else {
        insertElementOrdered(parentContainer, newElement, (el) => parseInt(el.dataset.partIndex, 10), payload.index);
    }
}
