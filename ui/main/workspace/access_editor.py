"""Editor for the WorkspaceModel ``access`` JSON field.

Renders the filesystem access policy (``read``/``write`` sections, each with
a default of allow/ask/deny plus allow/ask/deny glob lists) as selects and
textareas.  Values are buffered in the view (no re-render on keystroke, so
focus is never lost); the parent reads :attr:`access_data` on save.

Used by the workspace create page and the current-workspace card edit mode.
"""
from __future__ import annotations
from ui.lib.model_view import ModelView


SECTIONS = ("read", "write")
KEYS = ("allow", "ask", "deny")
DEFAULTS = ("allow", "ask", "deny")
FALLBACK_DEFAULT = "ask"


def normalize_access(raw: dict | None) -> dict:
    """Return a complete access dict (both sections, default + 3 lists)."""
    raw = raw if isinstance(raw, dict) else {}
    data: dict = {}
    for section in SECTIONS:
        sec = raw.get(section) if isinstance(raw.get(section), dict) else {}
        default = sec.get("default")
        if default not in DEFAULTS:
            default = FALLBACK_DEFAULT
        lists = {}
        for key in KEYS:
            vals = sec.get(key) or []
            if isinstance(vals, str):
                vals = [vals]
            lists[key] = [str(v) for v in vals if str(v).strip()]
        data[section] = {"default": default, **lists}
    return data


class AccessEditor(ModelView):
    DOM_ELEMENT_CLASS = "ws-access"
    TEMPLATE_STR = '''
        {% for section in pyview.sections %}
        <div class="ws-access-section">
            <div class="ws-access-head">
                <span class="ws-access-title">{{ section|title }}</span>
                <label class="ws-access-default">default
                    <select onchange="pyview.setAccess('{{ section }}', 'default', this.value)">
                        {% for opt in pyview.defaults %}
                        <option value="{{ opt }}"{% if pyview.data[section]["default"] == opt %} selected{% endif %}>{{ opt }}</option>
                        {% endfor %}
                    </select>
                </label>
            </div>
            {% for key in pyview.keys %}
            <label class="ws-access-label">{{ key }} <span class="ws-access-hint">one glob per line</span></label>
            <textarea class="ws-access-list" rows="2" onchange="pyview.setAccessList('{{ section }}', '{{ key }}', this.value)" placeholder="e.g. src/**">{{ pyview.list_text(section, key) }}</textarea>
            {% endfor %}
        </div>
        {% endfor %}
    '''

    def __init__(self, subject, parent, access: dict | None = None, **kwargs):
        super().__init__(subject, parent, **kwargs)
        if access is None:
            access = getattr(subject, "access", None)
        self._data = normalize_access(access)

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    @property
    def sections(self) -> tuple:
        return SECTIONS

    @property
    def keys(self) -> tuple:
        return KEYS

    @property
    def defaults(self) -> tuple:
        return DEFAULTS

    @property
    def data(self) -> dict:
        return self._data

    def list_text(self, section: str, key: str) -> str:
        try:
            return "\n".join(self._data[section][key])
        except (KeyError, TypeError):
            return ""

    @property
    def access_data(self) -> dict:
        """Buffered policy in the model's JSON shape."""
        return {s: {"default": self._data[s]["default"],
                    **{k: list(self._data[s][k]) for k in KEYS}}
                for s in SECTIONS}

    # ------------------------------------------------------------------
    # Actions (buffered — no update(), textareas keep focus)
    # ------------------------------------------------------------------

    def setAccess(self, section: str, key: str, value: str) -> None:
        if section not in SECTIONS:
            return
        if key == "default":
            self._data[section]["default"] = (
                value if value in DEFAULTS else FALLBACK_DEFAULT
            )
        elif key in KEYS:
            self._set_list(section, key, value)

    def setAccessList(self, section: str, key: str, text: str) -> None:
        if section in SECTIONS and key in KEYS:
            self._set_list(section, key, text)

    def _set_list(self, section: str, key: str, text: str) -> None:
        self._data[section][key] = [
            line.strip() for line in (text or "").splitlines() if line.strip()
        ]
