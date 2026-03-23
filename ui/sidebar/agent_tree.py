from __future__ import annotations
from typing import TYPE_CHECKING
from server.models.agents.agent import Agent
from server.models.agents.agent_version import AgentVersion
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.app_view import UiAppView


class AgentVersionNodeView(ModelView):
    DOM_ELEMENT = "li"
    DOM_ELEMENT_CLASS = "AgentVersionNodeView"

    TEMPLATE_STR = """
        <div class="tree-node-header version-node">
            <span class="tree-node-spacer"></span>
            <i class="fa fa-code tree-node-icon"></i>
            <span class="tree-node-name" onclick="pyview.select()">
                v{{ pyview.subject.version_number }}
                <span class="tree-node-meta">{{ pyview.subject.created_at.strftime('%Y-%m-%d') }}</span>
            </span>
            <div class="node-menu-container" onmouseleave="pyview.hide_menu()">
                <button class="btn btn-xs btn-default burgerbtn"
                        onclick="event.stopPropagation(); pyview.show_menu()">
                    <i class="fa fa-bars"></i>
                </button>
                <div id="version-menu-{{ pyview.subject.id }}" class="node-menu-dropdown" style="display:none;">
                    <a href="#" onclick="event.stopPropagation(); pyview.hide_menu()">Edit version</a>
                    <a href="#" onclick="event.stopPropagation(); pyview.hide_menu()">Delete version</a>
                </div>
            </div>
        </div>
    """

    def __init__(self, subject: AgentVersion, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.app: UiAppView = self._resolve_app(parent)

    @staticmethod
    def _resolve_app(parent):
        node = parent
        while node is not None:
            if hasattr(node, 'app'):
                return node.app
            node = getattr(node, 'parent', None)
        return None

    def select(self):
        self.app.open_agent_tab(self.subject.agent)
        self.update()

    def show_menu(self):
        self.eval_javascript(
            script='document.getElementById("version-menu-" + args.id).style.display = "block";',
            id=self.subject.id,
        )

    def hide_menu(self):
        self.eval_javascript(
            script='document.getElementById("version-menu-" + args.id).style.display = "none";',
            id=self.subject.id,
        )


class AgentNodeView(ModelView):
    DOM_ELEMENT = "li"
    DOM_ELEMENT_CLASS = "AgentNodeView"

    TEMPLATE_STR = """
        <div class="tree-node-header">
            <i class="fa fa-caret-{{ 'down' if pyview.is_expanded else 'right' }} tree-node-toggle"
               onclick="event.stopPropagation(); pyview.toggle()"></i>
            <i class="fa fa-users tree-node-icon"></i>
            <span class="tree-node-name" onclick="pyview.select()">
                {{ pyview.subject.name }}
                {% if pyview.subject.latest_agent_version %}
                    <span class="tree-node-meta">v{{ pyview.subject.latest_agent_version.version_number }}</span>
                {% endif %}
            </span>
            <span class="tree-node-meta">{{ pyview.subject.related_agent_instances.count() }}i</span>
            <div class="node-menu-container" onmouseleave="pyview.hide_menu()">
                <button class="btn btn-xs btn-default burgerbtn"
                        onclick="event.stopPropagation(); pyview.show_menu()">
                    <i class="fa fa-bars"></i>
                </button>
                <div id="agent-menu-{{ pyview.subject.id }}" class="node-menu-dropdown" style="display:none;">
                    <a href="#" onclick="event.stopPropagation(); pyview.edit()">Edit agent</a>
                    <a href="#" onclick="event.stopPropagation(); pyview.delete()">Delete agent</a>
                </div>
            </div>
        </div>
        <div class="tree-node-children" style="{{ 'display:block' if pyview.is_expanded else 'display:none' }}">
            <ul class="tree-view-list">
                {% for version in pyview.subject.agent_versions.order_by('-version_number').all() %}
                    {{ pyview.get_version_view(version).render() }}
                {% endfor %}
            </ul>
        </div>
    """

    def __init__(self, subject: Agent, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.app: UiAppView = parent.app
        self.is_expanded = False
        self._version_views: dict[int, AgentVersionNodeView] = {}

    def get_version_view(self, version: AgentVersion) -> AgentVersionNodeView:
        if version.id not in self._version_views:
            self._version_views[version.id] = AgentVersionNodeView(version, self)
        return self._version_views[version.id]

    def toggle(self):
        self.is_expanded = not self.is_expanded
        self.update()

    def select(self):
        self.app.open_agent_tab(self.subject)
        self.update()

    def edit(self):
        self.app.open_agent_tab(self.subject)
        self.hide_menu()

    def delete(self):
        self.hide_menu()  # TODO

    def show_menu(self):
        self.eval_javascript(
            script='document.getElementById("agent-menu-" + args.id).style.display = "block";',
            id=self.subject.id,
        )

    def hide_menu(self):
        self.eval_javascript(
            script='document.getElementById("agent-menu-" + args.id).style.display = "none";',
            id=self.subject.id,
        )


class AgentTreeView(ModelView):
    DOM_ELEMENT_CLASS = "AgentTreeView sidebar-tree-body"

    TEMPLATE_STR = """
        <ul class="tree-view-list">
            {% for pk, view in pyview.agent_views.items() %}
                {{ view.render() }}
            {% endfor %}
        </ul>
    """

    def __init__(self, subject: "UiApp", parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.app: UiAppView = parent.app
        self.agent_views: dict[int, AgentNodeView] = {}
        self._rebuild()

    def _rebuild(self):
        self.agent_views = {
            agent.id: AgentNodeView(agent, self)
            for agent in self.subject.agents.all()
        }
        self.update()

    def _on_subject_updated(self, source, **kwargs):
        self._rebuild()