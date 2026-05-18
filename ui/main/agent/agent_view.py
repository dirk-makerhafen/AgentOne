from __future__ import annotations
from typing import TYPE_CHECKING

from runtime.agents.agent import Agent
from server.models.agents.agent import AgentModel
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView

if TYPE_CHECKING:
    from ui.main.main_view import MainView


class AgentView(ModelView):
    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''
        <div style="display:None">
            
            def all_versions(self):
                pass

        </div>

        <div id="mainProfiles" class="main-view">
            <div class="main-view-header">
                <div class="main-view-title" id="profileDetailTitle">{{ pyview.agent.name }} </div>
                <div class="main-view-actions">
                <button id="btnActivateProfileDetail" class="panel-head-btn" title="Activate" data-i18n-title="profile_switch_title" onclick="activateCurrentProfile()" style="display:none1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg></button>
                <button id="btnDeleteProfileDetail" class="panel-head-btn" title="Delete" data-i18n-title="profile_delete_title" onclick="deleteCurrentProfile()" style="display:none1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg></button>
                <button id="btnCancelProfileDetail" class="panel-head-btn" title="Cancel" data-i18n-title="cancel" onclick="cancelProfileForm()" style="display:none1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
                <button id="btnSaveProfileDetail" class="panel-head-btn primary" title="Save" data-i18n-title="save" onclick="saveProfileForm()" style="display:none1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg></button>
                </div>
            </div>
            <div class="main-view-body" id="profileDetailBody">
                <div class="main-view-content">
                    <div class="detail-card">
                        <div class="detail-card-title">Agent</div>

                        <div class="detail-row">
                            <div class="detail-row-label">Name</div>
                            <div class="detail-row-value">{{ pyview.agent.name }}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">Version</div>
                            <div class="detail-row-value">{{ pyview.agent.version_number }}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">Extends</div>
                            <div class="detail-row-value">
                            {% for extends_agent_version in pyview.agent.extends_agent_versions %}
                                 {{ extends_agent_version.name }}:{{ extends_agent_version.model.pk }}<br>
                            {% endfor %}
                            </div>
                        </div>
                        
                        <div class="detail-row">
                            <div class="detail-row-label">Status</div>
                            <div class="detail-row-value"><span class="detail-badge active">ACTIVE</span> <span class="detail-badge">(default)</span> </div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">Description</div>
                            <div class="detail-row-value">{{ pyview.agent.description }}</div>
                        </div>
                    </div>
                    
                    <div class="detail-card">
                        <div class="detail-card-title">Settings</div>
                        
                        <div style="display:flex; flex-direction: row; gap: 23px;">
                            <div style="width: stretch;">
                                <div class="detail-row">
                                    <div class="detail-row-label">Model</div>
                                    <div class="detail-row-value">{{pyview.agent.aimodel}}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">execution_mode</div>
                                    <div class="detail-row-value">{{pyview.agent.execution_mode}}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">tool_call_syntax</div>
                                    <div class="detail-row-value">{{pyview.agent.tool_call_syntax}}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">priority</div>
                                    <div class="detail-row-value">{{pyview.agent.priority}}</div>
                                </div>
                            </div>
                            
                            <div style="width:stretch;">
                                <div class="detail-row">
                                    <div class="detail-row-label">max_retries</div>
                                    <div class="detail-row-value">{{pyview.agent.max_retries}}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">max_turns</div>
                                    <div class="detail-row-value">{{pyview.agent.max_turns}}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">max_unattended_turns</div>
                                    <div class="detail-row-value">{{pyview.agent.max_unattended_turns}}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">max_history_messages</div>
                                    <div class="detail-row-value">{{pyview.agent.max_history_messages}}</div>
                                </div>
                            </div>
                        </div>
                    </div>



                    <div class="detail-card">
                        <div class="detail-card-title">Tools</div>
                        <div class="detail-row">
                            <div class="detail-row-label">Defined</div>
                            <div class="detail-row-value">
                                {% for definedToolVersion in pyview.agent.definedToolVersions %}
                                    {{ definedToolVersion.task_definition.name }}:{{ definedToolVersion.pk }}, 
                                {% endfor %}
                            </div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">Allowed</div>
                            <div class="detail-row-value">
                                {% for allowedTool in pyview.agent.allowedTools %}
                                    {{ allowedTool.task_definition.name }}:{{ allowedTool.pk }}, 
                                {% endfor %}
                            </div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">Tools</div>
                            <div class="detail-row-value">{{pyview.agent.toolNames}}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">disallowed tools</div>
                            <div class="detail-row-value">{{pyview.agent.disallowedToolNames}}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">allowed tools</div>
                            <div class="detail-row-value">{{pyview.agent.allowedToolNames}}</div>
                        </div>

                        
                    </div>

                    <div class="detail-card">


                    
                        <div class="detail-card-title">Skills</div>
                        <div class="detail-row">
                            <div class="detail-row-label">Defined</div>
                            <div class="detail-row-value">
                                {% for definedSkillVersion in pyview.agent.definedSkillVersions %}
                                    {{ definedSkillVersion.skill.name }}:{{ definedSkillVersion.pk }}, 
                                {% endfor %}
                           </div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">skills</div>
                            <div class="detail-row-value">{{pyview.agent.skillNames}}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">disallowed skill</div>
                            <div class="detail-row-value">{{pyview.agent.disallowedSkillNames}}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">allowed skill</div>
                            <div class="detail-row-value">{{pyview.agent.allowedSkillNames}}</div>
                        </div>
                    </div>

                    <div class="detail-card">
                        <div class="detail-card-title">Commands</div>
                        <div class="detail-row">
                            <div class="detail-row-label">Defined</div>
                            <div class="detail-row-value">
                                {% for definedCommandVersion in pyview.agent.definedCommandVersions %}
                                    {{ definedCommandVersion.task_definition.name }}:{{ definedCommandVersion.pk }}, 
                                {% endfor %}
                            </div>
                        </div>
                        
                        <div class="detail-row">
                            <div class="detail-row-label">Allowed</div>
                            <div class="detail-row-value">
                                {% for allowedCommand in pyview.agent.allowedCommands %}
                                    {{ allowedCommand.task_definition.name }}:{{ allowedCommand.pk }}, 
                                {% endfor %}
                            </div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">commands</div>
                            <div class="detail-row-value">{{pyview.agent.commandNames}}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">disallowed Commands</div>
                            <div class="detail-row-value">{{pyview.agent.disallowedCommandNames}}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">allowed Commands</div>
                            <div class="detail-row-value">{{pyview.agent.allowedCommandNames}}</div>
                        </div>
                    </div>
                    
                    <div class="detail-card">
                        <div class="detail-card-title">Tasks</div>
                        <div class="detail-row">
                            <div class="detail-row-label">Defined</div>
                            <div class="detail-row-value">
                                {% for definedTaskVersion in pyview.agent.definedTaskVersions %}
                                    {{ definedTaskVersion.task_definition.name }}:{{ definedTaskVersion.pk }}, 
                                {% endfor %}
                            </div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">Allowed</div>
                            <div class="detail-row-value">
                                {% for allowedTask in pyview.agent.allowedTasks %}
                                    {{ allowedTask.task_definition.name }}:{{ allowedTask.pk }}, 
                                {% endfor %}
                            </div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">tasks</div>
                            <div class="detail-row-value">{{pyview.agent.taskNames}}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">disallowed Tasks</div>
                            <div class="detail-row-value">{{pyview.agent.disallowedTaskNames}}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">allowed Tasks</div>
                            <div class="detail-row-value">{{pyview.agent.allowedTaskNames}}</div>
                        </div>
                    </div>

                    

                    <div class="detail-card">
                        <div class="detail-card-title">System Prompt</div>
                        <div class="detail-row">
                            <div style="min-height:0px; white-space: pre-line;height: 238px; overflow: auto; resize: auto;">
                                {{pyview.agent.system_prompt}}
                            </div>
                        </div>
                    </div>
                    <div class="detail-card">
                        <div class="detail-card-title">Task Prompt</div>
                        <div class="detail-row">
                            <div style="min-height:0px;white-space: pre-line;height: 238px; overflow: auto; resize: auto;">
                                {{pyview.agent.task_prompt}}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="main-view-empty" id="profileDetailEmpty" style="display:None">
                <svg class="main-view-empty-icon" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                <div class="main-view-empty-title" data-i18n="profiles_empty_title">Select a profile</div>
                <div class="main-view-empty-sub" data-i18n="profiles_empty_sub">Pick an agent profile from the sidebar to view and edit its settings, or create a new one.</div>
            </div>
        </div>
    '''

    def __init__(self, subject: AgentModel, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.agent = Agent(agent_model=subject)
