from server.models.agents.agent_profile import AgentProfile
from server.models.agents.agent_instance import AgentInstance
from server.models.agents.agent_instance_version import AgentInstanceVersion
from server.models.agents.agent_version import AgentVersion
from ui.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView

class InstanceHeaderView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="instance-header-container">
    agentinstanceversion:{{pyview.latest_agent_instance_version}}
        <div class="header-column">
            <div class="header-item"><i class="fa fa-user-circle header-icon" title="Agent"></i> <b>Agent:</b> <span class="header-value" id="instance-agent-name_{{ pyview.subject.id }}">{{ pyview.subject.agent.name }}</span></div>
            <div class="header-item instance-name-container" id="instance-name-container">
                <i class="fa fa-hashtag header-icon" title="Instance"></i> <b>Instance:</b>
                <span class="header-value instance-editable-name" contenteditable="true" onblur="pyview.handle_instance_name_edit(this)" data-original-value="{{ pyview.subject.name }}">
                    {% if pyview.subject.name %}{{ pyview.subject.name }}{% else %}Unnamed Instance{% endif %}
                </span>
            </div>
            <div class="header-item" id="instance-model-container">
                <i class="fa fa-microchip header-icon" title="Model"></i> <b>Model:</b>
                <select id="instance-model-select_{{ pyview.subject.id }}" 
                        onchange="pyview.handle_instance_model_change(this)" 
                        onblur="pyview.handle_instance_model_change(this)" 
                        class="header-value edit-select">
                    {% for model in pyview.subject.all_available_models %}
                        <option value="{{ model.id }}" {{ 'selected' if model.id == pyview.subject.model_id else '' }}>{{ model.name }}</option>
                    {% endfor %}
                </select>
            </div>
        </div>

        <div class="header-column">
            <div class="header-item">
                <i class="fa fa-code header-icon" title="Pinned Version"></i> <b>Version:</b> 
                <span class="header-value">{% if pyview.agent_version %}v{{ pyview.agent_version.version_number }}{% else %}N/A{% endif %}</span>
            </div>
            <div class="header-item">
                <i class="fa fa-code-fork header-icon" title="Pinned Variant"></i> <b>Variant:</b> 
                <span class="header-value">{% if pyview.pinned_agent_profile %}{{ pyview.pinned_agent_profile.name }}{% else %}N/A{% endif %}</span>
            </div>
            <div class="header-item" id="instance-autorun-container">
                <i class="fa fa-cogs header-icon" title="Auto-Run Steps"></i> <b>Auto-Run:</b>
                <span class="header-value" id="instance-autorun-count_{{ pyview.subject.id }}">{{ pyview.subject.automated_step_count }} / </span>
                <input type="number" 
                       id="limit-max-automated-steps-input_{{ pyview.subject.id }}" 
                       value="{{ pyview.subject.effective_limit_max_automated_steps }}" 
                       onchange="pyview.handle_auto_run_limit_change(this)" 
                       onblur="pyview.handle_auto_run_limit_change(this)" 
                       class="edit-input"/>
            </div>
            <div class="header-item" id="instance-system-container">
                <i class="fa fa-server header-icon" title="System"></i> <b>System:</b>
                <select id="instance-system-select_{{ pyview.subject.id }}" 
                        onchange="pyview.handle_instance_system_change(this)" 
                        onblur="pyview.handle_instance_system_change(this)" 
                        class="header-value edit-select">
                    {% for system in pyview.subject.all_available_systems %}
                        <option value="{{ system.id }}" {{ 'selected' if system.id == pyview.subject.system_id else '' }}>{{ system.name }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="header-item">
                <i class="fa fa-arrow-circle-o-up header-icon" title="Tokens Sent (Prompt)"></i> <span class="header-value" id="instance-tokens-sent_{{ pyview.subject.id }}">{{ pyview.subject.total_prompt_tokens }}</span>
                <i class="fa fa-arrow-circle-o-down header-icon" title="Tokens Received (Completion)" style="margin-left: 10px;"></i><span class="header-value" id="instance-tokens-received_{{ pyview.subject.id }}">{{ pyview.subject.total_completion_tokens }}</span>
            </div>
        </div>

        
        <div class="header-column">
            <div class="header-item full-width instance-description-container" id="instance-description-container">
                <div class="display-view instance-description-display-view">
                    <span class="header-value instance-editable-description" contenteditable="true" onblur="pyview.handle_instance_description_text_edit(this)" data-original-value="{{ pyview.subject.description_text }}">
                        {% if pyview.subject.description_text %}{{ pyview.subject.description_text }}{% else %}No description provided.{% endif %}
                    </span>
                    <span class="description-bottom-right">Description</span>
                </div>
            </div>
        </div>
    </div>
    """
    def __init__(self, subject: AgentInstance, parent: PyHtmlView | PyHtmlGuiInstance, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.agent_instance = subject
        self.latest_agent_instance_version:AgentInstanceVersion|None= None
        self.agent_version:AgentVersion|None = None
        self.pinned_agent_profile:AgentProfile|None = None
        self.reload()

    def reload(self):
        self.latest_agent_instance_version = self.agent_instance.latest_agent_instance_version
        self.agent_version = self.latest_agent_instance_version.agent_version
        self.pinned_agent_profile = self.latest_agent_instance_version.pinned_agent_profile


    def handle_instance_name_edit(self, element): pass
    def handle_instance_model_change(self, element): pass
    def handle_auto_run_limit_change(self, element): pass
    def handle_instance_system_change(self, element): pass
    def handle_instance_description_text_edit(self, element): pass