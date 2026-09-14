from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.session import Session
from ui.app import UiApp
from ui.lib.model_view import ModelView
from ui.main.chat.composer.dropdown.command import CommandDropdown
from ui.main.chat.composer.footer import ComposerFooter
if TYPE_CHECKING:
    from ui.main.chat.chat import Chat


class ComposerBox(ModelView):
    DOM_ELEMENT_CLASS = 'composer-box'
    TEMPLATE_STR = '''
        {{ pyview.command_dropdown.render() }}
       
        <div class="drop-hint" id="dropHint">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            Drop files to upload to workspace
        </div>
        
        <div class="attach-tray" id="attachTray"></div>
        
        <div class="mic-status" id="micStatus" style="display:none"><span class="mic-dot"></span> Listening…</div>
        
        <div class="voice-mode-bar" id="voiceModeBar" style="display:none">
            <span class="voice-mode-indicator" id="voiceModeIndicator"></span>
            <span class="voice-mode-label" id="voiceModeLabel"></span>
        </div>
        
        <textarea id="input_{{pyview.uid}}" onchange="pyview.new_text_input(document.getElementById('input_{{pyview.uid}}').value)" onkeyup="pyview.new_text_input(document.getElementById('input_{{pyview.uid}}').value)" onkeydown="{% if pyview.send_key == 'enter' %}if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();window.sendChatDraft('{{pyview.uid}}')}{% else %}if(event.key==='Enter'&&(event.ctrlKey||event.metaKey)&&!event.isComposing){event.preventDefault();window.sendChatDraft('{{pyview.uid}}')}{% endif %}"  class="composer-chat-message" rows="1"  oninput='this.style.height = "";this.style.height = this.scrollHeight + "px"' placeholder="Message AgentOne..."></textarea>

        {{ pyview.footer.render() }}
        
        <div class="upload-bar-wrap" id="uploadBarWrap">
            <div class="upload-bar" id="uploadBar"></div>
        </div>
    '''

    def __init__(self, subject:Session, parent: Chat, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.footer = ComposerFooter(subject, self)
        self.command_dropdown = CommandDropdown(subject, self)

    @property
    def send_key(self) -> str:
        """Return the configured send-key mode (default: ``"ctrl+enter"``)."""
        app = UiApp.get_instance()
        if app is not None:
            return app.settings.send_key
        return "ctrl+enter"

    def send(self, parts):
        """Delegate to the footer's send (used by the textarea send-key)."""
        self.footer.send(parts)

    def new_text_input(self, input):
        print("new_text_input", input)
        if input.startswith("/"):
            self.command_dropdown.open()
            if cmd := input[1:]:
                self.command_dropdown.filter_commands(cmd)
                print("command")
        elif self.command_dropdown.open:
            self.command_dropdown.close()
