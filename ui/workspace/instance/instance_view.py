from server.models.agents.agent_instance import AgentInstance
from ui.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.components.chat.chat import ChatView
from AgentOne.ui.panels.subagents_view import SidebarSubagentsView
from ui.components.tabs.instance.instanceheader import InstanceHeaderView
from ui.components.chat.filesystemlog_view import FilesystemLogView
from ui.components.chat.inter_agent_log import InterAgentLogView
from ui.components.chat.query_view import QueryView
from ui.components.chat.response_view import ResponseView
from AgentOne.ui.panels.memory_view import MemoryView
from AgentOne.ui.panels.settings_view import SettingsView
from AgentOne.ui.panels.filesystem_view import FilesystemView
from AgentOne.ui.panels.tasklist_view import TaskListView
from AgentOne.ui.panels.tools_view import ToolListView

class TabInstanceView(PyHtmlView):
    DOM_ELEMENT_CLASS = "tab-content resizable-container"
    DOM_ELEMENT_EXTRAS = ' data-orientation="vertical"'
    TEMPLATE_STR = """        
        <!-- Header Panel -->
        <div class="resizable-panel agentInstanceHeader" data-size-pc="5">
            {{ pyview.header.render() }}
        </div>

        <!-- Main Content Area (Chat + Right ) -->
        <div class="resizable-panel resizable-container" data-orientation="horizontal" data-size-pc="95">
            
            <!-- Chat Area Panel -->
            <div class="resizable-panel" data-orientation="vertical" data-size-pc="70">
                {{pyview.chat.render() }}
            </div>

            <!-- Right  Panel -->
            <div class="resizable-panel resizable-container" data-orientation="vertical" data-size-pc="30">
                <div class="resizable-panel resizable-container" data-orientation="vertical"  data-orientation="vertical" data-size-pc="30">
                    <div class="tabs">
                        <button class="tab-btn {{ 'active' if pyview.active_tab == 'filesystem' else '' }}" onclick="pyview.show_tab('filesystem')">Filesystem</button>
                        <button class="tab-btn {{ 'active' if pyview.active_tab == 'tasks' else '' }}" onclick="pyview.show_tab('tasks')">Tasks</button>
                        <button class="tab-btn {{ 'active' if pyview.active_tab == 'memory' else '' }}" onclick="pyview.show_tab('memory')">Memory</button>
                        <button class="tab-btn {{ 'active' if pyview.active_tab == 'settings' else '' }}" onclick="pyview.show_tab('settings')">Settings</button>
                        <button class="tab-btn {{ 'active' if pyview.active_tab == 'subagents' else '' }}" onclick="pyview.show_tab('subagents')">Subagents</button>
                        <button class="tab-btn {{ 'active' if pyview.active_tab == 'tools' else '' }}" onclick="pyview.show_tab('tools')">Tools</button>

                    </div>

                    {% if pyview.filesystem_view %}
                    <div id="tab-filesystem_{{ pyview.subject.id }}" class="tab-content {{ 'active' if pyview.active_tab == 'filesystem' else '' }}" {% if pyview.active_tab != 'filesystem' %}style="display: none;"{% endif %}>
                        {{ pyview.filesystem_view.render() }}
                    </div>
                    {% endif %}
                    <div id="tab-tasks_{{ pyview.subject.id }}" class="tab-content {{ 'active' if pyview.active_tab == 'tasks' else '' }}" {% if pyview.active_tab != 'tasks' %}style="display: none;"{% endif %}>
                        {{ pyview.task_list_view.render() }}
                    </div>

                    <div id="tab-memory_{{ pyview.subject.id }}" class="tab-content flex-column {{ 'active' if pyview.active_tab == 'memory' else '' }}" {% if pyview.active_tab != 'memory' %}style="display: none;"{% endif %}>
                        {% if pyview.memory_view %}
                            {{ pyview.memory_view.render() }}
                        {% endif %}
                    </div>

                    <div id="tab-settings_{{ pyview.subject.id }}" class="tab-content {{ 'active' if pyview.active_tab == 'settings' else '' }}" {% if pyview.active_tab != 'settings' %}style="display: none;"{% endif %}>
                        {{ pyview.settings_view.render() }}
                    </div>

                    <div id="tab-subagents_{{ pyview.subject.id }}" class="tab-content {{ 'active' if pyview.active_tab == 'subagents' else '' }}" {% if pyview.active_tab != 'subagents' %}style="display: none;"{% endif %}>
                        {{ pyview.subagents_view.render() }}
                    </div>

                    <div id="tab-tools_{{ pyview.subject.id }}" class="tab-content {{ 'active' if pyview.active_tab == 'tools' else '' }}" {% if pyview.active_tab != 'tools' %}style="display: none;"{% endif %}>
                        {{ pyview.tools_view.render() }}
                    </div>
                </div>


                <script>
                    parent = document.getElementById("{{pyview.uid}}");
                    initializeSplitForContainer(parent.parentNode);
                    parent.parentNode.querySelectorAll('.resizable-container').forEach(container => {
                        initializeSplitForContainer(container);
                    });
                </script>
            </div>
        </div>

        <!-- Instance-specific Agent Status Bar -->
        <div id="agent-status-bar_{{ pyview.subject.id }}" class="agent-status-bar agent-status-bar-hidden">
            <span id="agent-status-text_{{ pyview.subject.id }}" class="status-text"></span>
        </div>
        <script>
            parent = document.getElementById("{{pyview.uid}}");
            initializeSplitForContainer(parent);
            parent.querySelectorAll('.resizable-container').forEach(container => {
                initializeSplitForContainer(container);
            });        
        </script>
    """
    def __init__(self, subject: AgentInstance, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.agent_instance = subject
        self.selected_agent_instance_version = self.agent_instance.latest_agent_instance_version
        self.selected_agent_version = self.selected_agent_instance_version.agent_version

        self.chat = ChatView(self.agent_instance, self)
        self.header = InstanceHeaderView(subject, self)

        self.s = subject
        self.active_tab = 'filesystem'
        self.ri = subject.latest_agent_instance_version.get_runtime_instance()
        try:
            self.filesystem_view = FilesystemView(self.ri.filesystem, self)
        except:
            self.filesystem_view = None
        try:
            self.memory_view = MemoryView(self.ri.memory, self)
        except:
            self.memory_view = None
        self.settings_view = SettingsView(subject, self)
        self.task_list_view = TaskListView(subject, self)
        self.subagents_view = SidebarSubagentsView(self.selected_agent_version, self)
        self.tools_view = ToolListView(subject.agent_version, self)

    def show_tab(self, tab_name):
        self.active_tab = tab_name
        self.update()

    def _on_subject_died(self, wr) -> None:
        pass
