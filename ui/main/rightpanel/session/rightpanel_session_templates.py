from __future__ import annotations
from typing import TYPE_CHECKING, Any

from runtime.session.session import Session
from server.models.sessions.session import SessionModel
from ui.lib.model_view import ModelView, orm_subscribe, orm_unsubscribe_view

if TYPE_CHECKING:
    from ui.main.rightpanel.session.rightpanel_session import RightPanelSession


class RightPanelSessionTemplates(ModelView):
    # pylint: disable=too-many-instance-attributes
    """Session-scoped query-template picker: list, fill variables, run.

    Templates are database rows scoped to this session (immutable versions
    + a per-session link).  Selecting a template builds a
    variable form from its frontmatter schema; Preview renders locally via
    ``runtime.query_templates`` and Run dispatches ``call_llm_direct``
    (ephemeral session, same as the ``template_execute`` tool).  The run
    result arrives through the existing ``AgentTaskCall.session:<sid>``
    observable — the panel subscribes on dispatch and unsubscribes when the
    call ends, mirroring ``ui/main/chat/messages/messages.py``.
    """

    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
    TEMPLATE_STR = '''
        <div class="panel-header">
            <span>Templates</span>
            <button class="panel-head-btn" title="Refresh" onclick="pyview.refreshTemplates()">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
            </button>
        </div>
        <div style="flex:1;overflow-y:auto;padding:8px">
            {% if not pyview.templates %}
            <div class="detail-row">
                <div class="detail-row-value" style="color:var(--muted);font-size:12px">No templates yet. Ask the agent to save one with the <code>template_save</code> tool (name, body, and variable specs).</div>
            </div>
            {% else %}
            {% for t in pyview.templates %}
            <div class="task-card" style="margin-bottom:6px;padding:6px 8px;cursor:pointer{% if pyview._selected == t.name %};border-color:var(--accent){% endif %}" onclick="pyview.selectTemplate('{{ t.name }}')">
                <div style="font-size:12px;font-weight:600">{{ t.name }}</div>
                {% if t.description %}<div style="font-size:11px;color:var(--muted)">{{ t.description }}</div>{% endif %}
            </div>
            {% endfor %}
            {% endif %}

            {% if pyview.selected_template %}
            {% set sel = pyview.selected_template %}
            <div class="detail-card" style="margin-top:8px">
                <div class="detail-card-title">{{ sel.name }}</div>
                {% if sel.description %}<div style="font-size:11px;color:var(--muted);margin-bottom:6px">{{ sel.description }}</div>{% endif %}
                {% if sel.variables %}
                {% for var in sel.variables %}
                <div class="detail-form-row">
                    <label>{{ var.name }}{% if var.required %} *{% endif %} <span style="font-weight:normal;color:var(--muted)">({{ var.type }}{% if var.has_default %}, default: {{ var.default }}{% endif %})</span></label>
                    <input type="text" value="{{ pyview._values.get(var.name, '') }}" placeholder="{% if var.has_default %}{{ var.default }}{% endif %}" autocomplete="off" onchange="pyview.setVar('{{ var.name }}', this.value)">
                    {% if var.description %}<div class="detail-form-hint">{{ var.description }}</div>{% endif %}
                </div>
                {% endfor %}
                {% else %}
                <div style="font-size:11px;color:var(--muted)">No variables — runs as-is.</div>
                {% endif %}
                <div style="display:flex;gap:6px;margin-top:8px">
                    <button class="panel-head-btn" onclick="pyview.previewTemplate()">Preview</button>
                    <button class="panel-head-btn primary" onclick="pyview.runTemplate()">Run</button>
                    <button class="panel-head-btn" title="Delete template" onclick="pyview.deleteTemplate('{{ sel.name }}')">Delete</button>
                </div>
                <div class="detail-form-error" style="display:{% if pyview._error %}block{% else %}none{% endif %}">
                    {{ pyview._error }}
                </div>
            </div>
            {% endif %}

            {% if pyview._preview %}
            <div class="detail-card" style="margin-top:8px">
                <div class="detail-card-title">Preview</div>
                <pre style="font-size:11px;white-space:pre-wrap">{{ pyview._preview }}</pre>
            </div>
            {% endif %}

            {% if pyview._run_status %}
            <div class="detail-card" style="margin-top:8px">
                <div class="detail-card-title">Run — {{ pyview._run_status }}</div>
                {% if pyview._run_meta %}<div style="font-size:11px;color:var(--muted);margin-bottom:4px">{{ pyview._run_meta }}</div>{% endif %}
                {% if pyview._result %}<pre style="font-size:11px;white-space:pre-wrap">{{ pyview._result }}</pre>{% endif %}
                <div style="display:flex;gap:6px;margin-top:6px">
                    {% if pyview._run_status == "running" %}<button class="panel-head-btn" onclick="pyview.checkRun()">Check result</button>{% endif %}
                    <button class="panel-head-btn" onclick="pyview.clearRun()">Clear</button>
                </div>
            </div>
            {% endif %}
        </div>
    '''

    def __init__(self, subject: SessionModel, parent: RightPanelSession, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.session = Session(subject)
        self._selected: str | None = None
        self._values: dict[str, str] = {}
        self._preview: str = ""
        self._error: str = ""
        self._run_call_pk: int | None = None
        self._run_status: str = ""
        self._run_meta: str = ""
        self._result: str = ""
        self._run_key: str | None = None

    # ------------------------------------------------------------------
    # Template data
    # ------------------------------------------------------------------

    @property
    def templates(self) -> list[dict]:
        from runtime.query_templates import list_templates

        try:
            return list_templates(self.session.model.pk)
        except Exception:
            return []

    @property
    def selected_template(self) -> Any | None:
        if not self._selected:
            return None
        from runtime.query_templates import TemplateError, get_template

        try:
            return get_template(self.session.model.pk, self._selected)
        except TemplateError:
            return None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Selection + form
    # ------------------------------------------------------------------

    def selectTemplate(self, name: str) -> None:
        from runtime.query_templates import get_template

        try:
            template = get_template(self.session.model.pk, name)
        except Exception as exc:
            self._error = str(exc)
            self.update()
            return
        self._selected = template.name
        self._values = {
            var.name: ("" if not var.has_default else str(var.default))
            for var in template.variables
        }
        self._preview = ""
        self._error = ""
        self.update()

    def setVar(self, name: str, value: str) -> None:
        self._values[name] = value
        self.update()

    def refreshTemplates(self) -> None:
        if self._selected and self.selected_template is None:
            self._selected = None
            self._values = {}
            self._preview = ""
        self.update()

    def deleteTemplate(self, name: str) -> None:
        from runtime.query_templates import TemplateError, delete_template

        try:
            delete_template(self.session.model.pk, name)
        except TemplateError as exc:
            self._error = str(exc)
            self.update()
            return
        except Exception as exc:
            self._error = str(exc)
            self.update()
            return
        if self._selected == name:
            self._selected = None
            self._values = {}
            self._preview = ""
        self._error = ""
        self.update()

    # ------------------------------------------------------------------
    # Preview + run
    # ------------------------------------------------------------------

    def previewTemplate(self) -> None:
        if not self._selected:
            return
        from runtime.query_templates import TemplateError, render_template_by_name

        try:
            _, rendered = render_template_by_name(
                self.session.model.pk, self._selected, dict(self._values)
            )
        except TemplateError as exc:
            self._error = str(exc)
            self._preview = ""
            self.update()
            return
        except Exception as exc:
            self._error = str(exc)
            self._preview = ""
            self.update()
            return
        self._preview = rendered
        self._error = ""
        self.update()

    def runTemplate(self, model: str | None = None) -> None:
        if not self._selected:
            return
        from runtime.query_templates import TemplateError, render_template_by_name

        try:
            _, rendered = render_template_by_name(
                self.session.model.pk, self._selected, dict(self._values)
            )
        except TemplateError as exc:
            self._error = str(exc)
            self.update()
            return
        except Exception as exc:
            self._error = str(exc)
            self.update()
            return
        task = self.session.get_task("call_llm_direct")
        if task is None:
            self._error = "Task 'call_llm_direct' is not available for this session."
            self.update()
            return
        try:
            call = task.delay(
                messages=[{"role": "user", "content": rendered}],
                model_name=model,
            )
        except Exception as exc:
            self._error = f"Failed to dispatch run: {exc}"
            self.update()
            return
        self._unsubscribe_run()
        self._run_call_pk = getattr(call, "pk", None)
        self._run_status = "running"
        self._run_meta = f"template {self._selected} · call {self._run_call_pk}"
        self._result = ""
        self._error = ""
        self._preview = rendered
        self._run_key = f"AgentTaskCall.session:{self.session.model.pk}"
        try:
            orm_subscribe(self, self._run_key, self._on_orm_event)
        except Exception:
            pass
        self.update()

    def checkRun(self) -> None:
        self._refresh_run()
        self.update()

    def clearRun(self) -> None:
        self._unsubscribe_run()
        self._run_call_pk = None
        self._run_status = ""
        self._run_meta = ""
        self._result = ""
        self.update()

    # ------------------------------------------------------------------
    # Async result handling
    # ------------------------------------------------------------------

    def _on_orm_event(self, key=None, model=None, pk=None, action=None, data=None) -> None:  # pylint: disable=unused-argument
        """Redis observable callback: refresh our run when its call updates."""
        try:
            if model == "AgentTaskCall" and pk == self._run_call_pk:
                self._refresh_run()
                self.update()
        except Exception:
            pass

    def _refresh_run(self) -> None:
        if self._run_call_pk is None:
            return
        from server.models.tasks.agent_task_call import AgentTaskCall

        try:
            call = AgentTaskCall.objects.get(pk=self._run_call_pk)
        except Exception:
            self._run_status = "unknown (call not found)"
            return
        try:
            result = call.get_result(timeout=0)
        except TimeoutError:
            try:
                detail = call.status_detail
            except Exception:
                detail = ""
            self._run_status = f"running ({detail})" if detail else "running"
            return
        except Exception as exc:
            self._run_status = "ended"
            self._run_meta = f"template {self._selected} · error reading result"
            self._result = str(exc)
            self._unsubscribe_run()
            return
        if result is None:
            self._run_status = "ended"
            self._run_meta = f"template {self._selected} · no result recorded"
            self._result = "(the run ended without recording a result)"
            self._unsubscribe_run()
            return
        if not isinstance(result, dict):
            result = {"content": str(result)}
        self._result = result.get("content") or result.get("error") or ""
        status = result.get("status", "")
        model_name = result.get("model", "")
        self._run_meta = f"template {self._selected} · {status} · {model_name}".strip()
        self._run_status = "done" if status == "SUCCESS" else f"ended ({status})"
        self._unsubscribe_run()

    def _unsubscribe_run(self) -> None:
        if self._run_key is not None:
            try:
                orm_unsubscribe_view(self, self._run_key)
            except Exception:
                pass
            self._run_key = None
