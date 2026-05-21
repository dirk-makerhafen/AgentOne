from __future__ import annotations
from server.models.agents.agent_version import AgentVersionModel
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.lib.queryset_view import QuerySetView
from ui.lib.model_view import ModelView


class SubagentView(ModelView):
    """Renders a single sub-agent version entry."""
    DOM_ELEMENT = "li"
    DOM_ELEMENT_CLASS = "SubagentView list-group-item"

    TEMPLATE_STR = """
        <i class="fa fa-sitemap list-icon"></i>
        <strong>{{ pyview.subject.agent.name }}</strong>
        <span class="text-muted small">v{{ pyview.subject.version_number }}</span>
        <span class="text-muted small">· {{ pyview.subject.created_at }}</span>
    """
    CSS_STR = '''
        /* Styling for the Sub-Agents tab in the right sidebar */

        .subagents-list-body {
            padding: 10px;
            width: 100%;
        }

        .subagents-list-body .list-group-item {
            display: flex;
            align-items: center;
            padding: 8px 10px;
            margin-bottom: 5px;
            border-radius: 4px;
            background-color: #f8f8f8;
            border: 1px solid #eee;
            font-size: 0.9em;
        }

        .subagents-list-body .list-group-item:hover {
            background-color: #f0f0f0;
        }

        .subagents-list-body .list-group-item .list-icon {
            margin-right: 10px;
            color: #007bff; /* A nice blue for icons */
        }

        .subagents-list-body .list-group-item strong {
            flex-grow: 1; /* Allows the name to take up available space */
            font-weight: 600;
            color: #333;
        }

        .subagents-list-body .list-group-item .badge {
            margin-left: 10px;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.7em;
            min-width: 60px; /* Ensure badges have a consistent minimum width */
            text-align: center;
        }

        .subagents-list-body .list-group-item p.text-muted {
            margin-bottom: 0;
            font-size: 0.75em;
            margin-left: 10px;
        }

        /* Specific badge colors */
        .badge-success {
            background-color: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }

        .badge-warning {
            background-color: #fff3cd;
            color: #856404;
            border: 1px solid #ffeeba;
        }

        .log-info {
            padding: 10px;
            width: 100%;
            font-style: italic;
            color: #6c757d;
        }
'''


class SubagentsPanelView(ModelView):
    """Right-panel view listing all sub-agent versions for this agent version."""
    DOM_ELEMENT_CLASS = "SubagentsPanelView"

    TEMPLATE_STR = """
        <div class="panel-section-header">Sub-agents</div>
        <div class="panel-section-body">
            {{ pyview.subagents_view.render() }}
        </div>
    """

    def __init__(self, subject: AgentVersionModel, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.subagents_view = QuerySetView(
            subject=subject.sub_agent_versions.all(),
            parent=self,
            item_class=SubagentView,
            dom_element="ul",
            dom_element_class="list-group",
        )