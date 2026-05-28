from __future__ import annotations
from typing import TYPE_CHECKING
from server.models.cron import Cronjob
from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView
from ui.main.cron.create import CronCreateView
from ui.main.cron.cron import CronView
from runtime.cron.file_io import delete_cron_file

if TYPE_CHECKING:
    from ui.sidebar.sidebar import SidebarView
    from ui.app import UiApp
    from ui.app_view import UiAppView


class SidebarPanelCronjob(ModelView):
    DOM_ELEMENT_CLASS = "cron-item"
    TEMPLATE_STR = '''
        <div class="cron-header" onclick="pyview.open_cron_details()">
            <span class="cron-name" title="{{ pyview.subject.name }}">
                {% if pyview.subject.is_archived %}<span class="cron-archived-badge" title="Archived">🗄</span>{% endif %}
                {{ pyview.subject.name }}
            </span>
            <span class="cron-profile-badge">{{ pyview.subject.agent.name }}</span>
            <span class="cron-status {% if pyview.subject.is_archived %}archived{% elif pyview.subject.is_active %}active{% endif %}">
                {% if pyview.subject.is_archived %}archived{% elif pyview.subject.is_active %}active{% else %}paused{% endif %}
            </span>
            <div class="session-actions" style="position:relative;right:0px">
                <button type="button" class="session-actions-trigger" title="Cron job actions" aria-haspopup="menu" aria-label="Cron job actions" onclick="event.stopPropagation();toggleSessionMenu(event,'{{pyview.uid}}')">
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" stroke="none"><circle cx="8" cy="3" r="1.25"></circle><circle cx="8" cy="8" r="1.25"></circle><circle cx="8" cy="13" r="1.25"></circle></svg>
                </button>
                <div class="session-action-menu" id="menu_{{pyview.uid}}" style="display:none">
                    <div class="session-action-menu-items">
                        <button type="button" class="ws-opt session-action-opt" onclick="event.stopPropagation();showProjectPicker('{{pyview.uid}}')">
                            <span class="ws-opt-action">
                                <span class="ws-opt-icon">
                                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3"><path d="M2 4.5h4l1.5 1.5H14v7H2z"></path></svg>
                                </span>
                                <span class="session-action-copy">
                                    <span class="ws-opt-name">Move to project</span>
                                    <span class="session-action-meta">Assign a project to this cron job</span>
                                </span>
                            </span>
                        </button>
                        <button type="button" class="ws-opt session-action-opt" onclick="event.stopPropagation();pyview.archive_cron();closeAllSessionMenus()">
                            <span class="ws-opt-action">
                                <span class="ws-opt-icon">
                                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3"><rect x="1.5" y="2" width="13" height="3" rx="1"></rect><path d="M2.5 5v8h11V5"></path><line x1="6" y1="8.5" x2="10" y2="8.5"></line></svg>
                                </span>
                                <span class="session-action-copy">
                                    <span class="ws-opt-name">{% if pyview.subject.is_archived %}Unarchive{% else %}Archive{% endif %} cron job</span>
                                    <span class="session-action-meta">{% if pyview.subject.is_archived %}Restore this cron job{% else %}Hide this cron job{% endif %}</span>
                                </span>
                            </span>
                        </button>
                        <button type="button" class="ws-opt session-action-opt" onclick="event.stopPropagation();pyview.duplicate_cron();closeAllSessionMenus()">
                            <span class="ws-opt-action">
                                <span class="ws-opt-icon">
                                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3"><rect x="4.5" y="4.5" width="8.5" height="8.5" rx="1.5"></rect><path d="M3 11.5V3h8.5"></path></svg>
                                </span>
                                <span class="session-action-copy">
                                    <span class="ws-opt-name">Duplicate</span>
                                    <span class="session-action-meta">Create a copy of this cron job</span>
                                </span>
                            </span>
                        </button>
                        <button type="button" class="ws-opt session-action-opt danger" onclick="event.stopPropagation();pyview.delete_cron();closeAllSessionMenus()">
                            <span class="ws-opt-action">
                                <span class="ws-opt-icon">
                                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3"><path d="M3.5 4.5h9M6.5 4.5V3h3v1.5M4.5 4.5v8.5h7v-8.5"></path><line x1="7" y1="7" x2="7" y2="11"></line><line x1="9" y1="7" x2="9" y2="11"></line></svg>
                                </span>
                                <span class="session-action-copy">
                                    <span class="ws-opt-name">Delete cron job</span>
                                    <span class="session-action-meta">Permanently remove this cron job</span>
                                </span>
                            </span>
                        </button>
                    </div>
                    <div class="session-project-picker" style="display:none">
                        <div class="project-picker-item{% if not pyview.subject.parent_project_id %} active{% endif %}"
                            onclick="pyview.move_to_project(null);closeAllSessionMenus()">
                            No project
                        </div>
                        {% for project in pyview.all_projects %}
                        <div class="project-picker-item{% if project.pk == pyview.subject.parent_project_id %} active{% endif %}"
                            onclick="pyview.move_to_project({{project.pk}});closeAllSessionMenus()">
                            {{ project.name }}
                        </div>
                        {% endfor %}
                        <div class="project-picker-item project-picker-create"
                            onclick="pyview.show_project_dialog()">
                            + New project
                        </div>
                    </div>
                </div>
            </div>

        </div>

        {% if pyview._show_project_dialog %}
        <div class="app-dialog-overlay" style="display:flex;position:fixed;inset:0;z-index:1100;">
            <div class="app-dialog">
                <div class="app-dialog-header">
                    <div class="app-dialog-title">New project</div>
                    <button class="app-dialog-close" onclick="pyview.cancel_project_dialog()" type="button" aria-label="Close dialog">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                    </button>
                </div>
                <div class="app-dialog-desc">Project name:</div>
                <input class="app-dialog-input" id="projName_{{pyview.uid}}" type="text" placeholder="Project name" autocomplete="off" spellcheck="false">
                <div class="app-dialog-actions">
                    <button class="app-dialog-btn" onclick="pyview.cancel_project_dialog()">Cancel</button>
                    <button class="app-dialog-btn confirm" onclick="pyview.create_project(document.getElementById('projName_{{pyview.uid}}').value)">Create</button>
                </div>
            </div>
        </div>
        {% endif %}
    '''

    def __init__(self, subject: Cronjob, parent: QuerySetView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.parent.root_view
        self._show_project_dialog = False

    def open_cron_details(self):
        self.root_view.main_panel.create_and_open_tab(CronView, self.subject)

    @property
    def all_projects(self):
        from server.models.project import Project
        return Project.objects.only("pk", "name").all()

    def move_to_project(self, project_id: int | None) -> None:
        self.subject.parent_project_id = project_id if project_id else None
        self.subject.save(update_fields=["parent_project_id"])
        self.parent.parent.refresh_list()

    def archive_cron(self) -> None:
        self.subject.is_archived = not self.subject.is_archived
        self.subject.save(update_fields=["is_archived"])
        self.parent.parent.refresh_list()

    def duplicate_cron(self) -> None:
        self.root_view.main_panel.create_and_open_tab(CronCreateView, self.subject)

    def delete_cron(self) -> None:
        delete_cron_file(self.subject.name)
        self.subject.delete()
        self.parent.parent.refresh_list()

    def show_project_dialog(self) -> None:
        self._show_project_dialog = True
        self.update()

    def cancel_project_dialog(self) -> None:
        self._show_project_dialog = False
        self.update()

    def create_project(self, name: str) -> None:
        from server.models.project import Project
        project = Project.objects.create(name=name)
        self.subject.parent_project = project
        self.subject.save(update_fields=["parent_project_id"])
        self._show_project_dialog = False
        self.parent.parent.refresh_list()


class SidebarPanelCronjobs(ModelView):
    DOM_ELEMENT_CLASS = "panel-view active"
    TEMPLATE_STR = '''
        <div class="panel-head">
            <span data-i18n="scheduled_jobs">Scheduled jobs</span>
            <div class="panel-head-actions">
                <button class="panel-head-btn" onclick="pyview.refreshList()" title="Refresh job list">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                </button>
                <button class="panel-head-btn" onclick="pyview.openCronCreate()" title="New job" data-i18n-title="new_job">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                </button>
            </div>
        </div>
        <div class="cron-filter-bar">
            <span class="project-chip{% if not pyview._show_archived %} active{% endif %}" onclick="pyview.show_active()">Active</span>
            <span class="project-chip{% if pyview._show_archived %} active{% endif %}" onclick="pyview.show_archived()">Archived</span>
        </div>
        {{ pyview.cronjob_list.render() }}
        <script>
            function toggleSessionMenu(event, uid) {
                event.stopPropagation();
                var menu = document.getElementById('menu_' + uid);
                var isOpen = menu.style.display === 'block';
                closeAllSessionMenus();
                if (!isOpen) {
                    var btn = event.currentTarget;
                    var rect = btn.getBoundingClientRect();
                    menu.style.left = Math.max(8, rect.left - 220 + rect.width) + 'px';
                    menu.style.top = (rect.bottom + 4) + 'px';
                    menu.style.display = 'block';
                    var items = menu.querySelector('.session-action-menu-items');
                    var picker = menu.querySelector('.session-project-picker');
                    if (items) items.style.display = '';
                    if (picker) picker.style.display = 'none';
                    var cronItem = btn.closest('.cron-item');
                    if (cronItem) cronItem.classList.add('menu-open');
                }
            }
            function closeAllSessionMenus() {
                var menus = document.querySelectorAll('.session-action-menu');
                for (var i = 0; i < menus.length; i++) {
                    menus[i].style.display = 'none';
                }
                var items = document.querySelectorAll('.cron-item.menu-open');
                for (var i = 0; i < items.length; i++) {
                    items[i].classList.remove('menu-open');
                }
            }
            function showProjectPicker(uid) {
                var menu = document.getElementById('menu_' + uid);
                menu.querySelector('.session-action-menu-items').style.display = 'none';
                menu.querySelector('.session-project-picker').style.display = 'block';
            }
            if (!window._cronMenuListenerAdded) {
                document.addEventListener('click', function(e) {
                    if (!e.target.closest('.session-action-menu') && !e.target.closest('.session-actions-trigger')) {
                        closeAllSessionMenus();
                    }
                });
                window._cronMenuListenerAdded = true;
            }
        </script>
    '''

    def __init__(self, subject: UiApp, parent: SidebarView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.root_view
        self._show_archived = False
        self.cronjob_list = QuerySetView(
            subject=self._base_query(),
            parent=self,
            item_class=SidebarPanelCronjob,
            dom_element_class="cron-list",
        )

    def _base_query(self):
        qs = self.subject.cronjobs.root()
        if self._show_archived:
            return qs.filter(is_archived=True)
        return qs.filter(is_archived=False)

    def refresh_list(self):
        self.cronjob_list.query = self._base_query()
        self.cronjob_list._recreate()
        self.update()

    def set_project_filter(self, project_id: int | None) -> None:
        if project_id is None:
            base = self.subject.cronjobs.root()
        else:
            base = Cronjob.objects.filter(parent_project_id=project_id)
        if self._show_archived:
            base = base.filter(is_archived=True)
        else:
            base = base.filter(is_archived=False)
        self.cronjob_list.query = base
        self.cronjob_list._recreate()
        self.update()

    def show_active(self):
        if self._show_archived:
            self._show_archived = False
            self.refresh_list()

    def show_archived(self):
        if not self._show_archived:
            self._show_archived = True
            self.refresh_list()

    def openCronCreate(self):
        self.root_view.main_panel.create_and_open_tab(CronCreateView, self.subject)

    def refreshList(self):
        self.cronjob_list.query = self._base_query()
        self.cronjob_list._recreate()
        self.update()
