from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.session import Session
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.chat.composer.footer import ComposerFooter

class ToolsetsDropdown(ModelView):
    TEMPLATE_STR = '''
        <div class="toolsets-dropdown-desc" id="toolsetsDropdownDesc"></div>
        <div class="toolsets-dropdown-state" id="toolsetsDropdownState"></div>
        <div class="toolsets-dropdown-input-row">
            <input type="text" id="toolsetsInput" class="toolsets-input" placeholder="" autocomplete="off">
        </div>
        <div class="toolsets-dropdown-actions">
            <button type="button" class="toolsets-action-btn toolsets-apply-btn" id="toolsetsApplyBtn">Apply</button>
            <button type="button" class="toolsets-action-btn toolsets-clear-btn" id="toolsetsClearBtn">Clear (global)</button>
        </div>
        <script>
            document.getElementById('{{pyview.uid}}').style.left = document.getElementById('{{pyview.parent.toolsets_wrap.uid}}').offsetLeft + "px";
        </script>
    '''
    @property
    def DOM_ELEMENT_CLASS(self):
        return f'composer-toolsets-dropdown {"open" if self.open else ""}'

    def __init__(self, subject:Session, parent: ComposerFooter, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.open = False
    
    def toggle(self):
        if not self.open:
            self.parent.close_dropdowns()
        self.open = not self.open
        self.update()

    def close(self):
        if self.open:
            self.open = False
            self.update()