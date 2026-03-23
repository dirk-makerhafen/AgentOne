from __future__ import annotations
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.lib.queryset_view import QuerySetView
from ui.lib.model_view import ModelView


class AgentTaskDefinitionView(ModelView):
    """One row of task definition detail — used inside AgentVersionView table."""
    DOM_ELEMENT_CLASS = "AgentTaskDefinitionView"

    TEMPLATE_STR = """
        <tr>
            <td>
                <strong>{{ pyview.subject.name }}</strong>
                <span class="badge text-muted small">{{ pyview.subject.task_type }}</span>
            </td>
            <td>
                <span class="text-muted small">{{ pyview.subject.description }}</span>
                <div class="small">
                    approval={{ pyview.subject.requires_approval }}
                    retries={{ pyview.subject.max_retries }}
                    priority={{ pyview.subject.priority }}
                    delay={{ pyview.subject.retry_delay }}s
                    {% if pyview.subject.trigger %}trigger={{ pyview.subject.trigger }}{% endif %}
                </div>
                <button class="btn btn-xs btn-default" onclick="pyview.toggle_schema()">
                    schema
                </button>
                <pre class="{{ 'hidden' if pyview.is_schema_hidden else '' }}">{{ pyview.subject.function_schema }}</pre>
            </td>
        </tr>
    """

    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_schema_hidden = True

    def toggle_schema(self):
        self.is_schema_hidden = not self.is_schema_hidden
        self.update()


class AgentTaskDefinitionsView(QuerySetView):
    """
    Renders task definitions as <tr> rows inside an AgentVersionView table.
    Subclasses QuerySetView to emit bare rows without a wrapper container.
    """
    TEMPLATE_STR = """
        {% for item in pyview.get_items() %}
            {{ item.render() }}
        {% endfor %}
    """

    def __init__(self, subject, parent, item_class=None, **kwargs):
        super().__init__(
            subject=subject,
            parent=parent,
            item_class=item_class or AgentTaskDefinitionView,
            **kwargs,
        )


class AgentTaskInstanceView(ModelView):
    """One-row summary of an AgentTaskInstance."""
    DOM_ELEMENT_CLASS = "AgentTaskInstanceView task-instance-row"

    TEMPLATE_STR = """
        <div class="task-instance-inner">
            <span class="task-def-name">
                {{ pyview.subject.agent_task_definition.name }}
            </span>
            <span class="text-muted small">
                calls={{ pyview.subject.agent_task_calls.count() }}
                deps={{ pyview.subject.taskinstance_arg_references.count() }}
                subtasks={{ pyview.subject.taskinstance_sub_taskinstances.count() }}
                on_success={{ pyview.subject.taskinstances_on_success_callbacks.count() }}
                on_error={{ pyview.subject.taskinstances_on_error_callbacks.count() }}
            </span>
        </div>
    """


class AgentTaskInstancesView(ModelView):
    """List of AgentTaskInstances for an agent version or instance."""
    DOM_ELEMENT_CLASS = "AgentTaskInstancesView"

    TEMPLATE_STR = """
        <h4>Task instances</h4>
        {{ pyview.instances_view.render() }}
    """

    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.instances_view = QuerySetView(
            subject=subject,
            parent=self,
            item_class=AgentTaskInstanceView,
        )