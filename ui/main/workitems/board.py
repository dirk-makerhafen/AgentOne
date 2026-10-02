"""Work Items board — the main view behind the sidebar's Kanban icon.

One board, not many: a work item is not a card on a user-authored board, it is
a row in one durable queue per project, so the multi-board switcher that the
Kanban CSS carries is deliberately left unrendered.  Columns are the work-item
statuses, in pipeline order.

Every visible class here already exists in ``ui/static/css/main.css`` (the
"Kanban native board" block, ~L3675-3938).  No new stylesheet rules are added
by this view.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ui.lib.model_view import ModelView
from ui.main.workitems.board_data import (
    STATUS_COLUMNS,
    TERMINAL_STATUSES,
    actions_for,
    agent_filter_options,
    apply_action,
    count_by_status,
    group_by_status,
    item_row,
    scoped_queryset,
)

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.main_view import MainView


class WorkItemsBoard(ModelView):
    DOM_ELEMENT_CLASS = "main-view kanban-pane"

    TEMPLATE_STR = '''
        <div class="main-view-header">
            <div class="main-view-title-row">
                <div class="main-view-title">Work Items</div>
                <div class="kanban-badge tenant">{{ pyview.scope_label }}</div>
            </div>
            <div class="main-view-actions">
                <button class="btn primary" onclick="pyview.reload()">Refresh</button>
            </div>
        </div>

        <div class="kanban-filter-stack">
            <select onchange="pyview.set_agent_filter(this.value)">
                <option value="">All assignees</option>
                {% for option in pyview.agent_options %}
                <option value="{{ option.id }}" {% if option.id == pyview.agent_filter %}selected{% endif %}>{{ option.label }}</option>
                {% endfor %}
            </select>
            <select onchange="pyview.set_verify_filter(this.value)">
                <option value="">Any verification</option>
                <option value="required" {% if pyview.verify_filter == 'required' %}selected{% endif %}>Needs verification</option>
                <option value="pending" {% if pyview.verify_filter == 'pending' %}selected{% endif %}>Awaiting verdict</option>
                <option value="rejected" {% if pyview.verify_filter == 'rejected' %}selected{% endif %}>Rejected</option>
                <option value="escalated" {% if pyview.verify_filter == 'escalated' %}selected{% endif %}>Escalated</option>
            </select>
            <label class="kanban-check">
                <input type="checkbox" onchange="pyview.set_show_terminal(this.checked)" {% if pyview.show_terminal %}checked{% endif %}>
                Show done &amp; cancelled
            </label>
            <label class="kanban-check">
                <input type="checkbox" onchange="pyview.set_only_actionable(this.checked)" {% if pyview.only_actionable %}checked{% endif %}>
                Only needs a human
            </label>
        </div>

        <div class="kanban-summary">
            <div class="kanban-stats-grid">
                {% for value, label in pyview.columns %}
                <span class="kanban-stat-cell">{{ label }} <strong>{{ pyview.counts[value] }}</strong></span>
                {% endfor %}
            </div>
        </div>

        {% if pyview.message %}
        <div class="kanban-summary" style="color:{% if pyview.message_ok %}var(--accent-text, var(--text)){% else %}var(--danger){% endif %}">{{ pyview.message }}</div>
        {% endif %}

        <div class="kanban-board-wrap">
            {% if pyview.empty_board %}
                <div class="kanban-empty">No work items match these filters.</div>
            {% else %}
            <div class="kanban-board">
                {% for value, label in pyview.columns %}
                {% set column_items = pyview.grouped.get(value, []) %}
                <div class="kanban-column">
                    <div class="kanban-column-head">
                        <span>{{ label }}</span>
                        <span class="kanban-count">{{ column_items|length }}</span>
                    </div>
                    <div class="kanban-column-body">
                        {% for row in column_items %}
                        <div class="kanban-card{% if row.id == pyview.selected_id %} selected{% endif %}" onclick="pyview.select({{ row.id }})">
                            <div class="kanban-card-topline">
                                <span class="kanban-card-id">#{{ row.id }}</span>
                                {% if row.priority %}
                                <span class="kanban-badge priority">P{{ row.priority }}</span>
                                {% endif %}
                                {% if row.verify_status %}
                                <span class="kanban-badge">verify: {{ row.verify_status }}</span>
                                {% elif row.requires_verification %}
                                <span class="kanban-badge">needs review</span>
                                {% endif %}
                            </div>
                            <div class="kanban-card-title">{{ row.title }}</div>
                            {% if row.body %}
                            <div class="kanban-card-body">{{ row.body }}</div>
                            {% endif %}
                            <div class="kanban-card-meta">
                                <span class="kanban-card-assignee">{{ row.assignee or 'Unassigned' }}</span>
                                <span>&middot; {{ row.dispatch_count }} dispatch(es)</span>
                                {% if row.parent_id %}
                                <span>&middot; child of #{{ row.parent_id }}</span>
                                {% endif %}
                            </div>
                        </div>
                        {% else %}
                        <div class="kanban-empty">Nothing here.</div>
                        {% endfor %}
                    </div>
                </div>
                {% endfor %}
            </div>
            {% endif %}
        </div>

        {% if pyview.selected %}
        <div class="kanban-task-preview">
            <div class="kanban-task-preview-header">
                <button class="btn secondary kanban-back-btn" onclick="pyview.select(0)">Back</button>
                <h2 class="kanban-task-preview-title">#{{ pyview.selected.id }} &mdash; {{ pyview.selected.title }}</h2>
            </div>
            {% if pyview.selected.body %}
            <div class="kanban-task-preview-body">{{ pyview.selected.body }}</div>
            {% endif %}
            <div class="kanban-card-meta">
                <span class="kanban-badge">{{ pyview.selected.status_label }}</span>
                {% if pyview.selected.assignee %}
                <span class="kanban-card-assignee">{{ pyview.selected.assignee }}</span>
                {% endif %}
                <span>priority {{ pyview.selected.priority }}</span>
                <span>{{ pyview.selected.dispatch_count }} dispatch(es)</span>
                {% if pyview.selected.verify_status %}
                <span>verify: {{ pyview.selected.verify_status }} (attempt {{ pyview.selected.verify_attempts }})</span>
                {% endif %}
            </div>
            {% if pyview.selected.last_outcome %}
            <div class="kanban-readonly">{{ pyview.selected.last_outcome }}</div>
            {% endif %}
            {% if pyview.selected.verify_reason %}
            <div class="kanban-readonly">Reviewer: {{ pyview.selected.verify_reason }}</div>
            {% endif %}

            <div class="kanban-status-actions">
                <input id="wiReason_{{ pyview.uid }}" type="text" placeholder="Reason (optional)" class="kanban-card-action" style="flex:1;min-width:160px">
                {% for action in pyview.selected_actions %}
                <button class="btn{% if action.danger %} danger{% endif %}" onclick="pyview.run_action('{{ action.key }}', document.getElementById('wiReason_{{ pyview.uid }}').value)">{{ action.label }}</button>
                {% endfor %}
            </div>
            <div class="kanban-readonly">Items are dispatched and verified by the scheduler. These buttons only record a human decision.</div>

            {% if pyview.children %}
            <div class="kanban-detail-section" style="margin-top:12px">
                <h3>Sub-items</h3>
                {% for child in pyview.children %}
                <div class="kanban-detail-row" onclick="pyview.select({{ child.id }})" style="cursor:pointer">
                    <div class="kanban-detail-row-main">#{{ child.id }} &mdash; {{ child.title }}</div>
                    <div class="kanban-detail-row-meta">{{ child.status_label }} &middot; {{ child.assignee or 'Unassigned' }}</div>
                </div>
                {% endfor %}
            </div>
            {% endif %}
        </div>
        {% endif %}
    '''

    #: Render-scoped caches, cleared by :meth:`update`. Declared at class level
    #: as well as in ``__init__`` so an instance built without ``__init__``
    #: (the tests do this to avoid a live pyHtmlGui app) still has them. The
    #: cache is keyed on :meth:`_filter_signature` rather than only on
    #: ``update()``, so a filter set directly on the view still takes effect
    #: instead of serving rows filtered by the previous state.
    _rows_cache: list[dict] | None = None
    _rows_signature: tuple | None = None
    _scope_label_cache: str | None = None

    def __init__(self, subject: "UiApp", parent: "MainView", **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view = getattr(parent, "parent", None)
        self.agent_filter = ""
        self.verify_filter = ""
        self.show_terminal = False
        self.only_actionable = False
        self.selected_id: int | None = None
        self.message = ""
        self.message_ok = True
        self._rows_cache = None
        self._rows_signature = None
        self._scope_label_cache = None
        self._watch_work_items(subject)

    def _watch_work_items(self, subject: "UiApp") -> None:
        """Re-render when anything else moves an item.

        Dispatch, agent reports and reviewer verdicts all happen in Celery
        workers, minutes after the click that queued them. Without this the
        board silently shows the pre-dispatch state until the user reloads,
        which is exactly when they are watching to see whether it ran.
        """
        app = subject if hasattr(subject, "model_observer") else None
        if app is None:
            return
        from server.models.workitems.work_item import WorkItem

        try:
            # One board per tab: drop any subscription this tab left behind
            # when it was closed and reopened, then resubscribe. unwatch()
            # is per-view across all models, and this view only watches
            # WorkItem.
            app.model_observer.unwatch(self)
            app.model_observer.watch(
                WorkItem,
                callback_name="_on_work_item_changed",
                view=self,
            )
        except Exception:
            # Live refresh is an enhancement; a board that renders statically
            # is still correct, so never let registration break the tab.
            pass

    def _on_work_item_changed(self, pk=None, action=None, filter_context=None) -> None:
        """ModelObserver callback: drop caches and re-render."""
        self._rows_cache = None
        self._rows_signature = None
        self._scope_label_cache = None
        try:
            self.update()
        except Exception:
            pass

    def update(self, *args, **kwargs):
        """Drop the render-scoped caches, then re-render.

        Every property below is read many times per pass by the template, and
        each read used to re-run the full board query. Caching for exactly one
        render keeps the template free to ask as often as it likes while still
        showing fresh data after any interaction, because every mutator here
        ends in ``update()``.
        """
        self._rows_cache = None
        self._rows_signature = None
        self._scope_label_cache = None
        return super().update(*args, **kwargs)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    @property
    def project_id(self) -> int | None:
        """The sidebar's selected project, read live on every render."""
        sidebar = getattr(self.root_view, "sidebar", None)
        if sidebar is None:
            return None
        return getattr(sidebar, "selected_project_id", None)

    @property
    def scope_label(self) -> str:
        if self._scope_label_cache is not None:
            return self._scope_label_cache
        pid = self.project_id
        if pid is None:
            self._scope_label_cache = "All projects"
            return self._scope_label_cache
        try:
            from server.models.project import Project

            label = Project.objects.filter(pk=pid).values_list("name", flat=True).first() or f"Project {pid}"
        except Exception:
            label = f"Project {pid}"
        self._scope_label_cache = label
        return label

    @property
    def columns(self) -> tuple[tuple[str, str], ...]:
        if self.show_terminal:
            return STATUS_COLUMNS
        return tuple((v, l) for v, l in STATUS_COLUMNS if v not in TERMINAL_STATUSES)

    @property
    def agent_options(self) -> list[dict]:
        return agent_filter_options(self.project_id)

    def _filter_signature(self) -> tuple:
        """Everything ``_rows`` depends on besides the database."""
        return (
            self.project_id,
            self.show_terminal,
            self.agent_filter,
            self.verify_filter,
            self.only_actionable,
        )

    def _rows(self) -> list[dict]:
        signature = self._filter_signature()
        if self._rows_cache is not None and self._rows_signature == signature:
            return self._rows_cache
        rows = [
            item_row(item)
            for item in scoped_queryset(self.project_id, include_terminal=True)
        ]
        if not self.show_terminal:
            rows = [r for r in rows if r["status"] not in TERMINAL_STATUSES]
        if self.agent_filter:
            rows = [r for r in rows if (r["assignee"] or "") == self.agent_filter]
        if self.verify_filter == "required":
            rows = [r for r in rows if r["requires_verification"]]
        elif self.verify_filter == "pending":
            rows = [r for r in rows if r["verify_status"] in ("", "pending")]
        elif self.verify_filter:
            rows = [r for r in rows if r["verify_status"] == self.verify_filter]
        if self.only_actionable:
            rows = [r for r in rows if r["status"] in ("in_review", "blocked", "ready")]
        self._rows_cache = rows
        self._rows_signature = signature
        return rows

    @property
    def grouped(self) -> dict[str, list[dict]]:
        return group_by_status(self._rows())

    @property
    def counts(self) -> dict[str, int]:
        return count_by_status(self._rows())

    @property
    def empty_board(self) -> bool:
        return not any(self.grouped.get(value) for value, _ in self.columns)

    @property
    def selected(self) -> dict | None:
        if not self.selected_id:
            return None
        for row in self._rows():
            if row["id"] == self.selected_id:
                return row
        return None

    @property
    def selected_actions(self) -> list[dict]:
        row = self.selected
        return actions_for(row) if row else []

    @property
    def children(self) -> list[dict]:
        row = self.selected
        if not row:
            return []
        try:
            from server.models.workitems.work_item import WorkItem

            kids = WorkItem.objects.filter(parent_id=row["id"]).order_by("created_at")
            return [item_row(k) for k in kids]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def select(self, item_id) -> None:
        try:
            self.selected_id = int(item_id) or None
        except (TypeError, ValueError):
            self.selected_id = None
        self.update()

    def reload(self) -> None:
        self.update()

    def set_agent_filter(self, value: str) -> None:
        self.agent_filter = (value or "").strip()
        self.update()

    def set_verify_filter(self, value: str) -> None:
        self.verify_filter = (value or "").strip()
        self.update()

    def set_show_terminal(self, checked) -> None:
        self.show_terminal = bool(checked)
        self.update()

    def set_only_actionable(self, checked) -> None:
        self.only_actionable = bool(checked)
        self.update()

    def run_action(self, action_key: str, reason: str = "") -> None:
        """Apply a human decision to the selected item via the FSM."""
        if not self.selected_id:
            self.message, self.message_ok = "Select an item first.", False
            self.update()
            return
        ok, message = apply_action(self.selected_id, action_key, reason)
        self.message, self.message_ok = message, ok
        if ok and self.selected_id and not self._still_visible(self.selected_id):
            self.selected_id = None
        self.update()

    def _still_visible(self, item_id: int) -> bool:
        return any(row["id"] == item_id for row in self._rows())
