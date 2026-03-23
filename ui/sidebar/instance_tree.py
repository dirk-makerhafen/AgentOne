from __future__ import annotations
from typing import TYPE_CHECKING
from server.models.agents.agent_instance import AgentInstance
from server.models.agents.agent_instance_version import AgentInstanceVersion
from ui.lib.queryset_view import QuerySetView
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.app_view import UiAppView


def _resolve_app(parent):
    node = parent
    while node is not None:
        if hasattr(node, 'app'):
            return node.app
        node = getattr(node, 'parent', None)
    return None


class InstanceVersionNodeView(ModelView):
    """One AgentInstanceVersion — sub-agent spawned during execution."""
    DOM_ELEMENT_CLASS = "InstanceVersionNodeView"

    TEMPLATE_STR = """
        <div class="tree-node-header">
            {% if pyview.has_children %}
                <i class="fa fa-caret-{{ 'down' if pyview.is_expanded else 'right' }} tree-node-toggle"
                   onclick="event.stopPropagation(); pyview.toggle()"></i>
            {% else %}
                <span class="tree-node-spacer"></span>
            {% endif %}
            <i class="fa fa-code-fork tree-node-icon"></i>
            <span class="tree-node-name" onclick="pyview.select()">
                {{ pyview.subject.agent_instance.agent.name }}
                <span class="tree-node-meta">
                    v{{ pyview.subject.agent_version.version_number }} · #{{ pyview.subject.pk }}
                </span>
                {{ pyview.subject.agent_instance.name or '' }}
            </span>
            <div class="node-menu-container" onmouseleave="pyview.hide_menu()">
                <button class="btn btn-xs btn-default burgerbtn"
                        onclick="event.stopPropagation(); pyview.show_menu()">
                    <i class="fa fa-bars"></i>
                </button>
                <div id="iv-menu-{{ pyview.subject.id }}" class="node-menu-dropdown" style="display:none;">
                    <a href="#" onclick="event.stopPropagation(); pyview.hide_menu()">Delete instance</a>
                </div>
            </div>
        </div>
        <div class="tree-node-children" style="{{ 'display:block' if pyview.is_expanded else 'display:none' }}">
            <ul class="tree-view-list">{{ pyview.children_view.render() }}</ul>
        </div>
    """

    def __init__(self, subject: AgentInstanceVersion, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.app: UiAppView = _resolve_app(parent)
        self.is_expanded = False
        self.has_children = subject.child_agent_instance_versions.exists()
        self.children_view = QuerySetView(
            subject=subject.child_agent_instance_versions.all(),
            parent=self,
            item_class=InstanceVersionNodeView,
        )

    def toggle(self):
        self.is_expanded = not self.is_expanded
        self.update()

    def select(self):
        self.app.open_instance_tab(self.subject.agent_instance)
        self.update()

    def show_menu(self):
        self.eval_javascript(
            script='document.getElementById("iv-menu-" + args.id).style.display = "block";',
            id=self.subject.id,
        )

    def hide_menu(self):
        self.eval_javascript(
            script='document.getElementById("iv-menu-" + args.id).style.display = "none";',
            id=self.subject.id,
        )


class InstanceNodeView(ModelView):
    """Top-level AgentInstance node — expands to child instance versions."""
    DOM_ELEMENT = "li"
    DOM_ELEMENT_CLASS = "InstanceNodeView"

    TEMPLATE_STR = """
        <div id="agent_instance_{{ pyview.subject.id }}"
             class="tree-leaf-instance {{ 'selected-instance' if pyview.is_selected else '' }}">
            {% if pyview.has_children %}
                <i class="fa fa-caret-{{ 'down' if pyview.is_expanded else 'right' }} tree-node-toggle"
                   onclick="event.stopPropagation(); pyview.toggle()"></i>
            {% else %}
                <span class="tree-node-spacer"></span>
            {% endif %}
            <i class="fa fa-users tree-node-icon"></i>
            <span class="tree-node-name" onclick="pyview.select()">
                {{ pyview.subject.agent.name }}
                {% if pyview.subject.latest_agent_instance_version %}
                    <span class="tree-node-meta">
                        v{{ pyview.subject.latest_agent_instance_version.agent_version.version_number }}
                        · #{{ pyview.subject.latest_agent_instance_version.pk }}
                    </span>
                {% endif %}
                {{ pyview.subject.name or '' }}
            </span>
            <div class="node-menu-container" onmouseleave="pyview.hide_menu()">
                <button class="btn btn-xs btn-default burgerbtn"
                        onclick="event.stopPropagation(); pyview.show_menu()">
                    <i class="fa fa-bars"></i>
                </button>
                <div id="i-menu-{{ pyview.subject.id }}" class="node-menu-dropdown" style="display:none;">
                    <a href="#" onclick="event.stopPropagation(); pyview.remove()">Remove instance</a>
                </div>
            </div>
        </div>
        <div class="tree-node-children" style="{{ 'display:block' if pyview.is_expanded else 'display:none' }}">
            <ul class="tree-view-list">{{ pyview.children_view.render() }}</ul>
        </div>
    """

    def __init__(self, subject: AgentInstance, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.app: UiAppView = _resolve_app(parent)
        self.is_selected = False
        self.is_expanded = False
        latest = subject.latest_agent_instance_version
        child_qs = (
            latest.child_agent_instance_versions.all()
            if latest is not None
            else AgentInstanceVersion.objects.none()
        )
        self.has_children = child_qs.exists()
        self.children_view = QuerySetView(
            subject=child_qs,
            parent=self,
            item_class=InstanceVersionNodeView,
        )

    def toggle(self):
        self.is_expanded = not self.is_expanded
        self.update()

    def select(self):
        self.app.open_instance_tab(self.subject)
        self.update()

    def remove(self):
        self.hide_menu()  # TODO

    def show_menu(self):
        self.eval_javascript(
            script='document.getElementById("i-menu-" + args.id).style.display = "block";',
            id=self.subject.id,
        )

    def hide_menu(self):
        self.eval_javascript(
            script='document.getElementById("i-menu-" + args.id).style.display = "none";',
            id=self.subject.id,
        )


class InstanceTreeView(ModelView):
    DOM_ELEMENT_CLASS = "InstanceTreeView"

    TEMPLATE_STR = """
        <ul class="tree-view-list">{{ pyview.instances_view.render() }}</ul>
    """

    def __init__(self, subject: "UiApp", parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.app: UiAppView = parent.app
        self.instances_view = QuerySetView(
            subject=subject.agent_instances.filter(parent=None),
            parent=self,
            item_class=InstanceNodeView,
        )