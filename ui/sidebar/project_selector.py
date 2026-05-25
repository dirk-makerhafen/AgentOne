from __future__ import annotations
from typing import TYPE_CHECKING
from server.models.project import Project
from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView

if TYPE_CHECKING:
    from ui.sidebar.sidebar import SidebarView
    from ui.app import UiApp


class ProjectOption(ModelView):
    TEMPLATE_STR = '''
        <span class="project-opt-name">{{ pyview.subject.name }}</span>
        <span class="project-opt-path">{{ pyview.subject.path }}</span>
    '''
    @property
    def DOM_ELEMENT_CLASS(self):
        return f'project-opt {"active" if self.parent.parent.selected_project_id == self.subject.pk else ""}'

    @property
    def DOM_ELEMENT_EXTRAS(self):
        return f'onclick="set_project({self.subject.pk})"'


class ProjectSelector(ModelView):
    DOM_ELEMENT_CLASS = 'sidebar-project-wrap'
    TEMPLATE_STR = '''
        <div class="sidebar-top-bar">
            <button class="project-selector-btn" onclick="toggleProjectDropdown('{{pyview.uid}}')">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                <span class="project-selector-label">{{ pyview.current_label }}</span>
                <svg id="chevron_{{pyview.uid}}" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="flex-shrink:0;margin-left:auto;transition:transform .15s">
                    <polyline points="6 9 12 15 18 9"/>
                </svg>
            </button>
        </div>
        <div class="project-selector-dropdown" id="dropdown_{{pyview.uid}}">
            <div class="project-search-row">
                <input id="input_{{pyview.uid}}" class="project-search-input" type="text" placeholder="Search projects…" spellcheck="false" autocomplete="off" oninput="pyview.filter_projects(document.getElementById('input_{{pyview.uid}}').value)">
                <button class="project-search-clear" onclick="pyview.filter_projects('')" title="Clear search">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
            </div>
            <div class="project-opt" onclick="pyview.set_project(null); closeProjectDropdown('{{pyview.uid}}')">
                <span class="project-opt-name" style="color:var(--muted)">All Projects</span>
            </div>
        {{ pyview.project_list.render() }}
        <script>
            function toggleProjectDropdown(uid) {
                var dd = document.getElementById('dropdown_' + uid);
                var chevron = document.getElementById('chevron_' + uid);
                var isOpen = dd.classList.toggle('open');
                chevron.style.transform = isOpen ? 'rotate(180deg)' : 'rotate(0deg)';
            }
            function closeProjectDropdown(uid) {
                var dd = document.getElementById('dropdown_' + uid);
                var chevron = document.getElementById('chevron_' + uid);
                dd.classList.remove('open');
                chevron.style.transform = 'rotate(0deg)';
            }
            function set_project(pk){
                pyview.set_project(pk);
                var uid = '{{pyview.uid}}';
                closeProjectDropdown(uid);
            }
        </script>
    '''

    def __init__(self, subject: UiApp, parent: SidebarView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.open = False
        self.search_string = ""
        self.selected_project_id: int | None = None
        self.project_list = QuerySetView(
            subject=Project.objects.all(),
            parent=self,
            item_class=ProjectOption,
            filter_function=self._filter_function,
            dom_element_class="project-list-container",
        )

    @property
    def current_label(self) -> str:
        if self.selected_project_id is None:
            return "All Projects"
        try:
            project = Project.objects.get(pk=self.selected_project_id)
            return project.name
        except Project.DoesNotExist:
            return "All Projects"

    def toggle(self):
        self.open = not self.open

    def close(self):
        self.open = False

    def set_project(self, pk):
        self.selected_project_id = int(pk) if pk is not None else None
        self.parent.set_project(self.selected_project_id)
        self.close()

    def _filter_function(self, item: ProjectOption):
        if self.search_string:
            return self.search_string.lower() not in item.subject.name.lower()
        return False

    def filter_projects(self, searchstring: str):
        self.search_string = searchstring
        self.project_list.update()
