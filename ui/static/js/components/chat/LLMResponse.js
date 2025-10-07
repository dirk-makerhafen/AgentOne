// This file manages the rendering of LLMResponse log messages.

function renderLLMResponseMessage(payload, instancePk) {
    const llmResponseMessageTemplate = getTemplate('LLMResponseTemplate');

    const usage = payload.raw_data.usage || {};
    const prompt_tokens = usage.prompt_tokens || 0;
    const completion_tokens = usage.completion_tokens || 0;
    const tokens_display = `${prompt_tokens} Prompt / ${completion_tokens} Completion`;
    
    // Parts to highlight from the response's reference to the original query messages
    const partsToHighlight = [];
    if (payload.raw_data && payload.raw_data.messages) {
        payload.raw_data.messages.forEach(message => {
            if (message.parts) {
                message.parts.forEach(part => {
                    if (part.cmId) {
                        partsToHighlight.push({
                            type: 'conversation',
                            msgId: part.cmId,
                            partIndex: part.pnr
                        });
                    } else if (part.data && part.data.fs_content_type === 'FsLogEntry' && part.data.fs_content_id) {
                        partsToHighlight.push({
                            type: 'fs',
                            fsId: part.data.fs_content_id
                        });
                    }
                });
            }
        });
    }
    const hasPartsToHighlight = partsToHighlight.length > 0;

    const templateData = {
        formattedTimestamp: new Date(payload.created_at).toLocaleTimeString(),
        id: payload.id,
        created_at: payload.created_at,
        object: payload.object,
        tokens_display: tokens_display,
        hasPartsToHighlight: hasPartsToHighlight,
        partsJson: JSON.stringify(partsToHighlight), // For a potential highlight button in the future
        raw_json: JSON.stringify(payload.raw_data, null, 2),
        instancePk: instancePk // Pass instancePk to the template
    };

    const renderedHtml = llmResponseMessageTemplate(templateData);
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = renderedHtml.trim();
    const newElement = tempDiv.firstChild;
    
    // --- Idempotency Check & State Preservation ---
    const existingElement = document.getElementById(`llm_response_message_${payload.id}`);
    if (existingElement) {
        const parentLogArea = existingElement.closest(`#logArea_${instancePk}`);
        const oldRawJsonView = existingElement.querySelector(`#raw_json_container_llm_response_${payload.id}`);
        const isRawJsonVisible = oldRawJsonView && !oldRawJsonView.classList.contains('hidden');

        newElement.classList.add('no-animate');
        // ReplaceChild is safer than replaceWith if the element is part of a live NodeList
        parentLogArea.replaceChild(newElement, existingElement);

        // Reapply states to the newly inserted element
        if (isRawJsonVisible) {
            const newRawJsonView = newElement.querySelector(`#raw_json_container_llm_response_${payload.id}`);
            if (newRawJsonView) newRawJsonView.classList.remove('hidden');
        }
    } else {
        addToChatArea(newElement, instancePk);
    }
};