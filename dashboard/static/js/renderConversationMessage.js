const conversationMessageTemplate = Handlebars.compile(`
<div id="message_id_{{message.id}}" class="conversation-log-item log-type-conversation {{message.role}}-log-item"
     data-id="{{message.id}}" data-created-at="{{message.created_at}}">
    <div class="message-header">
        <strong>[{{formattedTimestamp}}]</strong> <strong>{{message.role}}</strong>
        <span class="message-actions">
            <i title="{{#if message.pin_to_context}}Unpin from context{{else}}Pin to context{{/if}}" class="fa fa-thumb-tack pin-icon {{#if message.pin_to_context}}pinned{{/if}}" 
               data-message-id="{{message.id}}" 
               onclick="event.stopPropagation(); togglePinToContext({{message.id}}, {{message.agentInstance_id}})"></i>
              <i title="{{#if message.hide_from_context}}Unhide{{else}}Hide{{/if}} this message from context" class="fa fa-eye-slash hide-icon {{#if message.hide_from_context}}hide_from_context{{/if}}" 
               data-message-id="{{message.id}}" 
               onclick="event.stopPropagation(); toggleHideFromContext({{message.id}}, {{message.agentInstance_id}})"></i>
        </span>
    </div>
    <div class="message-content">
        {{#each message.parts}}
            <div class="message-part" id="message_{{../message.id}}_part_{{this.pnr}}">
                {{#if this.content}}
                    {{#if this.tool_call_id}}
                        {{!-- This is content associated with a tool call, rendered within the tool call block below --}}
                    {{else}}
                        <p class="message-part-chat" style="white-space: pre;text-wrap:auto">{{this.content}}</p>
                    {{/if}}
                {{/if}}
                {{#if this.tool_call_id}}
                    <div class="message-toolcall">
                        <div class="toolcall-header">
                            <b class="status-{{this.status}}" id="tool_call_status_{{this.tool_call_id}}">{{this.status}}</b><b>{{this.function_name}}</b>&nbsp;<span class="toolcall-header-args">{{formatArgsForHeader this.arguments}}</span>
                            <button class="btn btn-xs btn-default log-btn" onclick="event.preventDefault(); toggleElementVisibility('tool_call_full_{{this.tool_call_id}}')" title="Show Details"><i class="fa fa-plus"></i> More </button>
                        </div>
                        <div class="toolcall-full hidden" id="tool_call_full_{{this.tool_call_id}}">
                            <pre>Arguments:
    {{jsonStringify this.arguments}}</pre>
                            <pre id="tool_call_result_{{this.tool_call_id}}">Response:
    {{jsonStringify this.result}}</pre>
                        </div>
                    </div>
                {{/if}}
             </div>
        {{/each}}
    </div>
</div>`);

function renderConversationMessage(payload) {    
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = conversationMessageTemplate({
        message: payload,
        formattedTimestamp: new Date(payload.created_at).toLocaleTimeString(),
    }).trim();
    const newElement = tempDiv.firstChild;

    const existingElement = document.getElementById(newElement.id);
    if (existingElement) {
        const parentLogArea = existingElement.closest(`#logArea_${payload.agentInstance_id}`);
        const expandedToolCallIds = new Set();
        existingElement.querySelectorAll('.toolcall-full').forEach(detailsView => {
            if (!detailsView.classList.contains('hidden')) {
                // Extract the ID from an id like 'tool_call_full_123'
                const toolCallId = detailsView.id.replace('tool_call_full_', '');
                if (toolCallId) {
                    expandedToolCallIds.add(toolCallId);
                }
            }
        });

        // If any were expanded, apply that state to the NEW element before it's rendered
        if (expandedToolCallIds.size > 0) {
            newElement.querySelectorAll('.toolcall-full').forEach(newDetailsView => {
                const toolCallId = newDetailsView.id.replace('tool_call_full_', '');
                if (expandedToolCallIds.has(toolCallId)) {
                    newDetailsView.classList.remove('hidden');
                }
            });
        }
        newElement.classList.add('no-animate');
        parentLogArea.replaceChild(newElement, existingElement);
    } else {
        appendLog(newElement, payload.agentInstance_id); // Pass instancePk to appendLog
    }
};

function togglePinToContext(messageId, instancePk) {
    if (!instancePk) {
        console.error("togglePinToContext: instancePk is required.");
        return;
    }
    const instanceLogArea = document.getElementById(`logArea_${instancePk}`);
    if (!instanceLogArea) {
        console.error(`Log area for instance ${instancePk} not found.`);
        return;
    }

    const pinIcon = instanceLogArea.querySelector(`.pin-icon[data-message-id="${messageId}"]`);
    if (pinIcon) {
        const isPinned = pinIcon.classList.contains('pinned');
        const newPinnedState = !isPinned;

        websocket.send(JSON.stringify({
            'type': 'update_conversation_message_flags',
            'payload': {
                'instance_pk': instancePk, // Use passed instancePk
                'message_id': messageId,
                'pin_to_context': newPinnedState
            }
        }));

        // Immediate visual feedback
        if (newPinnedState) {
            pinIcon.classList.add('pinned');
        } else {
            pinIcon.classList.remove('pinned');
        }
    }
};

function toggleHideFromContext(messageId, instancePk) {
    if (!instancePk) {
        console.error("toggleHideFromContext: instancePk is required.");
        return;
    }
    const instanceLogArea = document.getElementById(`logArea_${instancePk}`);
    if (!instanceLogArea) {
        console.error(`Log area for instance ${instancePk} not found.`);
        return;
    }

    const hideIcon = instanceLogArea.querySelector(`.hide-icon[data-message-id="${messageId}"]`);
    if (hideIcon) {
        const isHidden = hideIcon.classList.contains('hide_from_context');
        const newHiddenState = !isHidden;

        websocket.send(JSON.stringify({
            'type': 'update_conversation_message_flags',
            'payload': {
                'instance_pk': instancePk, // Use passed instancePk
                'message_id': messageId,
                'hide_from_context': newHiddenState
            }
        }));

        // Immediate visual feedback
        if (newHiddenState) {
            hideIcon.classList.remove('fa-eye');
        } else {
            hideIcon.classList.remove('hide_from_context');
        }
    }
};
