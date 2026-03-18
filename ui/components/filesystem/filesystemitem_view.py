from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
from tools.builtin_filesystem.models.fs_log_entry import FsLogEntry

class FilesystemItemView(PyHtmlView):
    TEMPLATE_STR = """
    <div id="fs-item-{{ pyview.subject.id }}" class="fs-item {% if not pyview.subject.is_loaded %}fs-item-unloaded{% endif %}" data-path="{{ pyview.subject.path }}" data-timestamp="{{ pyview.subject.created_at }}" data-is-loaded="{{ pyview.subject.is_loaded }}" data-instance-pk="{{ pyview.instancePk }}" data-load-mode="{{ pyview.subject.load_mode }}">
        <i class="fa {% if pyview.subject.is_dir %}fa-folder-o{% else %}{% if pyview.subject.is_summary %}fa-file{% else %}fa-file-o{% endif %}{% endif %} item-icon"></i>
        
        <span class="fs-path item-text" title="{{ pyview.subject.path }}">{{ pyview.subject.path }}</span>
        <span class="fs-token-count">{{ pyview.subject.tokens }}</span>
        {% if pyview.subject.deleted %}<span class="item-deleted" title="File no longer exists"><i class="fa fa-exclamation-circle"></i></span>{% endif %}
        <div class="item-actions">
            <i class="fa fa-thumb-tack fs-pin-btn {% if pyview.subject.is_pinned %}pinned{% endif %}" 
               data-fslogentry-pk="{{ pyview.subject.id }}"
               data-is-pinned="{{ pyview.subject.is_pinned }}"
               onclick="pyview.fs_pin()"
               title="{% if pyview.subject.is_pinned %}Unpin this item{% else %}Pin this item{% endif %}"></i>
            {% if not pyview.subject.is_dir %}
                {% if pyview.subject.is_loaded %}
                    {% if pyview.subject.is_summary %}
                        <i class="fa fa-expand fs-toggle-load-mode-btn" data-path="{{ pyview.subject.path }}" data-id="{{ pyview.subject.id }}" data-load-mode="summary" onclick="pyview.fs_toggle_load_mode()" title="Switch to Full Load Mode"></i>
                    {% else %}
                        <i class="fa fa-compress fs-toggle-load-mode-btn" data-path="{{ pyview.subject.path }}"data-id="{{ pyview.subject.id }}"  data-load-mode="full" onclick="pyview.fs_toggle_load_mode()" title="Switch to Summary Load Mode"></i>
                    {% endif %}
                {% endif %}
            {% endif %}
            <i class="fa fa-sign-out fs-unload-btn" data-path="{{ pyview.subject.path }}" data-path="{{ pyview.subject.id }}" onclick="pyview.fs_unload()" title="Unload this item" style="{% if not pyview.subject.is_loaded %}display: none;{% endif %}"></i>
            <i class="fa fa-sign-in fs-load-btn" data-path="{{ pyview.subject.path }}"    data-path="{{ pyview.subject.id }}" onclick="pyview.fs_load_item()" title="Load this item" style="{% if pyview.subject.is_loaded %}display: none;{% endif %}"></i>
        </div>
    </div>
    """
    def __init__(self, subject:FsLogEntry, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.s = subject

    def fs_pin(self):
        self.subject.is_pinned = not self.subject.is_pinned
        self.subject.save()
        self.update()
    def fs_toggle_load_mode(self):
        # Toggle between 'full' and 'summary'
        self.subject.load_mode = 'summary' if self.subject.load_mode == 'full' else 'full'
        self.subject.save()
        self.update()
    def fs_unload(self):
        # This should mark the item as unloaded in the backend
        self.subject.is_loaded = False
        self.subject.save()
        self.update()
    def fs_load_item(self):
        # This should mark the item as loaded in the backend
        self.subject.is_loaded = True
        self.subject.save()
        self.update()

