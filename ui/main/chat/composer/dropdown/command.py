from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.session import Session
from server.models.tasks.task_definition_version import TaskDefinitionVersion
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.lib.observableList import ObservableList
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.observable_list_view import ObservableListView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
if TYPE_CHECKING:
    from ui.main.chat.chat import Chat
    from ui.main.chat.composer.box import ComposerBox


class CommandDropdownOption(ModelView):
    TEMPLATE_STR = '''
        <div class="cmd-item-name">
            /{{pyview.task.task_definition.name}}
            <span class="cmd-item-arg"> {{pyview.schema_hint}}</span>
        </div>
        <div class="cmd-item-desc">
            {{pyview.task.description}}
        </div>
    '''

    @property
    def DOM_ELEMENT_CLASS(self):
        return f'cmd-item'

    def __init__(self, subject:TaskDefinitionVersion, parent: PyHtmlView | PyHtmlGuiInstance, **kwargs):
        self.task = subject
        super().__init__(subject, parent, **kwargs)

    @property
    def schema_hint(self) -> str:
        schema = self.task.function_schema
        if not schema or not isinstance(schema, dict):
            return ""
        required = schema.get("required", [])
        if not required:
            return ""
        return " ".join(f"<{n}>" for n in required)

    @property
    def DOM_ELEMENT_EXTRAS(self):
        composer_uid = self.parent.parent.parent.uid
        name = self.task.task_definition.name
        hint = self.schema_hint
        fill = f"/{name} {hint}" if hint else f"/{name} "
        return (
            'onclick="'
            f"var el=document.getElementById('input_{composer_uid}');"
            f"el.value='{fill}';"
            f"el.setSelectionRange(el.value.length,el.value.length);"
            f'el.focus();'
            f"select_command('{name}')"
            '"'
        )

class CommandDropdown(ModelView):
    TEMPLATE_STR = '''
        {{pyview.listView.render()}}
        <script>
        function select_command(name){
            pyview.select_command(name);
        }
        </script>
    '''

    @property
    def DOM_ELEMENT_CLASS(self):
        return f'cmd-dropdown {"open" if self.isopen else ""}'

    def __init__(self, subject: Session, parent: ComposerBox, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.isopen = False
        self.command_list = []
        self.search_string = ""
        self.allowed_commands = ObservableList(subject.allowedCommands+ subject.allowedTasks)
        self.listView = ObservableListView(self.allowed_commands, self, CommandDropdownOption, dom_element="div", filter_function=self._filter_function)
        

    def toggle(self):
        if not self.isopen:
            self.parent.footer.close_dropdowns()
        self.isopen = not self.isopen
        self.update()

    def open(self):
        if not self.isopen:
            self.search_string = ""
            self.parent.footer.close_dropdowns()
            self.isopen = True
            self.update()

    def close(self):
        if self.isopen:
            self.isopen = False
            self.update()
            self.search_string = ""

    def _filter_function(self, item:CommandDropdownOption):
        return self.search_string not in item.subject.task_definition.name and self.search_string  not in item.subject.description

    def select_command(self, cmd_name: str) -> None:
        self.close()

    def filter_commands(self, searchstring):
        self.search_string = searchstring
        self.listView.update()
        