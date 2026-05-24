from __future__ import annotations
from typing import TYPE_CHECKING

from server.models.tasks.agent_task_call import AgentTaskCall
from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView
from ui.main.chat.messages.toolcard import ToolCard

if TYPE_CHECKING:
    from server.models.message import Message
    from ui.main.chat.messages.message import MessageView

class AssistantMessageView(ModelView):
    DOM_ELEMENT_CLASS = 'msg-row'

    TEMPLATE_STR = '''
        <div class="msg-role assistant" title="30.4.2026, 21:44:25">
            <div class="role-icon assistant">A</div>
            <span style="font-size:12px">{{ pyview.subject.session_version.agent.name}} v{{ pyview.subject.session_version.pinned_agent_version if pyview.subject.session_version.pinned_agent_version else "-1"}}</span>

            <span class="msg-tps-inline" title="Response Tokens ">{{pyview.subject.response.completion_tokens}}tkn</span>
            <span class="msg-tps-inline" title="Time to first token">first {{pyview.subject.response.time_to_first_token |round(2) }}s</span>
            <span class="msg-tps-inline" title="Reasoning Time">think {{pyview.subject.response.reasoning_time |round(2) }}s</span>
            <span class="msg-tps-inline" title="Message Time">msg {{(pyview.subject.response.token_generation_time - pyview.subject.response.reasoning_time ) |round(2) }}s</span>
            <span class="msg-tps-inline" title="Total Time">total {{pyview.subject.response.total_time |round(2) }}s</span>
            <span class="msg-tps-inline" title="Tokens per second">{{(pyview.subject.response.completion_tokens / pyview.subject.response.token_generation_time) |round(2)}}tkn/s</span>
            <span class="msg-tps-inline" title="Tokens per second">{{(pyview.subject.response.completion_tokens / pyview.subject.response.total_time) |round(2)}}tkn/s</span>

            
        </div>
        <div class="assistant-turn-blocks">
            {% if pyview.subject.response.reasoning %}
                <div class="thinking-card open">
                    <div class="thinking-card-header" onclick="this.parentElement.classList.toggle('open')">
                        <span class="thinking-card-icon">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M12 2a7 7 0 0 1 7 7c0 2.5-1.3 4.7-3.2 6H8.2C6.3 13.7 5 11.5 5 9a7 7 0 0 1 7-7z"></path><line x1="9" y1="17" x2="15" y2="17"></line><line x1="10" y1="20" x2="14" y2="20"></line></svg>
                        </span>
                        <span class="thinking-card-label">Thinking</span>
                        <span class="thinking-card-toggle">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><polyline points="9 18 15 12 9 6"></polyline></svg>
                        </span>
                    </div>
                    <div class="thinking-card-body">
                        <pre> {{ pyview.subject.response.reasoning }} </pre>
                    </div>
                </div>
            {% endif %}

            <div class="assistant-segment" data-msg-idx="13">
                <div class="msg-body" id="message_body_{{pyview.subject.pk}}">{% for message_part in  pyview.subject.parts.filter(type__in=["MESSAGE"]) %}{{ message_part.content.get()}}{% endfor %}   
                </div>
                <div class="msg-foot">
                    <span class="msg-duration-inline">Done in {{pyview.subject.response.total_time |round(2) }}s</span>
                    <span class="msg-time" title="{{pyview.subject.create_at}}">{{pyview.subject.create_at}}</span>
                    <span class="msg-actions">
                        <button class="msg-action-btn msg-tts-btn" title="Listen" onclick="speakMessage(this)">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>
                        </button>
                        <button class="msg-action-btn" title="Fork from here" onclick="forkFromMessage(14)">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><line x1="6" y1="3" x2="6" y2="15"></line><circle cx="18" cy="6" r="3"></circle><circle cx="6" cy="18" r="3"></circle><path d="M18 9a9 9 0 0 1-9 9"></path></svg>
                        </button>
                        <button class="msg-copy-btn msg-action-btn" title="Copy" onclick="copyMsg(this)">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                        </button>
                    </span>
                </div>
            </div>
            <script>
                el = document.getElementById('message_body_{{pyview.subject.pk}}')
                el.innerHTML = marked.parse(el.innerHTML);
            </script>
            <div class="tool-card-row">
                {{ pyview.tool_list.render() }}
            </div>
        

        </div>
        
    '''
    def __init__(self, subject: Message, parent: MessageView, **kwargs):
        super().__init__(subject, parent, **kwargs) 
      
        self.message_parts = subject.parts.filter(tool_call__isnull=False)
        self.tool_calls = AgentTaskCall.objects.filter(pk__in=[message_part.tool_call.pk for message_part in self.message_parts])
        self.tool_list = QuerySetView(
            subject = self.tool_calls,
            parent = self,
            item_class = ToolCard,
            #filter_function=self._filter_function
        )
        

