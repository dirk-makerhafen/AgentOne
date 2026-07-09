
from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.session import Session
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.chat.composer.footer import ComposerFooter

class ReasoningDropdown(ModelView):
    TEMPLATE_STR = '''
        <div onclick="pyview.set_reasoning_effort('none')"    class="reasoning-option {% if pyview.parent.subject.reasoning_effort == 'none'    %}selected{% endif %}" data-effort="none">None</div>
        <div onclick="pyview.set_reasoning_effort('minimal')" class="reasoning-option {% if pyview.parent.subject.reasoning_effort == 'minimal' %}selected{% endif %}" data-effort="minimal">Minimal</div>
        <div onclick="pyview.set_reasoning_effort('low')"     class="reasoning-option {% if pyview.parent.subject.reasoning_effort == 'low'     %}selected{% endif %}" data-effort="low">Low</div>
        <div onclick="pyview.set_reasoning_effort('medium')"  class="reasoning-option {% if pyview.parent.subject.reasoning_effort == 'medium'  %}selected{% endif %}" data-effort="medium">Medium</div>
        <div onclick="pyview.set_reasoning_effort('high')"    class="reasoning-option {% if pyview.parent.subject.reasoning_effort == 'high'    %}selected{% endif %}" data-effort="high">High</div>
        <div onclick="pyview.set_reasoning_effort('xhigh')"   class="reasoning-option {% if pyview.parent.subject.reasoning_effort == 'xhigh'   %}selected{% endif %}" data-effort="xhigh">Extra High</div>
        <script>
            document.getElementById('{{pyview.uid}}').style.left = document.getElementById('{{pyview.parent.reasoning_wrap.uid}}').offsetLeft + "px";
        </script>
    '''
    @property
    def DOM_ELEMENT_CLASS(self):
        return f'composer-reasoning-dropdown {"open" if self.open else ""}'

    def __init__(self, subject:Session, parent: ComposerFooter, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.open = False
    
    def set_reasoning_effort(self, value):
        self.subject.set_reasoning_effort(value)
        self.open = False
        self.parent.reasoning_wrap.update()
        self.update()

    def toggle(self):
        if not self.open:
            self.parent.close_dropdowns()
        self.open = not self.open
        self.update()

    def close(self):
        if self.open:
            self.open = False
            self.update()