"""Create a DataCollection (stream or ordered set)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.models.collections import DataCollection
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.main_view import MainView


class CollectionCreateView(ModelView):
    """Create a new DataCollection (stream or set)."""

    DOM_ELEMENT_CLASS = "main-view"

    TEMPLATE_STR = '''
        <div class="main-view-header">
            <div class="main-view-title">New data flow</div>
            <div class="main-view-actions">
                <button class="panel-head-btn" title="Cancel" onclick="pyview.cancel()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
                <button class="panel-head-btn primary" title="Save" onclick="pyview.save()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
                </button>
            </div>
        </div>
        <div class="main-view-body">
            <div class="main-view-content">
                <div class="detail-card">
                    <div class="detail-card-title">Data collection</div>

                    <div class="detail-form-row">
                        <label>Name</label>
                        <input type="text" value="{{ pyview._form_data.name }}" onchange="pyview.setField('name', this.value)" placeholder="my-stream-or-set">
                    </div>

                    <div class="detail-form-row">
                        <label>Description</label>
                        <input type="text" value="{{ pyview._form_data.description }}" onchange="pyview.setField('description', this.value)" placeholder="Optional description">
                    </div>

                    <div class="detail-form-row">
                        <label>Type</label>
                        <select onchange="pyview.setField('collection_type', this.value)">
                            <option value="stream"{% if pyview._form_data.collection_type == 'stream' %} selected{% endif %}>Stream (append-only)</option>
                            <option value="set"{% if pyview._form_data.collection_type == 'set' %} selected{% endif %}>Ordered Set (mutable)</option>
                        </select>
                    </div>

                    {% if pyview._form_error %}
                    <div style="color:red;padding:8px;background:var(--danger-bg);border-radius:4px;margin-top:8px">
                        {{ pyview._form_error }}
                    </div>
                    {% endif %}
                </div>
            </div>
        </div>
    '''

    def __init__(self, subject: UiApp, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._form_data: dict[str, str] = {
            "name": "",
            "description": "",
            "collection_type": "stream",
        }
        self._form_error = ""

    def setField(self, field: str, value: str) -> None:
        self._form_data[field] = value
        self._form_error = ""
        self.update()

    def save(self) -> None:
        name = self._form_data.get("name", "").strip()
        if not name:
            self._form_error = "Name is required."
            self.update()
            return
        collection_type = self._form_data.get("collection_type", "stream")
        description = self._form_data.get("description", "").strip()
        try:
            DataCollection.objects.create(
                name=name,
                description=description,
                collection_type=collection_type,
            )
        except Exception as e:
            self._form_error = f"Failed to create: {e}"
            self.update()
            return
        self._close_tab()

    def cancel(self) -> None:
        self._close_tab()

    def _find_main_view(self):
        parent = self.parent
        while parent and not hasattr(parent, "create_and_open_tab"):
            parent = parent.parent
        return parent

    def _close_tab(self) -> None:
        parent = self._find_main_view()
        if parent and hasattr(parent, "close_tab"):
            parent.close_tab(self)
