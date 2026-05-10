from __future__ import annotations
from ui.lib.model_view import ModelView
from server.models.agents.agent_version import AgentVersionModel
from ui.lib.queryset_view import QuerySetView


class AvailableToolView(ModelView):
    """Renders one available tool entry (AgentVersionAvailableTool)."""
    DOM_ELEMENT_CLASS = "AvailableToolView tool-item"

    TEMPLATE_STR = """
        <div class="tool-item-inner">
            <div class="tool-name">
                <strong>{{ pyview.subject.task_definition.name }}</strong>
                <span class="text-muted small">
                    via {{ pyview.subject.tool_agent_version.agent.name }}
                    v{{ pyview.subject.tool_agent_version.version_number }}
                </span>
            </div>
            <div class="tool-desc text-muted small">
                {{ pyview.subject.task_definition.description }}
            </div>
            <div class="tool-meta small">
                approval={{ pyview.subject.task_definition.requires_approval }}
            </div>
            <div class="tool-schema">
                <button class="btn btn-xs btn-default" onclick="pyview.toggle_schema()">
                    <i class="fa fa-code"></i> schema
                </button>
                <pre class="{{ 'hidden' if pyview.is_schema_hidden else '' }}">{{ pyview.subject.task_definition.function_schema }}</pre>
            </div>
        </div>
    """

    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_schema_hidden = True

    def toggle_schema(self):
        self.is_schema_hidden = not self.is_schema_hidden
        self.update()


class ToolsPanelView(ModelView):
    """Right-panel view listing all available tools for this agent version."""
    DOM_ELEMENT_CLASS = "ToolsPanelView"

    TEMPLATE_STR = """
        <div class="panel-section-header">
            Available tools
            <span class="text-muted small">
                ({{ pyview.subject.available_tools.count() }})
            </span>
        </div>
        <div class="panel-section-body">
            {{ pyview.tools_view.render() }}
        </div>
    """

    def __init__(self, subject: AgentVersionModel, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.tools_view = QuerySetView(
            subject=subject.available_tools.all(),
            parent=self,
            item_class=AvailableToolView,
        )