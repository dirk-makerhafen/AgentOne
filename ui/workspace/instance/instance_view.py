from __future__ import annotations
from ui.panels.monitor import MonitorPanelView
from ui.lib.model_view import ModelView
from server.models.agents.agent_instance import AgentInstance
from ui.workspace.instance.instance_header import InstanceHeaderView
from ui.workspace.instance.chat_workspace import ChatWorkspaceView
from ui.panels.filesystem import FilesystemPanelView
from ui.panels.tasks import TasksPanelView
from ui.panels.subagents import SubagentsPanelView
from ui.panels.tools import ToolsPanelView
from ui.panels.settings import SettingsPanelView


def _is_chat_agent(agent_instance: AgentInstance) -> bool:
    try:
        from runtime.agents.chat_agent import ChatAgent
        agent_version = agent_instance.latest_agent_instance_version.agent_version
        return issubclass(agent_version.get_runtime_class(), ChatAgent)
    except Exception:
        return False


class InstanceWorkspaceView(ModelView):
    """
    Per-instance tab layout:
      header (fixed height) / chat-or-task (grows) / right panels (fixed width)
    """
    DOM_ELEMENT_CLASS = "InstanceWorkspaceView resizable-container"
    DOM_ELEMENT_EXTRAS = 'data-orientation="vertical"'

    TEMPLATE_STR = """
        <!-- Header strip -->
        <div class="resizable-panel iw-header" data-size-pc="5">
            {{ pyview.header.render() }}
        </div>

        <!-- Content row -->
        <div class="resizable-panel resizable-container" data-orientation="horizontal" data-size-pc="95">

            <!-- Main workspace -->
            <div class="resizable-panel" data-size-pc="70">
                {{ pyview.main_workspace.render() }}
            </div>

            <!-- Right panels -->
            <div class="resizable-panel resizable-container iw-right-panels" data-orientation="vertical" data-size-pc="30">

                <!-- Panel tab bar -->
                <div class="iw-panel-tabs">
                    <button class="iw-panel-tab {{ 'active' if pyview.active_panel == 'filesystem' else '' }}"
                            onclick="pyview.show_panel('filesystem')">Filesystem</button>
                    <button class="iw-panel-tab {{ 'active' if pyview.active_panel == 'tasks' else '' }}"
                            onclick="pyview.show_panel('tasks')">Tasks</button>
                    <button class="iw-panel-tab {{ 'active' if pyview.active_panel == 'settings' else '' }}"
                            onclick="pyview.show_panel('settings')">Settings</button>
                    <button class="iw-panel-tab {{ 'active' if pyview.active_panel == 'subagents' else '' }}"
                            onclick="pyview.show_panel('subagents')">Sub-agents</button>
                    <button class="iw-panel-tab {{ 'active' if pyview.active_panel == 'tools' else '' }}"
                            onclick="pyview.show_panel('tools')">Tools</button>
                    <button class="iw-panel-tab {{ 'active' if pyview.active_panel == 'monitor' else '' }}"
                            onclick="pyview.show_panel('monitor')">Monitor</button>
                </div>

                <!-- Panel content areas -->
                <div class="iw-panel-content {{ 'active' if pyview.active_panel == 'filesystem' else '' }}"
                     style="{{ '' if pyview.active_panel == 'filesystem' else 'display:none' }}">
                    {% if pyview.filesystem_panel %}
                        {{ pyview.filesystem_panel.render() }}
                    {% else %}
                        <p class="iw-panel-empty">Filesystem not available.</p>
                    {% endif %}
                </div>

                <div class="iw-panel-content {{ 'active' if pyview.active_panel == 'tasks' else '' }}"
                     style="{{ '' if pyview.active_panel == 'tasks' else 'display:none' }}">
                    {{ pyview.tasks_panel.render() }}
                </div>

                <div class="iw-panel-content {{ 'active' if pyview.active_panel == 'settings' else '' }}"
                     style="{{ '' if pyview.active_panel == 'settings' else 'display:none' }}">
                    {{ pyview.settings_panel.render() }}
                </div>

                <div class="iw-panel-content {{ 'active' if pyview.active_panel == 'subagents' else '' }}"
                     style="{{ '' if pyview.active_panel == 'subagents' else 'display:none' }}">
                    {% if pyview.subagents_panel %}
                        {{ pyview.subagents_panel.render() }}
                    {% else %}
                        <p class="iw-panel-empty">No sub-agents.</p>
                    {% endif %}
                </div>

                <div class="iw-panel-content {{ 'active' if pyview.active_panel == 'tools' else '' }}"
                     style="{{ '' if pyview.active_panel == 'tools' else 'display:none' }}">
                    {% if pyview.tools_panel %}
                        {{ pyview.tools_panel.render() }}
                    {% else %}
                        <p class="iw-panel-empty">No tools.</p>
                    {% endif %}
                </div>

                <div class="iw-panel-content {{ 'active' if pyview.active_panel == 'monitor' else '' }}"
                     style="{{ '' if pyview.active_panel == 'monitor' else 'display:none' }}">
                    {% if pyview.monitor_panel %}
                        {{ pyview.monitor_panel.render() }}
                    {% else %}
                        <p class="iw-panel-empty">Nothing to monitor.</p>
                    {% endif %}
                </div>   
            
                <script>
                    (function() {
                        var el = document.getElementById("{{ pyview.uid }}");
                        if (el) {
                            initializeSplitForContainer(el.parentNode);
                            el.parentNode.querySelectorAll('.resizable-container')
                              .forEach(function(c) { initializeSplitForContainer(c); });
                        }
                    })();
                </script>
            </div>
        </div>

        <!-- Status bar (hidden until agent pushes a status) -->
        <div id="status-bar-{{ pyview.subject.id }}" class="iw-status-bar iw-status-bar-hidden">
            <span class="status-text"></span>
        </div>

        <script>
            (function() {
                var el = document.getElementById("{{ pyview.uid }}");
                if (el) {
                    initializeSplitForContainer(el);
                    el.querySelectorAll('.resizable-container')
                      .forEach(function(c) { initializeSplitForContainer(c); });
                }
            })();
        </script>
    """

    CSS_STR = """
/* Right panel strip */
.iw-right-panels { overflow: hidden; }

.iw-panel-tabs {
    display: flex;
    border-bottom: 1px solid var(--border);
    background: var(--bg-subtle);
    flex-shrink: 0;
    overflow-x: auto;
    scrollbar-width: none;
}
.iw-panel-tab {
    flex-shrink: 0;
    padding: 5px 10px;
    font-size: 0.78em;
    border: none;
    border-right: 1px solid var(--border);
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.12s, color 0.12s;
}
.iw-panel-tab:hover  { background: var(--bg-raised); color: var(--text); }
.iw-panel-tab.active { background: var(--bg); color: var(--accent); font-weight: 500; }

.iw-panel-content {
    flex-grow: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
}
.iw-panel-content.active { display: flex; }
.iw-panel-empty {
    padding: 16px;
    color: var(--text-faint);
    font-size: 0.85em;
    font-style: italic;
}

/* Status bar */
.iw-status-bar {
    background: var(--text-muted);
    color: #fff;
    text-align: center;
    font-size: 0.8em;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .05em;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: height 0.2s, opacity 0.2s;
    height: 22px;
}
.iw-status-bar-hidden { height: 0; opacity: 0; overflow: hidden; }
    """

    def __init__(self, subject: AgentInstance, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)

        latest = subject.latest_agent_instance_version
        agent_version = latest.agent_version if latest else None

        self.header = InstanceHeaderView(subject, self)
        self.active_panel = 'filesystem'

        # Main workspace — always ChatWorkspaceView until TaskWorkspaceView exists
        self.main_workspace = ChatWorkspaceView(subject, self)
        # TODO: activate when TaskWorkspaceView is implemented
        # self.main_workspace = ChatWorkspaceView(subject, self) if _is_chat_agent(subject) \
        #                        else TaskWorkspaceView(subject, self)

        # Right panels
        self.filesystem_panel = None
        if latest:
            try:
                ri = latest.get_runtime_instance()
                self.filesystem_panel = FilesystemPanelView(ri.filesystem, self)
            except Exception:
                pass

        self.tasks_panel    = TasksPanelView(subject, self)
        self.settings_panel = SettingsPanelView(subject, self)
        self.subagents_panel = SubagentsPanelView(agent_version, self) if agent_version else None
        self.tools_panel     = ToolsPanelView(agent_version, self)     if agent_version else None
        self.monitor_panel     = MonitorPanelView(agent_version, self)     if agent_version else None

    def show_panel(self, panel_name: str):
        self.active_panel = panel_name
        self.update()

    def _on_subject_died(self, wr) -> None:
        pass