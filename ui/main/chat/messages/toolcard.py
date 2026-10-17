from __future__ import annotations
from typing import TYPE_CHECKING, Any

from server.models.enums.task_enums import TaskCallStatusDetail
from ui.lib.model_view import ModelView
if TYPE_CHECKING:
    from server.models.tasks.agent_task_call import AgentTaskCall
    from ui.main.chat.messages.assistant_message import AssistantMessageView

def _fmt_duration(seconds: float | None) -> str:
    """Format a duration in seconds as a compact human string."""
    if seconds is None:
        return ""
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return ""
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}m {int(seconds % 60):02d}s"
    hours = minutes // 60
    return f"{hours}h {minutes % 60:02d}m"


def _fmt_clock(value) -> str:
    """Format a datetime as HH:MM:SS (empty string when missing)."""
    if value is None:
        return ""
    try:
        return value.strftime("%H:%M:%S")
    except Exception:
        return ""


def _status_class_for(call) -> str:
    """CSS modifier for a sub-call status pill (never raises)."""
    try:
        detail = (getattr(call, "status_detail", "") or "").upper()
        if "SUCCESS" in detail:
            return "success"
        if "FAILURE" in detail or "CANCELLED" in detail or "STOPPED" in detail:
            return "failure"
        status = (getattr(call, "status", "") or "").lower()
        if status in ("success", "failure", "active", "waiting"):
            return status
        if status in ("halted", "ended"):
            return "waiting"
        return status or "waiting"
    except Exception:
        return "waiting"


def _subcall_duration(call) -> str:
    """Compact duration for a sub-call row (never raises)."""
    try:
        start = getattr(call, "created_at", None)
        end = getattr(call, "ended_at", None) or getattr(call, "updated_at", None)
        if start is None or end is None:
            return ""
        return _fmt_duration((end - start).total_seconds())
    except Exception:
        return ""


class ToolCard(ModelView):
    DOM_ELEMENT_CLASS = "msg-row tool-card-row"
    TEMPLATE_STR = '''
        <div class="tool-card {% if pyview.subject.status_detail == 'HALTED_APPROVAL' %}open approval-pending{% endif %}  {% if pyview.is_open %}open{% endif %}">
        <div class="tool-card-header" onclick="pyview.toggle()">

            <span class="card-icon">
                <svg width="14px" height="14px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            </span>
            <span class="card-title">{{pyview.tool_name}}</span>
            {% if pyview.subject.status_detail == "HALTED_APPROVAL" %}
                <span class="tool-card-approval-hint">approval needed</span>
            {% else %}
                <span class="card-sub">{{pyview.status_label}}</span>
            {% endif %}
            {% if pyview.executing_subcall_count %}
                <span class="card-meta" title="{{pyview.executing_subcall_count}} sub-task call(s) currently executing{% if pyview.subcalls_truncated %} (counts capped — tree is bigger){% endif %}">↳ {{pyview.executing_subcall_count}} running</span>
            {% elif pyview.waiting_subcall_count %}
                <span class="card-meta" title="{{pyview.waiting_subcall_count}}{% if pyview.subcalls_truncated %}+{% endif %} sub-task call(s) queued, none executing{% if pyview.subcalls_truncated %} (counts capped — tree is bigger){% endif %}">↳ {{pyview.waiting_subcall_count}}{% if pyview.subcalls_truncated %}+{% endif %} queued</span>
            {% elif pyview.finished_subcall_count %}
                <span class="card-meta" title="{{pyview.finished_subcall_count}}{% if pyview.subcalls_truncated %}+{% endif %} finished sub-task call(s)">↳ {{pyview.finished_subcall_count}}{% if pyview.subcalls_truncated %}+{% endif %} subtasks</span>
            {% endif %}
            <span class="card-meta" title="Last update: {{pyview.subject.updated_at}}">{{pyview.updated_str}}</span>
            {% if pyview.show_duration %}
                <span class="card-meta" title="Time the tool took so far / in total">{{pyview.duration_str}}</span>
            {% endif %}
            <span class="card-status {{ pyview.status_class }}">{{ pyview.subject.status }}</span>

            <span class="card-toggle">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><polyline points="9 18 15 12 9 6"></polyline></svg>
            </span>
        </div>
        {% if pyview.has_subcalls %}
            <div class="tool-subcalls" style="padding:2px 12px 4px 26px;font-size:11px;line-height:1.7">
                {% for node in pyview.subcall_nodes %}
                    <div class="tool-subcall" style="margin-left:{{ node.indent }}px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="#{{ node.pk }} · {{ node.status_detail }} · updated {{ node.updated }}">
                        <span style="color:var(--muted)">↳</span>
                        <span style="font-weight:600;font-family:'SF Mono',ui-monospace,monospace">{{ node.name }}</span>
                        <span style="color:var(--muted)">:{{ node.pk }}</span>
                        <span class="card-status {{ node.status_class }}" style="margin-left:6px">{{ node.status }}</span>
                        {% if node.executing %}
                            <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--accent);margin-left:6px;vertical-align:1px" title="currently executing"></span>
                        {% endif %}
                        {% if node.duration %}
                            <span style="color:var(--muted);margin-left:6px">{{ node.duration }}</span>
                        {% endif %}
                    </div>
                {% endfor %}
                {% if pyview.waiting_subcall_count and not pyview.show_queued %}
                    <button class="tool-card-more" onclick="pyview.toggle_queued()" title="Show queued (not yet executing) sub-task calls">show {{ pyview.waiting_subcall_count }}{% if pyview.subcalls_truncated %}+{% endif %} queued</button>
                {% elif pyview.show_queued and pyview.waiting_subcall_count %}
                    <button class="tool-card-more" onclick="pyview.toggle_queued()" title="Hide queued sub-task calls">hide queued</button>
                {% endif %}
                {% if pyview.finished_subcall_count and not pyview.show_finished %}
                    <button class="tool-card-more" onclick="pyview.toggle_subcalls()" title="Load finished sub-task calls (costs one full subtree query)">show {{ pyview.finished_subcall_count }}{% if pyview.subcalls_truncated %}+{% endif %} finished</button>
                {% elif pyview.show_finished and pyview.finished_subcall_count %}
                    <button class="tool-card-more" onclick="pyview.toggle_subcalls()" title="Hide finished sub-task calls">hide finished</button>
                {% endif %}
            </div>
        {% endif %}
        {% if pyview.is_open %}
            <div class="tool-card-detail">
                <div class="tool-card-args">
                    {% for tool_arg_name, tool_arg_value in pyview.subject._resolve_call_arguments().items() %}
                        <div>
                            <span class="tool-arg-key">{{tool_arg_name}}</span> 
                            <span class="tool-arg-val">{{tool_arg_value}}</span>
                        </div>
                    {% endfor %}
                </div>
                <div class="tool-card-result"><pre>{{pyview.subject.get_result(allow_partial_results=True)}}</pre></div>
                {% if pyview.subject.status_detail == "HALTED_APPROVAL" %}
                    <div class="tool-card-approval">
                        <input id="tool_feedback_{{ pyview.subject.pk }}" type="text" placeholder="Reason for denying (optional)" autocomplete="off" spellcheck="false">
                        <button class="tool-card-approve" onclick="pyview.approve_call()">Approve</button>
                        <button class="tool-card-deny" onclick="pyview.deny_call(document.getElementById('tool_feedback_{{ pyview.subject.pk }}').value)">Deny</button>
                    </div>
                {% endif %}
            </div>
        {% endif %}
        </div>
    '''
    @property
    def tool_name(self) -> str:
        """Display name of the invoked tool (never raises in templates)."""
        try:
            tdv = getattr(self.subject, "task_definition_version", None)
            td = getattr(tdv, "task_definition", None) if tdv is not None else None
            if td is not None and getattr(td, "name", None):
                return td.name
            td = getattr(self.subject, "task_definition", None)
            if td is not None and getattr(td, "name", None):
                return td.name
        except Exception:
            pass
        return f"call #{getattr(self.subject, 'pk', '?')}"

    @property
    def status_label(self) -> str:
        """Human-readable status detail label (e.g. 'Running')."""
        try:
            detail = getattr(self.subject, "status_detail", "") or ""
            labels = dict(TaskCallStatusDetail.choices)
            return labels.get(detail, detail or getattr(self.subject, "status", ""))
        except Exception:
            return getattr(self.subject, "status", "")

    @property
    def status_class(self) -> str:
        """CSS modifier for the status pill (success/failure/active/waiting)."""
        try:
            detail = (getattr(self.subject, "status_detail", "") or "").upper()
            if "SUCCESS" in detail:
                return "success"
            if "FAILURE" in detail or "CANCELLED" in detail or "STOPPED" in detail:
                return "failure"
            status = (getattr(self.subject, "status", "") or "").lower()
            if status in ("success", "failure", "active", "waiting"):
                return status
            if status == "halted":
                return "waiting"
            if status == "ended":
                return "waiting"
            return status or "waiting"
        except Exception:
            return "waiting"

    @property
    def updated_str(self) -> str:
        try:
            return _fmt_clock(self.subject.updated_at)
        except Exception:
            return ""

    @property
    def show_duration(self) -> bool:
        """Show the elapsed/total time once the tool started or finished."""
        try:
            if getattr(self.subject, "ended_at", None) is not None:
                return True
            return (getattr(self.subject, "status", "") or "") in ("ACTIVE", "HALTED", "ENDED")
        except Exception:
            return False

    @property
    def duration_str(self) -> str:
        try:
            start = getattr(self.subject, "created_at", None)
            end = getattr(self.subject, "ended_at", None) or getattr(self.subject, "updated_at", None)
            if start is None or end is None:
                return ""
            return _fmt_duration((end - start).total_seconds())
        except Exception:
            return ""

    def __init__(self, subject:AgentTaskCall, parent: AssistantMessageView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_open = False
        # Only currently-executing sub-calls show by default (perf: the
        # chat would otherwise walk every subtree on every render, and
        # hundreds of queued rows bury the running call). Queued and
        # finished calls hide behind their expander buttons.
        self.show_queued = False
        self.show_finished = False
        self._active_tree_cache: list[dict] | None = None
        self._full_tree_cache: list[dict] | None = None
        self._subcall_counts_cache: dict | None = None
        self._executing_cache: list[dict] | None = None
        self._subcall_subscribed_keys: set[str] = set()
        try:
            self._subscribe_subtree()
        except Exception:
            pass

    def update(self) -> None:
        try:
            self._active_tree_cache = None
            self._full_tree_cache = None
            self._subcall_counts_cache = None
            self._executing_cache = None
        except Exception:
            pass
        super().update()
        try:
            self._subscribe_subtree()
        except Exception:
            pass

    def toggle(self):
        self.is_open = not self.is_open

        self.update()

    def toggle_subcalls(self):
        """Show/hide finished sub-calls (loads the full tree on demand)."""
        self.show_finished = not self.show_finished
        self.update()

    def toggle_queued(self):
        """Show/hide queued (waiting, non-executing) sub-calls."""
        self.show_queued = not self.show_queued
        self.update()

    # -- Sub-call tree -------------------------------------------------
    # By default only ACTIVE (non-ENDED) sub-calls are loaded: finished
    # branches are pruned at the DB level, so a long-finished tool costs
    # one cheap query instead of a full subtree walk. The full tree
    # (including finished calls) loads only after toggle_subcalls().
    def _get_active_tree(self) -> list[dict]:
        """Cached active-only descendant list (never raises)."""
        if self._active_tree_cache is not None:
            return self._active_tree_cache
        try:
            tree = self.subject.get_subcall_tree(
                max_depth=6, max_nodes=50, active_only=True
            )
        except Exception:
            tree = []
        self._active_tree_cache = tree
        return tree

    def _get_full_tree(self) -> list[dict]:
        """Cached full descendant list, loaded on demand (never raises)."""
        if self._full_tree_cache is not None:
            return self._full_tree_cache
        try:
            tree = self.subject.get_subcall_tree(max_depth=6, max_nodes=3000)
        except Exception:
            tree = []
        self._full_tree_cache = tree
        return tree

    def _get_subcall_counts(self) -> dict:
        """Cached cheap {"active": int, "finished": int} counts (never raises)."""
        if self._subcall_counts_cache is not None:
            return self._subcall_counts_cache
        try:
            counts = self.subject.count_subcalls(max_depth=6, max_nodes=3000)
        except Exception:
            counts = {"active": 0, "finished": 0}
        self._subcall_counts_cache = counts
        return counts

    def _get_visible_tree(self) -> list[dict]:
        """Queued (non-ended) tree when expanded, full tree for finished.

        Defaults to ``[]``: the executing pins (see :meth:`subcall_nodes`)
        are the only rows shown unless an expander is open — this keeps
        huge queued backlogs out of every chat render.
        """
        try:
            if self.show_finished:
                return self._get_full_tree()
            if self.show_queued:
                return self._get_active_tree()
            return []
        except Exception:
            return []

    @property
    def has_subcalls(self) -> bool:
        try:
            counts = self._get_subcall_counts()
            return (counts.get("active", 0) or 0) + (counts.get("finished", 0) or 0) > 0
        except Exception:
            return False

    @property
    def total_subcall_count(self) -> int:
        try:
            counts = self._get_subcall_counts()
            return (counts.get("active", 0) or 0) + (counts.get("finished", 0) or 0)
        except Exception:
            return 0

    @property
    def active_subcall_count(self) -> int:
        try:
            return int(self._get_subcall_counts().get("active", 0) or 0)
        except Exception:
            return 0

    @property
    def finished_subcall_count(self) -> int:
        try:
            return int(self._get_subcall_counts().get("finished", 0) or 0)
        except Exception:
            return 0

    @property
    def waiting_subcall_count(self) -> int:
        """Queued sub-calls: non-finished but not currently executing."""
        try:
            return max(0, self.active_subcall_count - self.executing_subcall_count)
        except Exception:
            return 0

    def _get_executing_pins(self) -> list[dict]:
        """Currently-executing descendants, found even past walk caps.

        First uses the capped walk's ``executing`` hits (fetched by pk);
        when the walk found unfinished calls but no executing one — i.e. on
        huge trees where the cap cut off before reaching it — falls back to
        :meth:`get_executing_subcalls` reverse lookup (tiny global ACTIVE
        set, walked upwards). Cached per render cycle, never raises.
        """
        if getattr(self, "_executing_cache", None) is not None:
            return self._executing_cache
        pins: list[dict] = []
        try:
            counts = self._get_subcall_counts()
            for pk, depth in counts.get("executing", None) or []:
                try:
                    from server.models.tasks.agent_task_call import AgentTaskCall
                    call = AgentTaskCall.objects.select_related(
                        "task_definition"
                    ).filter(pk=pk).first()
                except Exception:
                    call = None
                if call is not None:
                    pins.append({"call": call, "depth": depth})
            if not pins and (counts.get("active", 0) or 0) > 0:
                try:
                    pins = self.subject.get_executing_subcalls() or []
                except Exception:
                    pins = []
        except Exception:
            pins = []
        self._executing_cache = pins
        return pins

    @property
    def executing_subcall_count(self) -> int:
        """Calls with status ACTIVE (actually executing, not just queued)."""
        try:
            return len(self._get_executing_pins())
        except Exception:
            return 0

    @property
    def subcalls_truncated(self) -> bool:
        """Whether the sub-call counts hit walk caps (real tree is bigger)."""
        try:
            return bool(self._get_subcall_counts().get("truncated", False))
        except Exception:
            return False

    def _node_for(self, call, depth: int) -> dict | None:
        """Template-ready node dict for one sub-call (never raises)."""
        try:
            if call is None:
                return None
            try:
                name = getattr(getattr(call, "task_definition", None), "name", None) or f"call #{getattr(call, 'pk', '?')}"
            except Exception:
                name = f"call #{getattr(call, 'pk', '?')}"
            try:
                status = getattr(call, "status", "") or ""
                detail = getattr(call, "status_detail", "") or ""
            except Exception:
                status, detail = "", ""
            return {
                "pk": getattr(call, "pk", "?"),
                "name": name,
                "status": status,
                "status_detail": detail,
                "status_class": _status_class_for(call),
                "active": (status or "") != "ENDED",
                "executing": (status or "") == "ACTIVE",
                "indent": max(0, (int(depth or 1) - 1)) * 14,
                "duration": _subcall_duration(call),
                "updated": _fmt_clock(getattr(call, "updated_at", None)),
            }
        except Exception:
            return None

    def _get_pin_paths(self) -> list[dict]:
        """Active path(s): ancestors from root down to each executing pin.

        A lone executing row with a deep indent shows no context, so each
        pin is preceded by its ancestor chain below this card (root-down,
        shared prefixes merged). One extra narrow query per card, only when
        pins exist. Never raises.
        """
        paths: list[dict] = []
        try:
            pins = self._get_executing_pins()
        except Exception:
            return paths
        if not pins:
            return paths
        try:
            root_pk = getattr(self.subject, "pk", None)
        except Exception:
            return paths
        # Collect ancestor pks per pin (bottom-up), then fetch in one query.
        chains: list[tuple[list[int], dict]] = []
        wanted: set[int] = set()
        try:
            for pin in pins:
                call = pin.get("call")
                depth = int(pin.get("depth", 1) or 1)
                if call is None or getattr(call, "pk", None) is None:
                    continue
                try:
                    ancestors = call.get_ancestor_call_pks() or []
                except Exception:
                    ancestors = []
                if root_pk in ancestors:
                    idx = ancestors.index(root_pk)
                    # Bottom-up prefix excluding this card itself; depth of
                    # the pin's parent is depth-1, decreasing upwards.
                    chain = [
                        (pk, depth - 1 - j)
                        for j, pk in enumerate(ancestors[:idx])
                    ]
                    chains.append((chain, pin))
                    wanted.update(pk for pk, _ in chain)
                else:
                    chains.append(([], pin))
        except Exception:
            return paths
        cmap: dict[int, Any] = {}
        if wanted:
            try:
                from server.models.tasks.agent_task_call import AgentTaskCall
                cmap = {
                    c.pk: c
                    for c in AgentTaskCall.objects.select_related(
                        "task_definition"
                    ).filter(pk__in=list(wanted)[:200])
                }
            except Exception:
                cmap = {}
        seen: set[int] = set()
        try:
            for chain, pin in chains:
                for pk, depth in reversed(chain):  # root-down
                    if pk in seen:
                        continue
                    call = cmap.get(pk)
                    if call is None:
                        continue
                    paths.append({"call": call, "depth": depth})
                    seen.add(pk)
                call = pin.get("call")
                if call is not None and getattr(call, "pk", None) not in seen:
                    paths.append({"call": call, "depth": pin.get("depth", 1)})
                    seen.add(call.pk)
        except Exception:
            pass
        return paths

    @property
    def subcall_nodes(self) -> list[dict]:
        """Template-ready flat nodes: active path(s), then visible tree.

        The currently-executing (``ACTIVE``) calls render with their
        ancestor chain from this card down (the active path), regardless
        of display caps — followed by the rest of the visible tree
        (queued/finished rows only when expanded). Never raises.
        """
        nodes: list[dict] = []
        seen: set = set()
        try:
            for entry in self._get_pin_paths():
                call = entry.get("call")
                if call is not None and getattr(call, "pk", None) is not None:
                    seen.add(call.pk)
                node = self._node_for(call, entry.get("depth", 1))
                if node is not None:
                    nodes.append(node)
            for entry in self._get_visible_tree():
                call = entry.get("call")
                if call is not None and getattr(call, "pk", None) in seen:
                    continue
                node = self._node_for(call, entry.get("depth", 1))
                if node is not None:
                    nodes.append(node)
        except Exception:
            pass
        return nodes

    def _subscribe_subtree(self) -> None:
        """Subscribe to descendant updates so the tree refreshes live.

        Subscribes to ``AgentTaskCall.pk:<child>`` for status changes and
        to ``AgentTaskCall.parent_taskrun:<run>`` for newly spawned
        children at every level — which fires cross-session too (delegate
        children share the parent run but live in another session, so the
        chat's ``AgentTaskCall.session:<sid>`` watch would miss them).
        """
        try:
            from ui.lib.model_view import orm_subscribe
        except Exception:
            return
        if getattr(self, "_instance", None) is None:
            return
        tree = self._get_visible_tree()
        try:
            pins = self._get_pin_paths()
        except Exception:
            pins = []
        combined = list(tree) + [p for p in pins if p.get("call") is not None]
        run_pks: set[int] = set()
        try:
            from server.models.tasks.agent_task_run import AgentTaskRun
            call_pks = [getattr(self.subject, "pk", None)]
            for entry in combined:
                call = entry.get("call")
                pk = getattr(call, "pk", None) if call is not None else None
                if pk is not None:
                    call_pks.append(pk)
            call_pks = [pk for pk in call_pks if pk is not None][:250]
            if call_pks:
                run_pks.update(
                    AgentTaskRun.objects.filter(
                        agent_task_call_id__in=call_pks
                    ).values_list("pk", flat=True)[:500]
                )
        except Exception:
            pass
        keys: set[str] = set()
        for entry in combined:
            call = entry.get("call")
            pk = getattr(call, "pk", None) if call is not None else None
            if pk is not None:
                keys.add(f"AgentTaskCall.pk:{pk}")
        for run_pk in run_pks:
            keys.add(f"AgentTaskCall.parent_taskrun:{run_pk}")
        for key in keys:
            if key in self._subcall_subscribed_keys:
                continue
            try:
                orm_subscribe(self, key, self._on_subcall_event)
                self._subcall_subscribed_keys.add(key)
            except Exception:
                continue

    def _on_subcall_event(self, key=None, model=None, pk=None, action=None, data=None) -> None:
        """Redis callback for subtree changes: refresh + resubscribe."""
        try:
            subj = getattr(self, "subject", None)
            if subj is not None and getattr(subj, "pk", None) is not None:
                try:
                    subj.refresh_from_db()
                except Exception:
                    pass
            self._active_tree_cache = None
            self._full_tree_cache = None
            self._subcall_counts_cache = None
            self._executing_cache = None
        except Exception:
            pass
        try:
            self.update()
        except Exception:
            pass

    def approve_call(self) -> None:
        from runtime.tasks.call_scheduler import CallScheduler
        CallScheduler.approve_taskcall(self.subject.pk)

    def deny_call(self, feedback: str = "") -> None:
        from runtime.tasks.call_scheduler import CallScheduler
        CallScheduler.deny_taskcall(self.subject.pk, feedback=feedback)

