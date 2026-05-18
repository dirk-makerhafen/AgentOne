from __future__ import annotations
import json
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_run import AgentTaskRun
from ui.lib.queryset_view import QuerySetView
from ui.lib.model_view import ModelView


_TASK_ICONS = {
    'CHAIN': 'fa-link',
    'GROUP': 'fa-layer-group',
    'TOOL':  'fa-wrench',
    'CHAT':  'fa-comments',
}


class TaskCallView(ModelView):
    """
    Renders a single AgentTaskCall as a compact collapsible tree row.

    Collapsed:   ▶  icon · agent v#  ·  task name  Call#N  BADGE  time
    Expanded:    args (raw/resolved toggle) + TaskRunView for each run

    Only ROOT calls (parent=None or not in any run's subtask list) should
    appear in the top-level chat timeline. Child calls appear recursively
    inside TaskRunView via taskrun_subtask_references / taskrun_result_references.
    """
    DOM_ELEMENT_CLASS = "TaskCallView"

    TEMPLATE_STR = """
        <div class="tc-row status-{{ pyview.subject.status_detail|lower|replace('_','-') }}
                    {{ 'tc-row--sub' if pyview.is_subtask }}"
             onclick="pyview.toggle()">

            <div class="tc-gutter">
                <span class="tc-caret">{{ '▼' if not pyview.is_collapsed else '▶' }}</span>
                <i class="fa {{ pyview.task_icon }} tc-icon"></i>
            </div>

            <div class="tc-body">
                <span class="tc-agent">{{ pyview.subject.session_version.agent.name }}</span>
                <span class="tc-ver">v{{ pyview.subject.session_version.agent_version.version_number }}</span>
                <span class="tc-sep">·</span>
                <span class="tc-name">{{ pyview.subject.agent_task_definition.name }}</span>
                <span class="tc-id">Call#{{ pyview.subject.id }}</span>
                <span class="tc-badge tc-s-{{ pyview.subject.status_detail|lower|replace('_','-') }}">
                    {{ pyview.subject.status_detail }}
                </span>
            </div>

            <div class="tc-meta">
                {% if pyview.subject.taskcall_arg_references.exists() %}
                    <span class="tc-deps">{{ pyview.subject.taskcall_arg_references.count() }}d</span>
                {% endif %}
                {% if pyview.subject.status == "NEW" or pyview.subject.status_detail == "WAITING_RETRY" %}
                    <button class="tc-start" onclick="event.stopPropagation(); pyview.subject.apply_async()">
                        start
                    </button>
                {% endif %}
                <span class="tc-time">{{ pyview.subject.created_at.strftime('%H:%M:%S') }}</span>
            </div>
        </div>

        {% if not pyview.is_collapsed %}
        <div class="tc-expand">
            {% if pyview.subject.carguments_json %}
                <div class="tc-args-bar">
                    <button class="tc-arg-tab {{ 'active' if pyview.args_mode == 'resolved' }}"
                            onclick="event.stopPropagation(); pyview.set_args('resolved')">resolved</button>
                    <button class="tc-arg-tab {{ 'active' if pyview.args_mode == 'raw' }}"
                            onclick="event.stopPropagation(); pyview.set_args('raw')">raw</button>
                </div>
                <pre class="tc-pre">{{ pyview.call_args() }}</pre>
            {% endif %}
            {{ pyview.run_views.render() }}
        </div>
        {% endif %}
    """

    CSS_STR = """
        /* ── TaskCallView ─────────────────────────────────────────────────── */
        .TaskCallView {
            font-size: 0.84em;
            border-left: 2px solid var(--border-light);
            margin-bottom: 1px;
            border-radius: 0 var(--r-sm) var(--r-sm) 0;
            overflow: hidden;
        }

        /* status accent on left border */
        .tc-row.status-ended-success          { border-left-color: var(--success); }
        .tc-row.status-ended-failure-exception,
        .tc-row.status-ended-failure-logic    { border-left-color: var(--danger); }
        .tc-row.status-active-running         { border-left-color: var(--accent); }
        .tc-row.status-waiting-ratelimit,
        .tc-row.status-halted-approval        { border-left-color: var(--warning); }

        .tc-row {
            display: flex;
            align-items: center;
            gap: 0;
            cursor: pointer;
            padding: 3px 6px 3px 0;
            transition: background 0.1s;
            user-select: none;
        }
        .tc-row:hover       { background: var(--bg-subtle); }
        .tc-row--sub        { border-left: none; }

        .tc-gutter {
            width: 34px;
            flex-shrink: 0;
            display: flex;
            align-items: center;
            gap: 4px;
            padding-left: 6px;
        }
        .tc-caret { font-size: 0.65em; color: var(--text-faint); }
        .tc-icon  { font-size: 0.82em; color: var(--text-muted); }

        .tc-body {
            display: flex;
            align-items: center;
            gap: 4px;
            flex-grow: 1;
            min-width: 0;
            overflow: hidden;
        }
        .tc-agent { font-weight: 500; white-space: nowrap; }
        .tc-ver   { color: var(--text-faint); font-size: 0.88em; white-space: nowrap; }
        .tc-sep   { color: var(--text-faint); }
        .tc-name  { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex-shrink: 1; min-width: 0; }
        .tc-id    { font-size: 0.78em; color: var(--text-faint); white-space: nowrap; flex-shrink: 0; }

        .tc-badge {
            display: inline-block;
            padding: 0 6px;
            border-radius: 8px;
            font-size: 0.72em;
            font-weight: 500;
            white-space: nowrap;
            flex-shrink: 0;
            background: var(--badge-neutral-bg);
            color: var(--badge-neutral-fg);
        }
        .tc-s-ended-success               { background: var(--badge-success-bg); color: var(--badge-success-fg); }
        .tc-s-ended-failure-exception,
        .tc-s-ended-failure-logic         { background: var(--badge-error-bg);   color: var(--badge-error-fg); }
        .tc-s-active-running              { background: var(--badge-active-bg);  color: var(--badge-active-fg); }
        .tc-s-waiting-ratelimit,
        .tc-s-halted-approval             { background: var(--badge-warning-bg); color: var(--badge-warning-fg); }
        .tc-s-halted-input                { background: var(--badge-halted-bg);  color: var(--badge-halted-fg); }

        .tc-meta {
            display: flex;
            align-items: center;
            gap: 5px;
            flex-shrink: 0;
            padding-left: 8px;
        }
        .tc-deps  { font-size: 0.72em; color: var(--text-faint); }
        .tc-time  { font-size: 0.72em; color: var(--text-faint); white-space: nowrap; }
        .tc-start {
            padding: 1px 5px;
            font-size: 0.72em;
            border: 1px solid var(--warning);
            border-radius: var(--r-sm);
            background: var(--badge-warning-bg);
            color: var(--badge-warning-fg);
            cursor: pointer;
        }

        /* Expand panel */
        .tc-expand {
            padding: 2px 6px 4px 34px;
            background: var(--bg-subtle);
        }

        /* Args */
        .tc-args-bar { display: flex; gap: 0; margin-bottom: 0; }
        .tc-arg-tab {
            padding: 1px 8px;
            font-size: 0.72em;
            border: 1px solid var(--border);
            border-bottom: none;
            border-radius: var(--r-sm) var(--r-sm) 0 0;
            background: var(--bg-raised);
            color: var(--text-muted);
            cursor: pointer;
            margin-right: 2px;
        }
        .tc-arg-tab.active { background: #1e1e2e; color: #cdd6f4; border-color: #1e1e2e; }

        .tc-pre {
            font-family: var(--font-mono);
            font-size: 0.76em;
            background: #1e1e2e;
            color: #cdd6f4;
            padding: 6px 10px;
            border-radius: 0 var(--r-sm) var(--r-sm) var(--r-sm);
            max-height: 140px;
            overflow-y: auto;
            margin: 0 0 4px;
            white-space: pre-wrap;
            word-break: break-all;
        }

        /* ── TaskRunView ───────────────────────────────────────────────────── */
        .TaskRunView { margin: 1px 0; }

        .tr-row {
            display: flex;
            align-items: center;
            gap: 4px;
            padding: 2px 4px;
            font-size: 0.8em;
            cursor: pointer;
            color: var(--text-muted);
            border-radius: var(--r-sm);
            transition: background 0.1s;
            user-select: none;
        }
        .tr-row:hover { background: var(--bg-raised); }

        .tr-caret { font-size: 0.62em; color: var(--text-faint); flex-shrink: 0; }
        .tr-icon  { font-size: 0.78em; color: var(--text-faint); flex-shrink: 0; }
        .tr-label { flex-grow: 1; }
        .tr-badge {
            padding: 0 5px;
            border-radius: 6px;
            font-size: 0.78em;
            background: var(--badge-neutral-bg);
            color: var(--badge-neutral-fg);
        }
        .tr-badge--success { background: var(--badge-success-bg); color: var(--badge-success-fg); }
        .tr-badge--error   { background: var(--badge-error-bg);   color: var(--badge-error-fg); }
        .tr-badge--active  { background: var(--badge-active-bg);  color: var(--badge-active-fg); }

        .tr-meta { display: flex; gap: 5px; font-size: 0.78em; color: var(--text-faint); flex-shrink: 0; }

        .tr-expand { padding: 2px 4px 4px 20px; }

        /* Dep pills */
        .dep-list { display: flex; flex-wrap: wrap; gap: 3px; margin: 2px 0; }
        .dep-item {
            font-family: var(--font-mono);
            font-size: 0.75em;
            background: var(--bg-raised);
            border: 1px solid var(--border);
            border-radius: var(--r-sm);
            padding: 0 4px;
            color: var(--text-muted);
        }

        /* Subtask children block */
        .tc-children {
            padding-left: 10px;
            border-left: 1px solid var(--border-light);
            margin: 2px 0;
        }

        .section-label {
            font-size: 0.68em;
            text-transform: uppercase;
            letter-spacing: .05em;
            color: var(--text-faint);
            padding: 2px 0;
        }
    """

    @property
    def DOM_ELEMENT_EXTRAS(self):
        return f'style="order: {int(self.subject.created_at.timestamp())}"'

    @property
    def task_icon(self) -> str:
        return _TASK_ICONS.get(self.subject.agent_task_definition.task_type, 'fa-terminal')

    def __init__(self, subject: AgentTaskCall, parent, is_subtask=False, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_subtask   = is_subtask
        self.is_collapsed = True
        self.args_mode    = 'resolved'
        self.run_views    = QuerySetView(subject=subject.related_agent_task_runs.order_by('created_at'), parent=self, item_class=TaskRunView)

    def toggle(self):
        self.is_collapsed = not self.is_collapsed
        self.update()

    def set_args(self, mode: str):
        self.args_mode = mode
        self.update()

    def call_args(self) -> str:
        if self.args_mode == 'raw':
            try:
                return json.dumps(self.subject.carguments_json, indent=2)
            except Exception:
                return str(self.subject.carguments_json)
        return self.subject._resolve_call_arguments(timeout=0, allow_partial_results=True)
    

class TaskRunView(ModelView):
    """
    Compact run row shown inside an expanded TaskCallView.
    Expands to show deps, result, and subtask calls.
    """
    DOM_ELEMENT_CLASS = "TaskRunView"

    TEMPLATE_STR = """
        <div class="tr-row" onclick="pyview.toggle()">
            <span class="tr-caret">{{ '▼' if not pyview.is_collapsed else '▶' }}</span>
            <i class="fa fa-play tr-icon"></i>
            <span class="tr-label">Run#{{ pyview.subject.id }}</span>
            <span class="tr-badge tr-badge--{{ pyview.run_class }}">{{ pyview.subject.status }}</span>
            <div class="tr-meta">
                {% if pyview.subject.taskrun_arg_references.exists() %}
                    <span>{{ pyview.subject.taskrun_arg_references.count() }}d</span>
                {% endif %}
                <span>{{ pyview.subject.created_at.strftime('%H:%M:%S') }}</span>
            </div>
        </div>

        {% if not pyview.is_collapsed %}
            <div class="tr-expand">
                {% if pyview.subject.taskrun_arg_references.exists() %}
                    <div class="section-label">Dependencies</div>
                    <div class="dep-list">
                        {% for dep in pyview.subject.taskrun_arg_references.all() %}
                            <span class="dep-item">{{ dep.__class__.__name__ }}#{{ dep.pk }}</span>
                        {% endfor %}
                    </div>
                {% endif %}

                {% if pyview.result_str %}
                    <div class="section-label">Result</div>
                    <pre class="tc-pre">{{ pyview.result_str }}</pre>
                {% endif %}

                {% if pyview.has_children %}
                    <div class="tc-children">
                        {{ pyview.subtask_views.render() }}
                        {{ pyview.result_ref_views.render() }}
                    </div>
                {% endif %}
            </div>
        {% endif %}
    """

    @property
    def run_class(self) -> str:
        s = self.subject.status.lower()
        if 'success' in s: return 'success'
        if 'fail' in s or 'error' in s: return 'error'
        if 'active' in s or 'running' in s: return 'active'
        return ''

    @property
    def result_str(self) -> str:
        rj = self.subject.result_json
        if not rj:
            return ''
        try:
            return json.dumps(rj, indent=2)[:2000]
        except Exception:
            return str(rj)[:2000]

    @property
    def has_children(self) -> bool:
        return self.subject.taskrun_subtask_references.exists() or self.subject.taskrun_result_references.exists()

    def __init__(self, subject: AgentTaskRun, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_collapsed = True
        self.subtask_views = QuerySetView(
            subject=subject.taskrun_subtask_references.order_by('created_at'),
            parent=self,
            item_class=TaskCallView,
            is_subtask=True,
        )
        self.result_ref_views = QuerySetView(
            subject=subject.taskrun_result_references.order_by('created_at'),
            parent=self,
            item_class=TaskCallView,
            is_subtask=True,
        )

    def toggle(self):
        self.is_collapsed = not self.is_collapsed
        self.update()


class TaskCallPayloadView(ModelView):
    """Minimal compatibility shim — kept for panels/tasks.py."""
    DOM_ELEMENT_CLASS = "TaskCallPayloadView"
    TEMPLATE_STR = """{{ pyview.run_views.render() }}"""

    def __init__(self, subject: AgentTaskCall, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.run_views = QuerySetView(
            subject=subject.related_agent_task_runs.order_by('created_at'),
            parent=self,
            item_class=TaskRunView,
        )