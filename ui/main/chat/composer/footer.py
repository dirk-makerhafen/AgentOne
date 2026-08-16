from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.session import Session
from server.models.enums.message_enums import MessageRole
from server.models.sessions.session import SessionModel
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.main.chat.composer.dropdown.model import ModelDropdown
from ui.main.chat.composer.dropdown.profile import ProfileDropdown
from ui.main.chat.composer.dropdown.reasoning import ReasoningDropdown
from ui.main.chat.composer.dropdown.toolsets import ToolsetsDropdown
from ui.main.chat.composer.dropdown.workspace import WorkspaceDropdown
from ui.main.chat.panel.mobileconfig import MobileConfigPanel
from ui.main.chat.composer.wrap.ctxindicator import CtxIndicatorWrap
from ui.main.chat.composer.wrap.model import ModelWrap
from ui.main.chat.composer.wrap.profile import ProfileWrap
from ui.main.chat.composer.wrap.reasoning import ReasoningWrap
from ui.main.chat.composer.wrap.toolsets import ToolsetsWrap
from ui.main.chat.composer.wrap.workspace import WorkspaceWrap
if TYPE_CHECKING:
    from ui.main.chat.composer.box import ComposerBox
from server.models.enums.message_enums import MessagePartType, MessageContentType


class ComposerFooter(PyHtmlView):
    DOM_ELEMENT_CLASS = 'composer-footer'
    TEMPLATE_STR = '''
        <div class="composer-left">
            <input type="file" id="fileInput" multiple accept="image/*,text/*,application/pdf,application/json,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,.md,.py,.js,.ts,.yaml,.yml,.toml,.csv,.sh,.txt,.log,.env,.xls,.xlsx,.doc,.docx,.zip,.tar,.gz,.tgz,.bz2,.xz" style="display:none">
            
            <button class="icon-btn" id="btnAttach" title="Attach files" style="display:none">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
            </button>
            
            <button class="icon-btn mic-btn" id="btnMic" title="Dictate" data-i18n-title="voice_dictate" style="display:none">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="1" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
            </button>
            
            <button class="icon-btn voice-mode-btn" id="btnVoiceMode" title="Voice mode" data-i18n-title="voice_mode_toggle" style="display:none">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><!-- Lucide audio-lines: signals two-way voice conversation, matches ChatGPT/Gemini convention. --><path d="M2 10v4"/><path d="M6 6v12"/><path d="M10 3v18"/><path d="M14 8v8"/><path d="M18 5v14"/><path d="M22 10v4"/></svg>
            </button>
            
            <div class="composer-divider" aria-hidden="true"></div>

            <button style="display:none" class="yolo-pill" id="yoloPill" type="button" onclick="cmdYolo()" style="display:none1" title="YOLO mode — click to disable" data-i18n-title="yolo_pill_title_active">
                <span class="yolo-pill-icon" aria-hidden="true">⚡</span>
                <span class="yolo-pill-label" data-i18n="yolo_pill_label">YOLO</span>
            </button>


            <button class="icon-btn composer-mobile-config-btn" id="composerMobileConfigBtn" type="button" onclick="toggleMobileComposerConfig()" title="Workspace, model, reasoning, and context settings" aria-label="Workspace, model, reasoning, and context settings" aria-haspopup="true" aria-expanded="false" aria-controls="composerMobileConfigPanel">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>
                <span class="composer-mobile-ctx-badge" id="composerMobileCtxBadge" aria-hidden="true" style="display:none">0</span>
            </button>
            

            

            {{ pyview.toolsets_wrap.render() }}
            
        </div>

        <div class="composer-right">
            <span class="composer-status" id="composerStatus" style="display:none1"></span>
            
            {{ pyview.ctx_indicator_wrap.render() }}
            
            <span class="bg-badge" id="bgBadge" style="display:none1" title="Background tasks running">0</span>
            
            <button class="send-btn" id="btnSend" title="Send message" onclick="pyview.send(document.getElementById('input_{{pyview.parent.uid}}').value)">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>
            </button>

            <button class="send-btn visible stop" id="btnSend" onclick="pyview.send(document.getElementById('input_{{pyview.parent.uid}}').value)" title="Stop generation" data-action="stop" aria-label="Stop generation">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="5" width="14" height="14" rx="2"></rect></svg>
            </button>

            <button class="send-btn visible queue" id="btnSend" onclick="pyview.send(document.getElementById('input_{{pyview.parent.uid}}').value)" title="Queue message" data-action="queue" aria-label="Queue message">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M16 5H3"></path><path d="M16 12H3"></path><path d="M9 19H3"></path><path d="m16 16-3 3 3 3"></path><path d="M21 5v12a2 2 0 0 1-2 2h-6"></path></svg>
            </button>

            <button class="send-btn interrupt visible" id="btnSend" onclick="pyview.send(document.getElementById('input_{{pyview.parent.uid}}').value)" title="Interrupt and send" data-action="interrupt" aria-label="Interrupt and send">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 4v16"></path><path d="M6.029 4.285A2 2 0 0 0 3 6v12a2 2 0 0 0 3.029 1.715l9.997-5.998a2 2 0 0 0 .003-3.432z"></path></svg>
            </button>

            <button class="send-btn visible steer" id="btnSend" onclick="pyview.send(document.getElementById('input_{{pyview.parent.uid}}').value)" title="Steer current response" data-action="steer" aria-label="Steer current response">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><path d="m16.24 7.76-1.804 5.411a2 2 0 0 1-1.265 1.265L7.76 16.24l1.804-5.411a2 2 0 0 1 1.265-1.265z"></path></svg>
            </button>
        </div>

        {{ pyview.mobileconfig_panel.render() }}


        {{ pyview.toolsets_dropdown.render() }}

       

    '''
    # {{ pyview.profile_wrap.render() }}
    # {{ pyview.workspace_wrap.render() }}     
    # {{ pyview.model_wrap.render() }}
    # {{ pyview.reasoning_wrap.render() }}

    # {{ pyview.workspace_dropdown.render() }}
    # {{ pyview.profile_dropdown.render() }}
    # {{ pyview.model_dropdown.render() }}
    # {{ pyview.reasoning_dropdown.render() }}


    def __init__(self, subject:Session, parent: ComposerBox, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.parent:ComposerBox
        self.mobileconfig_panel = MobileConfigPanel(subject, self)

        self.profile_wrap = ProfileWrap(subject, self)
        self.workspace_wrap = WorkspaceWrap(subject, self)
        self.model_wrap = ModelWrap(subject, self)
        self.reasoning_wrap = ReasoningWrap(subject, self)
        self.toolsets_wrap = ToolsetsWrap(subject, self)
        
        self.profile_dropdown = ProfileDropdown(subject, self)
        self.workspace_dropdown = WorkspaceDropdown(subject, self)
        self.model_dropdown = ModelDropdown(subject, self)
        self.reasoning_dropdown = ReasoningDropdown(subject, self)
        self.toolsets_dropdown = ToolsetsDropdown(subject, self)

        self.ctx_indicator_wrap = CtxIndicatorWrap(subject, self)

    def send(self, parts):
        '''
        parts:  list from parse_llm_response of Parts
            Parts is dict with minimal keys:
                type: message, reasoning, toolcall
                content_type: text|image|template|json
                content: str|dict
        '''
        if isinstance(parts, str):
            parts = [{
                "type":  MessagePartType.MESSAGE,
                "content_type": MessageContentType.TEXT,
                "content": parts
            },]
        self.eval_javascript(f"document.getElementById('input_{self.parent.uid}').value = ''", skip_results=True)
        try:
            self.subject.add_user_message(parts)
        except Exception as e:
            from server.models.message import Message as Msg
            from runtime.events import publish_model_event
            session_version = self.subject.get_version_model()
            prev_message = self.subject.get_last_message()
            msg = Msg.objects.create(role=MessageRole.USER, session=session_version.session, session_version=session_version, prev_message=prev_message)
            msg.add_part(type=MessagePartType.MESSAGE, content_type=MessageContentType.TEXT, content=str(e))
            publish_model_event(msg, "create")

    def close_dropdowns(self):
        self.profile_dropdown.close()
        self.workspace_dropdown.close()
        self.model_dropdown.close()
        self.reasoning_dropdown.close()
        self.toolsets_dropdown.close()

    def toggleProfileDropdown(self):
        self.profile_dropdown.toggle()
    def toggleReasoningDropdown(self):
        self.reasoning_dropdown.toggle()
    def toggleToolsetsDropdown(self):
        self.toolsets_dropdown.toggle()
    def toggleComposerWsDropdown(self):
        self.workspace_dropdown.toggle()
    def toggleModelDropdown(self):
        self.model_dropdown.toggle()

        
        
        