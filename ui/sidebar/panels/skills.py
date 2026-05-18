from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.agents.agent import Agent
from runtime.agents.skill import Skill
from server.models.agents.agent import AgentModel
from server.models.skills.skill import SkillModel
from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView
from ui.main.skills.skill_view import SkillView

if TYPE_CHECKING:
    from ui.sidebar.sidebar import SidebarView
    from ui.app import UiApp
    from ui.app_view import UiAppView


'''
<div class="skills-category"><div class="skills-cat-header" data-cat="apple"><span class="cat-chevron" style="display:inline-flex;transition:transform .15s;transform:rotate(90deg)"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><polyline points="9 18 15 12 9 6"></polyline></svg></span> apple <span style="opacity:.5">(4)</span></div><div class="skill-item"><span class="skill-name">apple-notes</span><span class="skill-desc">Manage Apple Notes via memo CLI: create, search, edit.</span></div><div class="skill-item"><span class="skill-name">apple-reminders</span><span class="skill-desc">Apple Reminders via remindctl: add, list, complete.</span></div><div class="skill-item"><span class="skill-name">findmy</span><span class="skill-desc">Track Apple devices/AirTags via FindMy.app on macOS.</span></div><div class="skill-item"><span class="skill-name">imessage</span><span class="skill-desc">Send and receive iMessages/SMS via the imsg CLI on macOS.</span></div></div>

'''
class SidebarPanelSkill(ModelView):

    DOM_ELEMENT_CLASS = "skill-item"    
    TEMPLATE_STR = '''
    <div  onclick="pyview.open_skill_details()">
        <span class="skill-name">{{ pyview.subject.name }}</span>
        <span class="skill-desc">{{ pyview.subject.description }}</span>
        <span class="skill-desc">{{ pyview.subject.latest_skill_version.path }}</span>
    </div>
    '''    
    def __init__(self, subject: SkillModel, parent: QuerySetView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.parent.root_view
    
    
    def open_skill_details(self):
        self.root_view.main_panel.create_and_open_tab(SkillView, self.subject)
      
class SidebarPanelSkills(ModelView):
    DOM_ELEMENT_CLASS = "panel-view"
    TEMPLATE_STR = '''
        <!-- Skills panel -->
        <div class="panel-head">
            <span data-i18n="tab_skills">Skills</span>
            <div class="panel-head-actions">
            <button class="panel-head-btn" onclick="pyview.reloadFromDisk()" title="refresh from disk" data-i18n-title="skills_refresh_title" aria-label="Refresh from disk">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
            </button>
                <button class="panel-head-btn" onclick="openSkillCreate()" title="New skill" data-i18n-title="new_skill" aria-label="New skill">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                </button>
            </div>
        </div>
        <div class="skills-search sidebar-search">
            <svg class="sidebar-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
            <input id="input_{{pyview.uid}}" placeholder="Search skills..." data-i18n-placeholder="search_skills" oninput="pyview.filter_skills(document.getElementById('input_{{pyview.uid}}').value)">
        </div>
        <div class="skills-list">
            {{ pyview.skill_list.render() }}
        </div>
    '''
    def __init__(self, subject:UiApp, parent: SidebarView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.root_view
        self.search_string = ""
        self.skill_list = QuerySetView(
            subject = subject.skills.root(),
            parent = self,
            item_class = SidebarPanelSkill,
            dom_element_class = "skills-category",
            filter_function=self._filter_function
        )

    def reloadFromDisk(self):
        pass

    def _filter_function(self, item:SidebarPanelSkill):
        return self.search_string not in item.subject.name

    def filter_skills(self, searchstring):
        self.search_string = searchstring
        self.skill_list.update()
        