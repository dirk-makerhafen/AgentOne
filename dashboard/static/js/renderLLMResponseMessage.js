const llmResponseMessageTemplate = Handlebars.compile(`
<div id="llm_response_message_{{id}}" class="conversation-log-item log-type-llm llm-response-item"
        data-id="{{id}}" data-created-at="{{created_at}}">
    <div class="message-header">
        <strong>[{{formattedTimestamp}}]</strong> {{id}} <strong>{{object}} : </strong>
        {{tokens_display}}
        <button class="btn btn-xs btn-default log-btn toggle-raw-json" data-target="llm_response_{{id}}" title="Show Raw JSON"><i class="fa fa-code"></i> raw</button>
    </div>
    <div id="raw_json_container_llm_response_{{id}}" class="message-content hidden">
        <pre>{{raw_json}}</pre>
        <a href="#" class="toggle-raw-json" data-target="llm_response_{{id}}">Hide raw</a>
    </div>
</div>`);

function renderLLMResponseMessage(payload) {
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
        partsJson: JSON.stringify(partsToHighlight),
        raw_json: JSON.stringify(payload.raw_data, null, 2),
        instancePk: payload.agentInstance_id // Pass instancePk to the template
    };

    const renderedHtml = llmResponseMessageTemplate(templateData);
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = renderedHtml.trim();
    const newElement = tempDiv.firstChild;
    
    // --- Attach Event Listeners ---
    newElement.querySelectorAll('.toggle-raw-json').forEach(btn => {
        btn.addEventListener("click", function(event) {
            event.preventDefault();
            const targetId = this.getAttribute('data-target');
            document.getElementById(`raw_json_container_${targetId}`).classList.toggle('hidden');
        });
    });
    
    if (hasPartsToHighlight) {
        // The event listener is now directly in the template's onclick
    }

    // --- Idempotency Check & State Preservation ---
    const existingElement = document.getElementById(`llm_response_message_${payload.id}`);
    if (existingElement) {
        const parentLogArea = existingElement.closest(`#logArea_${payload.agentInstance_id}`);
        const oldRawJson = existingElement.querySelector(`#raw_json_container_llm_response_${payload.id}`);
        const isRawJsonVisible = oldRawJson && !oldRawJson.classList.contains('hidden');
        if (isRawJsonVisible) {
            newElement.querySelector(`#raw_json_container_llm_response_${payload.id}`).classList.remove('hidden');
        }
        newElement.classList.add('no-animate');
        parentLogArea.replaceChild(newElement, existingElement);
    } else {
        appendLog(newElement, payload.agentInstance_id);
    }
};
