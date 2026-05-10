from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView

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
        <span class="skill-name">{{ pyview.subject.name }}</span>
        <span class="skill-desc">{{ pyview.subject.description }}</span>
    '''

class SidebarPanelSkills(ModelView):
    DOM_ELEMENT_CLASS = "panel-view"
    TEMPLATE_STR = '''
        <!-- Skills panel -->
        <div class="panel-head">
            <span data-i18n="tab_skills">Skills</span>
            <div class="panel-head-actions">
                <button class="panel-head-btn" onclick="openSkillCreate()" title="New skill" data-i18n-title="new_skill" aria-label="New skill">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                </button>
            </div>
        </div>
        <div class="skills-search sidebar-search"><svg class="sidebar-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/>
            <path d="M21 21l-4.35-4.35"/></svg><input id="skillsSearch" placeholder="Search skills..." data-i18n-placeholder="search_skills" oninput="filterSkills()">
        </div>
        <div class="skills-list">
            {{ pyview.skill_list.render() }}
        </div>
    '''
    def __init__(self, subject:UiApp, parent: SidebarView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.uid = "panelSkills"
        self.root_view: UiAppView = parent.root_view
        self.skill_list = QuerySetView(
            subject = subject.skills.root(),
            parent = self,
            item_class = SidebarPanelSkill,
            dom_element_class = "skills-category",
        )
