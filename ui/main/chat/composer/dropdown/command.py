from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.session import Session
from ui.lib.model_view import ModelView
if TYPE_CHECKING:
    from ui.main.chat.chat import Chat
    from ui.main.chat.composer.box import ComposerBox


class CommandDropdownOption(ModelView):
    DOM_ELEMENT_EXTRAS = 'data-name="AgentOne" data-path="/Users/Dirk/AgentOne"'
    TEMPLATE_STR = '''
        <div class="cmd-item-name">
            /compress 
            <span class="cmd-item-arg">[focus topic]</span>
        </div>
        <div class="cmd-item-desc">
            Manually compress conversation context (usage: /compress [focus topic])
        </div>
    '''

    @property
    def DOM_ELEMENT_CLASS(self):
        # {"selected" if self.parent.parent.session.workingdir == self.subject.name else ""}
        return f'cmd-item'



class CommandDropdown(ModelView):
    TEMPLATE_STR = '''

    '''

    @property
    def DOM_ELEMENT_CLASS(self):
        return f'cmd-dropdown {"open" if self.isopen else ""}'

    def __init__(self, subject: Session, parent: ComposerBox, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.isopen = False
        self.command_list = []
        self.search_string = ""

    def toggle(self):
        if not self.isopen:
            self.parent.close_dropdowns()
        self.isopen = not self.isopen
        self.update()

    def open(self):
        if not self.isopen:
            self.search_string = ""
            self.parent.close_dropdowns()
            self.isopen = True
            self.update()

    def close(self):
        if self.isopen:
            self.isopen = False
            self.update()
            self.search_string = ""

    def _filter_function(self, item:CommandDropdownOption):
        return self.search_string not in item.subject.name

    def filter_commands(self, searchstring):
        self.search_string = searchstring
        self.command_list.update()
        