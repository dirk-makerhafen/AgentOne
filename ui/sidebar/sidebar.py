from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.sidebar.agent_tree import AgentTreeView
from ui.sidebar.instance_tree import InstanceTreeView

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.app_view import UiAppView


class SidebarView(ModelView):
    DOM_ELEMENT_CLASS = "SidebarView resizable-panel flex-column"

    TEMPLATE_STR = """
        <div class="sidebar-header">
            <span>Agents</span>
            <button class="btn btn-xs btn-default" onclick="pyview.add_agent()">
                <i class="fa fa-plus"></i>
            </button>
        </div>

        <div class="sidebar-mode-bar">
            <button class="sidebar-mode-btn {{ 'active' if pyview.view_mode == 'agent' else '' }}"
                    onclick="pyview.set_view_mode('agent')" title="Agents">
                <i class="fa fa-users"></i>
            </button>
            <button class="sidebar-mode-btn {{ 'active' if pyview.view_mode == 'dir' else '' }}"
                    onclick="pyview.set_view_mode('dir')" title="Directory">
                <i class="fa fa-folder-open"></i>
            </button>
            <button class="sidebar-mode-btn {{ 'active' if pyview.view_mode == 'instance' else '' }}"
                    onclick="pyview.set_view_mode('instance')" title="Hierarchy">
                <i class="fa fa-code-fork"></i>
            </button>
        </div>

        <div class="sidebar-tree-body">
            {% if pyview.view_mode == 'agent' %}
                {{ pyview.agent_tree.render() }}
            {% elif pyview.view_mode == 'instance' %}
                {{ pyview.instance_tree.render() }}
            {% else %}
                <div class="sidebar-placeholder">Directory view coming soon.</div>
            {% endif %}
        </div>

        <div class="sidebar-nav-ribbons">
            <button class="nav-ribbon" onclick="pyview.app.open_buildin_tab('systems')">
                <i class="fa fa-tasks"></i> Systems
            </button>
            <button class="nav-ribbon" onclick="pyview.app.open_buildin_tab('providers')">
                <i class="fa fa-cloud"></i> API Providers
            </button>
        </div>
    """

    CSS_STR = """
.SidebarView {
    background: var(--bg);
    border-right: 1px solid var(--border);
    min-width: 0;
    overflow: hidden;
}
.sidebar-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 10px;
    font-size: 0.75em;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .05em;
    color: var(--text-muted);
    background: var(--bg-subtle);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
}
.sidebar-mode-bar {
    display: flex;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
}
.sidebar-mode-btn {
    flex: 1;
    padding: 5px 0;
    font-size: 0.85em;
    border: none;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
}
.sidebar-mode-btn:hover  { background: var(--bg-subtle); color: var(--text); }
.sidebar-mode-btn.active { background: var(--bg); color: var(--accent); border-bottom: 2px solid var(--accent); }

.sidebar-tree-body { flex-grow: 1; overflow-y: auto; padding: 4px 0; }
.sidebar-placeholder { padding: 12px; font-size: 0.85em; color: var(--text-faint); }

/* ── Shared tree primitives (used by both agent_tree and instance_tree) ── */
.tree-view-list { list-style: none; padding: 0 0 0 4px; margin: 0; }
.tree-view-list li { padding: 0; }

.tree-node-header,
.tree-leaf-instance {
    display: flex;
    align-items: center;
    cursor: pointer;
    padding: 2px 6px 2px 0;
    border-radius: var(--r-sm);
    transition: background 0.12s;
    white-space: nowrap;
    min-width: 0;
}
.tree-node-header:hover,
.tree-leaf-instance:hover { background: var(--bg-subtle); }
.tree-leaf-instance.selected-instance { background: var(--badge-active-bg); }
.tree-leaf-instance.selected-instance .tree-node-name { font-weight: 600; }

.tree-node-toggle { width: 14px; text-align: center; flex-shrink: 0; color: var(--text-faint); font-size: 0.8em; }
.tree-node-spacer { width: 14px; flex-shrink: 0; }
.tree-node-icon   { margin: 0 4px; color: var(--text-muted); font-size: 0.85em; flex-shrink: 0; }
.tree-node-name   { flex-grow: 1; flex-shrink: 1; font-size: 0.88em; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; min-width: 0; }
.tree-node-meta   { font-size: 0.75em; color: var(--text-faint); flex-shrink: 0; margin: 0 4px; white-space: nowrap; }
.tree-node-children { margin-left: 10px; border-left: 1px solid var(--border-light); }

/* Context menus */
.node-menu-container { position: relative; flex-shrink: 0; margin-left: 2px; }
.burgerbtn {padding: 1px 4px; font-size: 0.7em; transition: opacity 0.15s; }
.tree-node-header:hover .burgerbtn,
.tree-leaf-instance:hover .burgerbtn { opacity: 1; }
.node-menu-dropdown {
    position: absolute; right: 0; top: 100%; z-index: 100;
    background: var(--bg); border: 1px solid var(--border);
    border-radius: var(--r-sm); box-shadow: var(--shadow-md);
    min-width: 130px; overflow: hidden;
}
.node-menu-dropdown a {
    display: block; padding: 6px 12px; font-size: 0.85em;
    color: var(--text); text-decoration: none; white-space: nowrap; transition: background 0.1s;
}
.node-menu-dropdown a:hover { background: var(--bg-subtle); color: var(--accent); }
    """

    def __init__(self, subject: "UiApp", parent: "UiAppView", **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.app: UiAppView = parent
        self.view_mode = "instance"
        self.agent_tree = AgentTreeView(subject, self)
        self.instance_tree = InstanceTreeView(subject, self)

    def set_view_mode(self, mode: str):
        self.view_mode = mode
        self.update()

    def add_agent(self):
        pass  # TODO