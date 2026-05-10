from __future__ import annotations
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from server.models.agents.agent_instance_version import InstanceVersionModel
from tools.builtin_filesystem.models.fs_log_entry import FsLogEntry
from ui.lib.model_view import ModelView


class FilesystemItemView(ModelView):
    """Renders a single loaded filesystem entry with pin/load/unload controls."""
    DOM_ELEMENT_CLASS = "FilesystemItemView fs-item"

    TEMPLATE_STR = """
        <div class="fs-item-inner {% if not pyview.subject.is_loaded %}fs-item-unloaded{% endif %}"
             data-path="{{ pyview.subject.path }}"
             data-load-mode="{{ pyview.subject.load_mode }}">

            <i class="fa {% if pyview.subject.is_dir %}fa-folder-o{% elif pyview.subject.is_summary %}fa-file{% else %}fa-file-o{% endif %} item-icon"></i>
            <span class="fs-path" title="{{ pyview.subject.path }}">{{ pyview.subject.path }}</span>
            <span class="fs-token-count">{{ pyview.subject.tokens }}</span>

            {% if pyview.subject.deleted %}
                <span class="item-deleted" title="File no longer exists">
                    <i class="fa fa-exclamation-circle"></i>
                </span>
            {% endif %}

            <div class="item-actions">
                <i class="fa fa-thumb-tack fs-pin-btn {{ 'pinned' if pyview.subject.is_pinned else '' }}"
                   onclick="pyview.toggle_pin()"
                   title="{{ 'Unpin' if pyview.subject.is_pinned else 'Pin' }}"></i>

                {% if not pyview.subject.is_dir and pyview.subject.is_loaded %}
                    {% if pyview.subject.is_summary %}
                        <i class="fa fa-expand fs-mode-btn" onclick="pyview.toggle_load_mode()"
                           title="Switch to full load"></i>
                    {% else %}
                        <i class="fa fa-compress fs-mode-btn" onclick="pyview.toggle_load_mode()"
                           title="Switch to summary"></i>
                    {% endif %}
                {% endif %}

                {% if pyview.subject.is_loaded %}
                    <i class="fa fa-sign-out fs-unload-btn" onclick="pyview.unload()" title="Unload"></i>
                {% else %}
                    <i class="fa fa-sign-in fs-load-btn" onclick="pyview.load()" title="Load"></i>
                {% endif %}
            </div>
        </div>
    """
    CSS_STR = '''
        .item-deleted > i {
            color:#ff0000a3;
        }
    '''

    def __init__(self, subject: FsLogEntry, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)

    def toggle_pin(self):
        self.subject.is_pinned = not self.subject.is_pinned
        self.subject.save()
        self.update()

    def toggle_load_mode(self):
        self.subject.load_mode = 'summary' if self.subject.load_mode == 'full' else 'full'
        self.subject.save()
        self.update()

    def unload(self):
        self.subject.is_loaded = False
        self.subject.save()
        self.update()

    def load(self):
        self.subject.is_loaded = True
        self.subject.save()
        self.update()


class FilesystemHeaderView(ModelView):
    """Working directory display/edit + permission toggles."""
    DOM_ELEMENT_CLASS = "FilesystemHeaderView fs-header"

    TEMPLATE_STR = """
        <div class="fs-header-inner">
            {% if not pyview.is_edit_mode %}
                <span class="editable-path {{ 'placeholder' if not pyview.subject.workingdir }}"
                      onclick="pyview.show_edit()"
                      title="{{ pyview.subject.workingdir or 'Click to set working directory' }}">
                    {{ pyview.subject.workingdir or '[Not Set]' }}
                </span>
            {% else %}
                <input type="text"
                       id="workingdir-input_{{ pyview.subject.id }}"
                       value="{{ pyview.subject.workingdir or '' }}"
                       onkeydown="pyview.handle_keydown(event)" />
                <i class="fa fa-check" onclick="pyview.save()"></i>
                <i class="fa fa-times" onclick="pyview.cancel()"></i>
            {% endif %}

            <span class="fs-token-count">{{ pyview.subject.total_fs_tokens }}</span>

            <div class="fs-header-controls">
                <i class="fa fa-eye fs-view-toggle"
                   title="Toggle unloaded items"
                   onclick="pyview.toggle_view()"></i>
                <i class="fa fa-pencil fs-permission-toggle {{ 'unlocked' if pyview.subject.workingdir_write_allowed else 'locked' }}"
                   title="{{ 'Write: ON' if pyview.subject.workingdir_write_allowed else 'Write: OFF' }}"
                   onclick="pyview.toggle_write_permission()"></i>
            </div>
        </div>
    """

    def __init__(self, subject: InstanceVersionModel, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_edit_mode = False

    def show_edit(self):
        self.is_edit_mode = True
        self.update()

    def handle_keydown(self, event):
        if event.key == 'Enter':
            self.save()
        elif event.key == 'Escape':
            self.cancel()

    def save(self):
        new_path = self.eval_javascript(
            script=f"return document.getElementById('workingdir-input_{self.subject.id}').value;"
        )
        if self.subject.workingdir != new_path:
            self.subject.workingdir = new_path
            self.subject.save()
        self.is_edit_mode = False
        self.update()

    def cancel(self):
        self.is_edit_mode = False
        self.update()

    def toggle_view(self):
        self.subject.show_unloaded_items = not self.subject.show_unloaded_items
        self.subject.save()
        self.update()

    def toggle_write_permission(self):
        self.subject.workingdir_write_allowed = not self.subject.workingdir_write_allowed
        self.subject.save()
        self.update()


class FilesystemPanelView(ModelView):
    """
    Right-panel filesystem browser.
    Subject is the AgentInstanceVersion's filesystem runtime object
    (exposes get_loaded_items(), access_rules, fs_load task, etc.).
    """
    DOM_ELEMENT_CLASS = "FilesystemPanelView"

    TEMPLATE_STR = """
        <div class="panel-section">
            {{ pyview.header_view.render() }}
        </div>

        <div class="fs-list-header">
            <span class="sort-header" onclick="pyview.sort('path')">
                Name <i class="fa fa-sort"></i>
            </span>
            <span class="sort-header" onclick="pyview.sort('size')">
                Size <i class="fa fa-sort"></i>
            </span>
            <span class="sort-header sort-header-actions">Actions</span>
        </div>

        <div class="fs-list">
            {% for item in pyview.subject.get_loaded_items() %}
                {{ pyview.get_item_view(item).render() }}
            {% endfor %}
        </div>

        <div class="fs-input-container">
            <textarea id="fs-path-input_{{ pyview.subject.id }}"
                      rows="3"
                      placeholder="Enter one path per line..."></textarea>
            <button class="button"
                    onclick="pyview.load_paths(document.getElementById('fs-path-input_{{ pyview.subject.id }}').value)">
                Load
            </button>
        </div>

        <div class="fs-rules-container">
            <i class="fa fa-question-circle"
               title="Access Rules: !path = deny, >path = write ok, <path = read only"></i>
            <textarea class="fs-rules-textarea"
                      placeholder="Access Rules (!/denied, >/writeok, </readonly)"
                      onblur="pyview.save_access_rules(this.value)">{{ pyview.subject.access_rules }}</textarea>
        </div>
    """
    CSS_STR = '''
        .sidebar-fs-header-new .fs-token-count {
            color: #6c757d;
            white-space: nowrap;
            margin-left: 2px;
            min-width: fit-content;
        }

        /* Filesystem Header Controls */
        .sidebar-fs-header-controls {
            display: flex;
            align-items: center;
            justify-content: flex-end;
            padding: 2px;
            background-color: #f1f3f5;
            border-top: 1px solid #dee2e6;
        }

        /* Filesystem List Header (Flexible Layout) */
        .sidebar-fs-list-header {
            display: flex;
            align-items: center;
            padding: 2px 8px; /* Reduced vertical padding to be more compact */
            border-bottom: 1px solid #dee2e6;
            background-color: #f8f9fa;
            font-weight: bold;
            font-size: 0.9em;
            min-height: 25px; /* Ensure a minimum height for the header */
            gap: 10px; /* Consistent spacing between header items */
        }

        .sidebar-fs-list-header .sort-header-item {
            cursor: pointer;
            /* Removed white-space: nowrap to allow wrapping if extremely narrow */
            display: flex;
            align-items: center;
            padding: 0; /* Remove internal padding, rely on gap for spacing */
        }

        .sidebar-fs-list-header .sort-header-item i {
            margin-left: 5px;
            font-size: 0.8em;
        }

        /* Adjust widths for alignment with list items using flexbox */
        .sidebar-fs-list-header .sort-header-item[data-sort-column="path"] {
            flex-grow: 1;
            flex-basis: 0; /* Allows it to take up remaining space */
            margin-left: 5px; /* Account for the initial icon in list items */
        }

        .sidebar-fs-list-header .sort-header-item[data-sort-column="size"] {
            flex-shrink: 0; /* Prevent shrinking below content size */
            text-align: right;
            justify-content: flex-end;
            padding-right: 5px; /* Matches fs-token-count right padding */
            min-width: 10px; /* Smallest sensible minimum width */
        }

        .sidebar-fs-list-header .sort-header-item[data-sort-column="actions"] {
            flex-shrink: 0; /* Prevent shrinking below content size */
            text-align: right;
            justify-content: flex-end;
            padding-right: 0; /* No right padding, buttons have their own margin */
            min-width: 10px; /* Smallest sensible minimum width */
        }

        .fs-permission-toggle {
            font-size: 1.2em;
            cursor: pointer;
            margin-right: 12px;
        }
        .fs-permission-toggle.locked { color: darkgray; }
        .fs-permission-toggle.locked:hover { color: gray; }
        .fs-permission-toggle.unlocked { color: black; }
        .fs-permission-toggle.unlocked:hover { color: rgb(57, 57, 57); }
        .fs-permission-select {
            font-size: 0.85em;
            padding: 2px 4px;
            border: 1px solid #ced4da;
            border-radius: 3px;
            background-color: #fff;
        }
        .sidebar-fs-rules-container, .sidebar-fs-input-container {
            padding: 0px 8px 6px 8px;
            background-color: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
            position: relative;
        }
        .fs-rules-textarea {
            min-height: 15%;
            width: 100%;
            box-sizing: border-box;
            font-family: monospace;
            font-size: 0.85em;
            border: 1px solid #ced4da;
            border-radius: 3px;
            resize: vertical;
            margin: 0;
            padding: 4px;
        }
        .fs-rules-help {
            position: absolute;
            top: 6px;
            right: 14px;
            color: #aaa;
            cursor: help;
            font-size: 1.1em;
        }
        .fs-rules-help:hover { color: #666; }

        /* --- Flexbox Layout for Scrolling --- */
        .sidebar-section {
            display: flex;
            flex-direction: column;
            height: 100%; /* Make the section fill its parent tab content area */
            max-height: 100%;
        }

        .sidebar-fs-list {
            flex-grow: 1; /* Allow the list to expand and fill available space */
            overflow-y: auto; /* Enable vertical scrolling ONLY for the list */
            min-height: 50px; /* Prevent it from collapsing completely */
            padding: 0 4px;
        }

        /* Ensure headers and footers do not grow or shrink */
        #sidebar-filesystem-header-container,
        .sidebar-fs-list-header,
        .sidebar-fs-input-container,
        .sidebar-fs-rules-container {
            flex-shrink: 0;
        }


        /* By default, hide unloaded filesystem items */
        .sidebar-fs-list .fs-item-unloaded {
            display: none;
        }

        /* When the container has the special class, show the unloaded items */
        .sidebar-fs-list.show-unloaded .fs-item-unloaded {
            display: flex;
        }

        .fs-view-toggle.active {
            color: #337ab7; /* Bootstrap's primary blue color */
        }


        /* Filesystem Sidebar Header */
        .sidebar-fs-header-new {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 6px 8px;
            border-bottom: 1px solid #dee2e6;
            background-color: #f8f9fa;
            font-size: 0.9em;
        }
        .sidebar-fs-header-new .fs-header-item {
            display: flex;
            align-items: center;
            overflow: hidden;
        }
        .sidebar-fs-header-new .editable-path {
            font-weight: bold;
            cursor: pointer;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            width: -webkit-fill-available;
        }
        .sidebar-fs-header-new .fa-pencil {
            margin-left: 2px;
            margin-right: 2px;
            cursor: pointer;
            color: #6c757d;
        }
        #sidebar-workingdir-edit input {
            border: 1px solid #007bff;
            border-radius: 3px;
            padding: 1px 4px;
            font-size: 1em;
            width: -webkit-fill-available;
        }
        #sidebar-workingdir-edit i {
            margin-left: 6px;
            cursor: pointer;
        }
        #sidebar-workingdir-edit .fa-check { color: #28a745; }
        #sidebar-workingdir-edit .fa-times { color: #dc3545; }

        .sidebar-fs-input-container {
            width: 100%;
            display: flex;
        }

        .sidebar-fs-input-container > textarea{
            width: 100%;
            display: flex;
        }
        /* Hide/Show Unloaded Items */
        .sidebar-fs-list .fs-item-unloaded {
            max-height: fit-content;
            display: None;
            margin-top: 0;
            margin-bottom: 0;
            overflow: hidden;
        }
        .sidebar-fs-list.show-all-fs-items .fs-item-unloaded {
            max-height: 50px;
            display: flex;
            pointer-events: auto;
        }
        .fs-item-unloaded .fs-token-count, .fs-item-unloaded .fs-path, .fs-item-unloaded .item-icon {
            color: #888;
        }
        .fs-item-unloaded .fs-token-count {
            text-decoration: line-through;
        }
'''

    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._item_views: dict = {}
        self.header_view = FilesystemHeaderView(subject, self)

    def get_item_view(self, item) -> FilesystemItemView:
        if item.id not in self._item_views:
            self._item_views[item.id] = FilesystemItemView(subject=item, parent=self)
        return self._item_views[item.id]

    def sort(self, column):
        # TODO: implement sort on subject
        self.update()

    def load_paths(self, paths_str: str):
        for path in [p.strip() for p in paths_str.split('\n') if p.strip()]:
            self.subject.fs_load.delay(path=path)
        self.update()

    def save_access_rules(self, value: str):
        # TODO: persist access rules on subject
        print(f"save_access_rules: {value}")