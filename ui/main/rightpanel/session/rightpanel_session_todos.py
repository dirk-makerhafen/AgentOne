from __future__ import annotations
from typing import TYPE_CHECKING, Any
from runtime.session.session import Session
from server.models.sessions.session import SessionModel
from ui.lib.model_view import ModelView


if TYPE_CHECKING:
    from ui.main.rightpanel.session.rightpanel_session import RightPanelSession


def _read_todo_state(session: Session | None) -> dict[str, Any]:
    """Best-effort read of the session todo state (empty state on any error).

    Items come from the ``todolist_store`` anchor history (event-sourced, no
    DB); the auto flag comes from the session settings (user-controlled).
    """
    empty: dict[str, Any] = {"items": [], "auto": False}
    if session is None:
        return empty
    try:
        anchor = session.get_task("todolist_store") or session.get_tool("todolist_store")
        raw = anchor.lastest_result() if anchor is not None else None
        auto = bool(session._get_session_setting("todo_auto_process"))
    except Exception:  # pylint: disable=broad-exception-caught
        return empty
    raw_items = []
    # NOTE: get_result() returns the raw (success, payload) pair — unwrap
    # before reading "items" (see todolist.unwrap_result).
    if isinstance(raw, (list, tuple)) and len(raw) == 2 and isinstance(raw[1], dict):
        raw = raw[1]
    if isinstance(raw, dict):
        raw_items = raw.get("items", [])
    clean = []
    if isinstance(raw_items, list):
        for it in raw_items:
            if isinstance(it, dict):
                text = str(it.get("text", "")).strip()
                if not text:
                    continue
                clean.append({
                    "id": it.get("id", 0),
                    "text": text,
                    "status": "done" if it.get("status") == "done" else "pending",
                })
    return {"items": clean, "auto": auto}


class RightPanelSessionTodos(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
    TEMPLATE_STR = '''
        <div class="panel-header">
            <span>Todo List</span>
            {% if pyview.state["auto"] %}
                <span style="font-size:10px;color:var(--success);margin-left:6px">● auto</span>
            {% else %}
                <span style="font-size:10px;color:var(--muted);margin-left:6px">○ paused</span>
            {% endif %}
        </div>
        <div style="display:flex;gap:6px;padding:8px;flex-wrap:wrap">
            {% if pyview.state["auto"] %}
                <button type="button" class="btn btn-sm" onclick="pyview.pauseAuto()" title="Stop feeding todos automatically">Pause</button>
            {% else %}
                <button type="button" class="btn btn-sm" onclick="pyview.startAuto()" title="Feed next todo after each finished task">Auto</button>
            {% endif %}
            <button type="button" class="btn btn-sm" onclick="pyview.clearTodos()" title="Drop all pending items">Clear</button>
            <button type="button" class="btn btn-sm" onclick="pyview.refreshTodos()" title="Reload list">⟳</button>
        </div>
        <div style="flex:1;overflow-y:auto;padding:0 8px 8px">
            {% if pyview.state["items"] %}
                {% for item in pyview.state["items"] %}
                <div class="task-card" style="margin-bottom:6px;display:flex;gap:8px;align-items:flex-start">
                    <span style="font-size:11px;color:var(--muted);min-width:22px">#{{ item["id"] }}</span>
                    <div style="flex:1;font-size:12px;color:var(--text);white-space:pre-wrap">{{ item["text"] }}</div>
                    {% if item["status"] == "done" %}
                        <span style="font-size:10px;color:var(--success)">done</span>
                    {% else %}
                        <span style="font-size:10px;color:var(--warning)">pending</span>
                    {% endif %}
                </div>
                {% endfor %}
            {% else %}
                <div class="detail-row">
                    <div class="detail-row-value" style="color:var(--muted);font-size:12px">No todo items. The agent can add some with the todo_append tool, or type /todo in chat.</div>
                </div>
            {% endif %}
        </div>
    '''

    def __init__(self, subject: SessionModel, parent: RightPanelSession, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.session = Session(subject)
        self.state: dict[str, Any] = _read_todo_state(self.session)
        # NOTE: no model_observer subscription here on purpose — the chat
        # view already owns the AgentTaskCall watch for this session and
        # re-subscribing would steal its callbacks.  The list refreshes on
        # tab open, manual reload, and after each button action below.

    def _set_auto(self, enabled: bool) -> None:
        try:
            self.session._set_session_setting("todo_auto_process", bool(enabled))
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def startAuto(self) -> None:
        self._set_auto(True)
        self.refreshTodos()

    def pauseAuto(self) -> None:
        self._set_auto(False)
        self.refreshTodos()

    def clearTodos(self) -> None:
        try:
            anchor = self.session.get_task("todolist_store") or self.session.get_tool("todolist_store")
            if anchor is not None:
                anchor.delay(action="clear")
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        self.refreshTodos()

    def refreshTodos(self) -> None:
        self.update()

    def update(self, *args, **kwargs):
        self.state = _read_todo_state(self.session)
        super().update(*args, **kwargs)

    def refresh(self):
        self.update()
