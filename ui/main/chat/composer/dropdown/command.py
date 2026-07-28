from __future__ import annotations
import json
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
        <div class="cmd-item-head">
            <div>
                <div class="cmd-item-name">
                    /{{pyview.task.task_definition.name}}
                    <span class="cmd-item-arg"> {{pyview.schema_hint}}</span>
                </div>
                <div class="cmd-item-desc">
                    {{pyview.task.description}}
                </div>
            </div>
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
        name = self.task.task_definition.name
        return (
            'onclick="'
            f"cmd_select_command('{name}')"
            '"'
        )


class CommandDropdown(ModelView):
    TEMPLATE_STR = '''
        {% if pyview.selected_command %}
            <div class="cmd-form" id="cmd-form-{{pyview.uid}}">
                <div class="cmd-form-header">
                    <span class="cmd-form-command">/{{pyview.selected_command.task_definition.name}}</span>
                    <span class="cmd-form-desc">{{pyview.selected_command.description}}</span>
                </div>
                <div class="cmd-form-fields">
                {% for field in pyview.form_fields() %}
                    <label class="cmd-form-label">
                        <span class="cmd-form-field-name">{{field.name}}{% if field.required %} <span class="cmd-form-required">*</span>{% endif %}</span>
                        {% if field.type == "boolean" %}
                            <select name="{{field.name}}" class="cmd-form-input cmd-form-select">
                                <option value="false">false</option>
                                <option value="true">true</option>
                            </select>
                        {% elif field.enum %}
                            <select name="{{field.name}}" class="cmd-form-input cmd-form-select">
                                {% for opt in field.enum %}
                                <option value="{{opt}}">{{opt}}</option>
                                {% endfor %}
                            </select>
                        {% else %}
                            <input name="{{field.name}}" type="{{field.input_type}}" class="cmd-form-input" placeholder="{{field.placeholder}}" {% if field.required %}required{% endif %}>
                        {% endif %}
                        {% if field.description %}
                            <span class="cmd-form-field-desc">{{field.description}}</span>
                        {% endif %}
                    </label>
                {% endfor %}
                </div>
                <div class="cmd-form-actions">
                    <button class="cmd-form-btn cmd-form-btn-back" onclick="pyview.back_to_list()">Back</button>
                    <button class="cmd-form-btn cmd-form-btn-send" onclick="submit_cmd_form_{{pyview.uid}}()">Send</button>
                </div>
            </div>
            <script>
            function submit_cmd_form_{{pyview.uid}}() {
                var form = document.querySelector('#cmd-form-{{pyview.uid}} .cmd-form-fields');
                var data = {};
                form.querySelectorAll('[name]').forEach(function(el) {
                    if (el.value !== '' || el.required) {
                        data[el.name] = el.value;
                    }
                });
                pyview.send_command(JSON.stringify(data));
            }
            function cmd_select_command(name) {
                pyview.select_command(name);
            }
            </script>
        {% else %}
            {{pyview.listView.render()}}
            <script>
            function cmd_select_command(name) {
                pyview.select_command(name);
            }
            </script>
        {% endif %}
    '''

    @property
    def DOM_ELEMENT_CLASS(self):
        cls = 'cmd-dropdown'
        if self.isopen:
            cls += ' open'
        if self.selected_command:
            cls += ' form-mode'
        return cls

    def __init__(self, subject: Session, parent: ComposerBox, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.isopen = False
        self.search_string = ""
        self.selected_command: TaskDefinitionVersion | None = None
        self.allowed_commands = ObservableList(subject.allowedCommands + subject.allowedTasks)
        self.listView = ObservableListView(self.allowed_commands, self, CommandDropdownOption, dom_element="div", filter_function=self._filter_function)

    def toggle(self):
        if not self.isopen:
            self.parent.footer.close_dropdowns()
        self.isopen = not self.isopen
        if not self.isopen:
            self.selected_command = None
        self.update()

    def open(self):
        if not self.isopen:
            self.search_string = ""
            self.selected_command = None
            self.parent.footer.close_dropdowns()
            self.isopen = True
            self.update()

    def close(self):
        if self.isopen:
            self.isopen = False
            self.selected_command = None
            self.update()
            self.search_string = ""

    def _filter_function(self, item: CommandDropdownOption):
        return self.search_string not in item.subject.task_definition.name and self.search_string not in item.subject.description

    def select_command(self, cmd_name: str) -> None:
        for item in self.allowed_commands:
            if item.task_definition.name == cmd_name:
                self.selected_command = item
                break
        self.update()

    def back_to_list(self) -> None:
        self.selected_command = None
        self.update()

    def send_command(self, json_data: str) -> None:
        data = json.loads(json_data)
        schema = self.selected_command.function_schema or {}
        properties = schema.get("properties", {})
        for key, value in list(data.items()):
            ptype = properties.get(key, {}).get("type", "string")
            if ptype in ("integer", "number"):
                try:
                    data[key] = int(value) if ptype == "integer" else float(value)
                except (ValueError, TypeError):
                    pass
            elif ptype == "boolean":
                data[key] = value.lower() == "true"
        cmd_name = self.selected_command.task_definition.name
        text = f"/{cmd_name} {json.dumps(data)}" if data else f"/{cmd_name}"
        self.close()
        self.parent.footer.send(text)

    def filter_commands(self, searchstring):
        self.search_string = searchstring
        self.listView.update()

    def form_fields(self) -> list[dict]:
        if not self.selected_command:
            return []
        schema = self.selected_command.function_schema
        if not schema or not isinstance(schema, dict):
            return []
        properties = schema.get("properties", {})
        required = set(schema.get("required", []) or [])
        fields = []
        for name, prop in properties.items():
            ptype = prop.get("type", "string")
            input_type = "text"
            if ptype == "integer" or ptype == "number":
                input_type = "number"
            elif ptype == "boolean":
                input_type = "boolean"
            fields.append({
                "name": name,
                "type": ptype,
                "input_type": input_type,
                "required": name in required,
                "placeholder": prop.get("description", ""),
                "description": prop.get("description", ""),
                "enum": prop.get("enum"),
            })
        return fields
