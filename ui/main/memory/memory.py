"""Memory UI — overview, node detail, and the improvement-proposal inbox.

The memory tree is inspected read-only; see :mod:`ui.main.memory.memory_data`.
This module is the presentation layer.  It deliberately never runs the memory
walker or edits a memory file: the walker is the synthesizer's job, and a
browser click must not mutate what an agent has learned.

What the three views are for:

``MemoryView``
    The landing tab.  Health of the whole tree, what needs a walk, and every
    scope/node in one place.

``MemoryNodeView``
    One node: the facts (``memory.md``), the playbook directives, the
    improvement proposals, and the source manifest from the last walk.

``MemoryImprovementsView``
    Every proposal in scope, deduplicated by fingerprint, with a deliberate
    "file as backlog work item" action.  Nothing is auto-applied or promoted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from markupsafe import Markup

from ui.lib.model_view import ModelView
from ui.main.memory.memory_data import (
    MemoryInventory,
    MemoryNode,
    build_inventory,
    find_node,
    unique_proposals,
)

if TYPE_CHECKING:
    from ui.main.main_view import MainView


#: Subject for the singleton overview/improvement tabs.  A stable ``id`` keeps
#: one tab per view instead of one per click.
@dataclass(frozen=True)
class MemoryTab:
    id: str
    name: str


OVERVIEW_TAB = MemoryTab("memory-overview", "Memory")
IMPROVEMENTS_TAB = MemoryTab("memory-improvements", "Memory improvements")


_MEMORY_CSS = '''
.mem-page { padding: 0; }
.mem-hero {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 10px;
    margin-bottom: 16px;
}
.mem-stat {
    border: 1px solid var(--border);
    border-radius: 10px;
    background: var(--surface);
    padding: 12px 14px;
}
.mem-stat-label {
    font-size: 11px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: .04em;
}
.mem-stat-value {
    font-size: 22px;
    font-weight: 650;
    font-variant-numeric: tabular-nums;
    margin-top: 3px;
}
.mem-stat-sub { font-size: 11px; color: var(--muted); margin-top: 2px; }
.mem-stat.warn .mem-stat-value { color: var(--warning, #f59e0b); }
.mem-stat.err .mem-stat-value { color: var(--danger); }
.mem-stat.ok .mem-stat-value { color: var(--success, #22c55e); }

.mem-section { margin-bottom: 16px; }
.mem-section-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 8px;
}
.mem-section-title { font-size: 14px; font-weight: 600; }
.mem-section-sub { font-size: 12px; color: var(--muted); }

.mem-scope-group { margin-bottom: 12px; }
.mem-scope-head {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    font-weight: 600;
    color: var(--muted);
    padding: 6px 4px 4px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 4px;
}
.mem-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 8px;
    cursor: pointer;
    border: 1px solid transparent;
}
.mem-row:hover { background: var(--hover-bg); border-color: var(--border); }
.mem-row.active { background: var(--accent-bg); border-color: var(--accent-bg-strong); }
.mem-row-main { min-width: 0; flex: 1; }
.mem-row-label { font-size: 13px; font-weight: 550; }
.mem-row-sub { font-size: 11px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mem-row-kind {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: .04em;
    color: var(--muted);
    border: 1px solid var(--border);
    border-radius: 5px;
    padding: 1px 5px;
    flex-shrink: 0;
}
.mem-row-badges { display: flex; gap: 4px; flex-shrink: 0; flex-wrap: wrap; justify-content: flex-end; }

.mem-badge {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    font-size: 10px;
    font-weight: 600;
    border-radius: 999px;
    padding: 2px 7px;
    border: 1px solid var(--border);
    color: var(--muted);
    background: var(--surface);
    white-space: nowrap;
}
.mem-badge.ok { color: var(--success, #22c55e); border-color: color-mix(in srgb, var(--success, #22c55e) 45%, var(--border)); }
.mem-badge.warn { color: var(--warning, #f59e0b); border-color: color-mix(in srgb, var(--warning, #f59e0b) 45%, var(--border)); }
.mem-badge.err { color: var(--danger); border-color: color-mix(in srgb, var(--danger) 45%, var(--border)); }
.mem-badge.kind { color: var(--accent-text); border-color: var(--accent-bg-strong); background: var(--accent-bg); }

.mem-empty {
    padding: 18px;
    text-align: center;
    color: var(--muted);
    font-size: 13px;
    border: 1px dashed var(--border);
    border-radius: 10px;
}
.mem-muted { color: var(--muted); font-size: 12px; }
.mem-mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
.mem-message {
    border-radius: 8px;
    padding: 8px 12px;
    margin-bottom: 12px;
    font-size: 13px;
    border: 1px solid var(--border);
    background: var(--surface);
}
.mem-message.ok { border-color: color-mix(in srgb, var(--success, #22c55e) 45%, var(--border)); }
.mem-message.err { border-color: color-mix(in srgb, var(--danger) 45%, var(--border)); color: var(--danger); }

.mem-filter-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    margin-bottom: 12px;
}
.mem-filter-bar select, .mem-filter-bar input[type="text"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 7px;
    color: var(--text);
    font-size: 12px;
    padding: 6px 8px;
}
.mem-filter-check { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: var(--muted); }

.mem-markdown { line-height: 1.6; font-size: 14px; padding: 4px 2px; }
.mem-markdown h1 { font-size: 17px; margin: 14px 0 6px; }
.mem-markdown h2 { font-size: 15px; margin: 12px 0 5px; }
.mem-markdown h3 { font-size: 14px; margin: 10px 0 4px; }
.mem-markdown p { margin: 5px 0; }
.mem-markdown ul, .mem-markdown ol { margin: 4px 0; padding-left: 20px; }
.mem-markdown code { background: var(--card-bg); border-radius: 3px; padding: 1px 4px; font-size: 12.5px; }
.mem-markdown pre { background: var(--card-bg); border: 1px solid var(--border); border-radius: 6px; padding: 8px 10px; overflow-x: auto; }
.mem-markdown pre code { background: none; padding: 0; }
.mem-markdown blockquote { border-left: 3px solid var(--border); padding-left: 12px; margin: 8px 0; color: var(--muted); }

.mem-raw summary { cursor: pointer; color: var(--muted); font-size: 12px; padding: 4px 0; }
.mem-raw pre {
    margin: 4px 0 0;
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 8px;
    overflow-x: auto;
    font-size: 11.5px;
    line-height: 1.5;
    white-space: pre-wrap;
}

.mem-directive, .mem-proposal {
    border: 1px solid var(--border);
    border-radius: 9px;
    background: var(--surface);
    padding: 10px 12px;
    margin-bottom: 8px;
}
.mem-directive-head, .mem-proposal-head {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    margin-bottom: 6px;
}
.mem-directive-rule { font-size: 13px; line-height: 1.5; }
.mem-directive-rule em { color: var(--muted); font-style: normal; font-weight: 550; }
.mem-proposal-summary { font-size: 13px; font-weight: 600; line-height: 1.45; }
.mem-proposal-detail { font-size: 12.5px; line-height: 1.55; margin-top: 5px; white-space: pre-wrap; }
.mem-proposal-meta { font-size: 11.5px; color: var(--muted); margin-top: 5px; line-height: 1.5; }
.mem-proposal-actions { display: flex; gap: 6px; align-items: center; margin-top: 8px; flex-wrap: wrap; }
.mem-proposal-actions .btn { font-size: 11.5px; padding: 4px 10px; }

.mem-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.mem-table th {
    text-align: left;
    color: var(--muted);
    font-weight: 600;
    font-size: 10.5px;
    text-transform: uppercase;
    letter-spacing: .04em;
    padding: 6px 8px;
    border-bottom: 1px solid var(--border);
}
.mem-table td { padding: 6px 8px; border-bottom: 1px solid var(--border); vertical-align: top; }
.mem-table tr:last-child td { border-bottom: none; }

.mem-ladder { font-size: 12.5px; line-height: 1.65; color: var(--muted); }
.mem-ladder strong { color: var(--text); }
.mem-ladder code { background: var(--card-bg); border-radius: 3px; padding: 1px 4px; }

.mem-panel-summary { font-size: 11px; color: var(--muted); padding: 2px 4px 8px; line-height: 1.5; }
.mem-panel-search {
    display: flex;
    align-items: center;
    gap: 6px;
    border: 1px solid var(--border);
    border-radius: 7px;
    padding: 5px 8px;
    margin-bottom: 8px;
    background: var(--surface);
}
.mem-panel-search input {
    border: none;
    background: none;
    outline: none;
    color: var(--text);
    font-size: 12px;
    width: 100%;
}
.mem-panel-section { font-size: 10.5px; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); padding: 8px 4px 3px; }
'''

#: Public alias so the sidebar panel (and tests) can reuse the same rules.
MEMORY_CSS = _MEMORY_CSS


def _main_panel(view: ModelView) -> Any:
    root = getattr(view, "root_view", None)
    panel = getattr(root, "main_panel", None)
    if panel is not None:
        return panel
    parent = getattr(view, "parent", None)
    return panel if panel is not None else parent


class _MemoryBase(ModelView):
    """Shared plumbing: live project filter, render-scoped inventory cache."""

    CSS_STR = _MEMORY_CSS
    DOM_ELEMENT_CLASS = "main-view"

    def __init__(self, subject: Any, parent: Any, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view = getattr(parent, "parent", None)
        self.message = ""
        self.message_ok = True
        self._inventory: MemoryInventory | None = None

    @property
    def project_id(self) -> int | None:
        sidebar = getattr(self.root_view, "sidebar", None)
        if sidebar is None:
            return None
        return getattr(sidebar, "selected_project_id", None)

    @property
    def inventory(self) -> MemoryInventory:
        if self._inventory is None:
            self._inventory = build_inventory(self.project_id)
        return self._inventory

    def update(self, *args, **kwargs):
        self._inventory = None
        return super().update(*args, **kwargs)

    def refresh(self) -> None:
        self.message = ""
        self.update()

    def _open(self, view_class: type, subject: Any) -> None:
        panel = _main_panel(self)
        if panel is not None and hasattr(panel, "create_and_open_tab"):
            panel.create_and_open_tab(view_class, subject)

    def open_node(self, node_id: str) -> None:
        node = find_node(self.inventory, str(node_id))
        if node is None:
            self.message, self.message_ok = "That memory node no longer exists.", False
            self.update()
            return
        self._open(MemoryNodeView, node)

    def open_improvements(self) -> None:
        self._open(MemoryImprovementsView, IMPROVEMENTS_TAB)


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


class MemoryView(_MemoryBase):
    """Landing tab: health, attention list, and every node in scope."""

    def __init__(self, subject: Any, parent: Any, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def project_label(self) -> str:
        pid = self.project_id
        if pid is None:
            return "All projects"
        for scope in self.inventory.scopes:
            if scope.project_id == pid and scope.kind == "project":
                return scope.name
        return f"Project {pid}"

    @property
    def totals(self) -> dict[str, int]:
        return self.inventory.totals

    @property
    def stale_nodes(self) -> list[MemoryNode]:
        return self.inventory.stale_nodes

    @property
    def scopes(self):
        return self.inventory.scopes

    @property
    def warnings(self) -> list[str]:
        return self.inventory.warnings

    @property
    def errors(self) -> list[str]:
        out = []
        for node in self.inventory.nodes:
            for error in node.errors:
                out.append(f"{node.id}: {error}")
        return out

    def open_overview(self) -> None:
        self.update()

    TEMPLATE_STR = '''
        <div class="main-view-header">
            <div class="main-view-title-row">
                <div class="main-view-title">Memory</div>
                <span class="mem-badge kind">{{ pyview.project_label }}</span>
            </div>
            <div class="main-view-actions">
                <button class="panel-head-btn" title="Improvement proposals" onclick="pyview.open_improvements()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 18h6"/><path d="M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z"/></svg>
                </button>
                <button class="panel-head-btn" title="Refresh" onclick="pyview.refresh()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                </button>
            </div>
        </div>
        <div class="main-view-body">
            <div class="main-view-content mem-page">

                {% if pyview.message %}
                <div class="mem-message {% if pyview.message_ok %}ok{% else %}err{% endif %}">{{ pyview.message }}</div>
                {% endif %}

                <div class="mem-hero">
                    <div class="mem-stat">
                        <div class="mem-stat-label">Nodes</div>
                        <div class="mem-stat-value">{{ pyview.totals.nodes }}</div>
                        <div class="mem-stat-sub">{{ pyview.totals.scopes }} scope(s) · {{ pyview.totals.agents }} agent(s) · {{ pyview.totals.tasks }} task(s)</div>
                    </div>
                    <div class="mem-stat {% if pyview.totals.pending %}warn{% endif %}">
                        <div class="mem-stat-label">Needs a walk</div>
                        <div class="mem-stat-value">{{ pyview.totals.pending }}</div>
                        <div class="mem-stat-sub">changed source(s) not yet synthesized</div>
                    </div>
                    <div class="mem-stat {% if pyview.totals.missing %}err{% endif %}">
                        <div class="mem-stat-label">Missing sources</div>
                        <div class="mem-stat-value">{{ pyview.totals.missing }}</div>
                        <div class="mem-stat-sub">path recorded but no longer present</div>
                    </div>
                    <div class="mem-stat">
                        <div class="mem-stat-label">Directives</div>
                        <div class="mem-stat-value">{{ pyview.totals.directives }}</div>
                        <div class="mem-stat-sub">{{ pyview.totals.active_directives }} active · candidates opt-in</div>
                    </div>
                    <div class="mem-stat {% if pyview.totals.proposals %}warn{% endif %}">
                        <div class="mem-stat-label">Proposals</div>
                        <div class="mem-stat-value">{{ pyview.totals.proposals }}</div>
                        <div class="mem-stat-sub">improvements waiting for a decision</div>
                    </div>
                    <div class="mem-stat">
                        <div class="mem-stat-label">Legacy playbooks</div>
                        <div class="mem-stat-value">{{ pyview.totals.legacy }}</div>
                        <div class="mem-stat-sub">prose reflections inject nothing</div>
                    </div>
                </div>

                {% if pyview.warnings %}
                <div class="mem-message err">
                    {% for warning in pyview.warnings %}<div>{{ warning }}</div>{% endfor %}
                </div>
                {% endif %}

                <div class="mem-section">
                    <div class="mem-section-head">
                        <div>
                            <div class="mem-section-title">Needs attention</div>
                            <div class="mem-section-sub">Nodes whose sources changed since the last synthesize.</div>
                        </div>
                    </div>
                    {% if pyview.stale_nodes %}
                        {% for node in pyview.stale_nodes %}
                        <div class="mem-row" onclick="pyview.open_node('{{ node.id }}')">
                            <span class="mem-row-kind">{{ node.kind_label }}</span>
                            <div class="mem-row-main">
                                <div class="mem-row-label">{{ node.label }}</div>
                                <div class="mem-row-sub">{{ node.scope.label }} · {{ node.relative_path }}</div>
                            </div>
                            <div class="mem-row-badges">
                                {% if node.pending_count %}<span class="mem-badge warn">{{ node.pending_count }} changed</span>{% endif %}
                                {% if node.missing_count %}<span class="mem-badge err">{{ node.missing_count }} missing</span>{% endif %}
                                {% if node.sources_as_of %}<span class="mem-badge">as of {{ node.sources_as_of }}</span>{% else %}<span class="mem-badge">no manifest</span>{% endif %}
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <div class="mem-empty">Every node is current. Nothing is waiting for the memory walker.</div>
                    {% endif %}
                </div>

                <div class="mem-section">
                    <div class="mem-section-head">
                        <div>
                            <div class="mem-section-title">Memory tree</div>
                            <div class="mem-section-sub">Read from disk. Click a node to inspect its facts and playbook.</div>
                        </div>
                        <button class="btn" onclick="pyview.open_improvements()">Open proposals</button>
                    </div>
                    {% if not pyview.totals.nodes %}
                        <div class="mem-empty">No memory has been written yet. A synthesized scope or task node will appear here.</div>
                    {% endif %}
                    {% for scope in pyview.scopes %}
                        {% if scope.nodes %}
                        <div class="mem-scope-group">
                            <div class="mem-scope-head">
                                <span>{{ scope.label }}</span>
                                <span class="mem-badge">{{ scope.nodes|length }} node(s)</span>
                                {% if scope.pending_count %}<span class="mem-badge warn">{{ scope.pending_count }} changed</span>{% endif %}
                                {% if scope.missing_count %}<span class="mem-badge err">{{ scope.missing_count }} missing</span>{% endif %}
                            </div>
                            {% for node in scope.nodes %}
                            <div class="mem-row" onclick="pyview.open_node('{{ node.id }}')">
                                <span class="mem-row-kind">{{ node.kind_label }}</span>
                                <div class="mem-row-main">
                                    <div class="mem-row-label">{{ node.label }}</div>
                                    <div class="mem-row-sub">
                                        {{ node.relative_path }}
                                        {% if node.memory_excerpt %} · {{ node.memory_excerpt }}{% endif %}
                                    </div>
                                </div>
                                <div class="mem-row-badges">
                                    {% if node.directive_count %}<span class="mem-badge ok">{{ node.directive_count }} directive(s)</span>{% endif %}
                                    {% if node.proposal_count %}<span class="mem-badge warn">{{ node.proposal_count }} proposal(s)</span>{% endif %}
                                    {% if node.playbook_legacy %}<span class="mem-badge">legacy</span>{% endif %}
                                    {% if node.status == 'pending' %}<span class="mem-badge warn">needs walk</span>{% elif node.status == 'missing' %}<span class="mem-badge err">missing</span>{% elif node.status == 'empty' %}<span class="mem-badge">empty</span>{% endif %}
                                </div>
                            </div>
                            {% endfor %}
                        </div>
                        {% endif %}
                    {% endfor %}
                </div>

                {% if pyview.errors %}
                <div class="mem-section">
                    <div class="mem-section-title">Parse errors</div>
                    <div class="mem-muted">Invalid files fail closed: the node stays pending so the synthesizer can retry.</div>
                    {% for error in pyview.errors %}
                    <div class="mem-proposal"><span class="mem-badge err">error</span> <span class="mem-mono">{{ error }}</span></div>
                    {% endfor %}
                </div>
                {% endif %}

                <div class="detail-card">
                    <div class="detail-card-title">How memory works</div>
                    <div class="mem-ladder">
                        Memory is the durable result of the reflection loop. Each node keeps:
                        <strong>facts</strong> (<code>memory.md</code>), a <strong>playbook</strong>
                        (<code>reflection.md</code> directives, injected into sessions when enabled),
                        and an <strong>improvement ledger</strong> (<code>improvements.md</code>).
                        <br><br>
                        Improvements climb a capability ladder — memory fact → directive → skill →
                        tool/script → harness fix. This UI never applies one for you. Filing a
                        proposal creates a <strong>backlog</strong> work item; promoting it to ready
                        (and implementing it) stays a human decision.
                        <br><br>
                        Source freshness comes from <code>.memory_sources.md</code>, written by the
                        memory walker. The values here are <em>as of the last walk</em>; this page
                        does not run the walker.
                    </div>
                </div>

            </div>
        </div>
    '''


# ---------------------------------------------------------------------------
# Node detail
# ---------------------------------------------------------------------------


class MemoryNodeView(_MemoryBase):
    """One memory node, read from disk."""

    def __init__(self, subject: MemoryNode, parent: Any, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._node = subject
        self._queued_cache: dict[str, dict[str, Any]] | None = None

    @property
    def node(self) -> MemoryNode:
        return self._node

    @property
    def title(self) -> str:
        return f"{self.node.scope.label} · {self.node.label}"

    @property
    def queued(self) -> dict[str, dict[str, Any]]:
        if self._queued_cache is None:
            from runtime.memory_improvements import queued_work_items

            self._queued_cache = queued_work_items()
        return self._queued_cache

    @property
    def proposal_rows(self) -> list[dict[str, Any]]:
        rows = []
        for proposal in self.node.proposals:
            fingerprint = str(proposal.get("fingerprint") or "")
            item = self.queued.get(fingerprint)
            rows.append(
                {
                    **proposal,
                    "path": self.node.improvements_path.as_posix(),
                    "queued": item,
                    "queueable": bool(fingerprint)
                    and proposal.get("kind") in self._queueable_kinds(),
                }
            )
        return rows

    @staticmethod
    def _queueable_kinds() -> tuple[str, ...]:
        from runtime.memory_improvements import QUEUEABLE_KINDS

        return QUEUEABLE_KINDS

    @property
    def queueable_kinds(self) -> tuple[str, ...]:
        return self._queueable_kinds()

    @property
    def open_proposal_count(self) -> int:
        return len(
            [row for row in self.proposal_rows if row.get("status") != "retired"]
        )

    @property
    def queueable_count(self) -> int:
        return len(
            [
                row
                for row in self.proposal_rows
                if row["queueable"] and not row["queued"] and row.get("status") != "retired"
            ]
        )

    @property
    def project(self) -> Any:
        pid = self.node.scope.project_id
        if pid is None:
            return None
        from server.models.project import Project

        return Project.objects.filter(pk=pid).first()

    def update(self, *args, **kwargs):
        self._queued_cache = None
        return super().update(*args, **kwargs)

    def refresh(self) -> None:
        from ui.main.memory.memory_data import reload_node

        reload_node(self.node)
        self._queued_cache = None
        self.message = ""
        self.update()

    def queue_proposal(self, fingerprint: str) -> None:
        self._queue([fingerprint])

    def queue_all(self) -> None:
        self._queue(None)

    def _queue(self, fingerprints: list[str] | None) -> None:
        from runtime.memory_improvements import queued_work_items, queue_proposals

        proposals = [
            {
                **{key: value for key, value in proposal.items()},
                "path": self.node.improvements_path.as_posix(),
            }
            for proposal in self.node.proposals
        ]
        existing = queued_work_items()
        created, skipped = queue_proposals(
            proposals,
            project=self.project,
            fingerprints=fingerprints,
            existing=existing,
        )
        self._queued_cache = existing
        if created:
            self.message = f"Queued {len(created)} proposal(s) as backlog work items."
            self.message_ok = True
        elif skipped:
            reason = skipped[0].get("reason") or "nothing to do"
            self.message = f"Nothing queued: {reason}."
            self.message_ok = False
        else:
            self.message = "No matching proposals."
            self.message_ok = False
        self.update()

    def open_improvements(self) -> None:
        self._open(MemoryImprovementsView, IMPROVEMENTS_TAB)

    @property
    def memory_html(self) -> Markup:
        return Markup(self.node.read_memory())

    @property
    def reflection_html(self) -> Markup:
        return Markup(self.node.read_reflection())

    @property
    def reflection_raw(self) -> str:
        return self.node.read_reflection()

    @property
    def improvements_raw(self) -> str:
        path = self.node.improvements_path
        try:
            return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        except OSError:
            return ""

    @property
    def sources_raw(self) -> str:
        return self.node.read_sources_raw()

    TEMPLATE_STR = '''
        <div class="main-view-header">
            <div class="main-view-title-row">
                <div class="main-view-title">{{ pyview.node.label }}</div>
                <span class="mem-badge kind">{{ pyview.node.kind_label }}</span>
                <span class="mem-badge">{{ pyview.node.scope.label }}</span>
                {% if pyview.node.playbook_legacy %}<span class="mem-badge">legacy playbook</span>{% endif %}
                {% if pyview.node.status == 'pending' %}<span class="mem-badge warn">needs walk</span>{% elif pyview.node.status == 'missing' %}<span class="mem-badge err">source missing</span>{% endif %}
            </div>
            <div class="main-view-actions">
                <button class="panel-head-btn" title="Improvement proposals" onclick="pyview.open_improvements()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 18h6"/><path d="M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z"/></svg>
                </button>
                <button class="panel-head-btn" title="Reload from disk" onclick="pyview.refresh()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                </button>
            </div>
        </div>
        <div class="main-view-body">
            <div class="main-view-content mem-page">

                {% if pyview.message %}
                <div class="mem-message {% if pyview.message_ok %}ok{% else %}err{% endif %}">{{ pyview.message }}</div>
                {% endif %}

                {% if pyview.node.errors %}
                <div class="mem-message err">
                    {% for error in pyview.node.errors %}<div>{{ error }}</div>{% endfor %}
                </div>
                {% endif %}

                <div class="detail-card">
                    <div class="detail-card-title">Node</div>
                    <div class="mem-table-wrap">
                        <table class="mem-table">
                            <tr><th>Scope</th><td>{{ pyview.node.scope.label }}</td></tr>
                            <tr><th>Layer</th><td>{{ pyview.node.kind_label }}</td></tr>
                            {% if pyview.node.agent_pk is not none %}
                            <tr><th>Agent</th><td>{{ pyview.node.agent_name or ('#' ~ pyview.node.agent_pk) }}{% if pyview.node.agent_name %} <span class="mem-muted">(#{{ pyview.node.agent_pk }})</span>{% endif %}</td></tr>
                            {% endif %}
                            {% if pyview.node.kind == 'task' %}
                            <tr><th>Task group</th><td class="mem-mono">{{ pyview.node.group_key }}</td></tr>
                            {% endif %}
                            <tr><th>Path</th><td class="mem-mono">{{ pyview.node.path }}</td></tr>
                            <tr><th>Facts</th><td>{% if pyview.node.has_memory %}{{ pyview.node.memory_chars }} chars of <code>memory.md</code>{% else %}<span class="mem-muted">no memory.md</span>{% endif %}</td></tr>
                            <tr><th>Sources as of</th><td>{% if pyview.node.sources_as_of %}{{ pyview.node.sources_as_of }}{% else %}<span class="mem-muted">no manifest</span>{% endif %}</td></tr>
                        </table>
                    </div>
                </div>

                <div class="detail-card">
                    <div class="detail-card-title">Facts — memory.md</div>
                    {% if pyview.node.has_memory %}
                        <div class="mem-markdown" id="memFacts_{{ pyview.uid }}">{{ pyview.node.read_memory() }}</div>
                        <script>
                            (function(){var el=document.getElementById('memFacts_{{ pyview.uid }}');if(el)el.innerHTML=marked.parse(el.textContent);})();
                        </script>
                    {% else %}
                        <div class="mem-empty">No facts recorded in this node yet.</div>
                    {% endif %}
                </div>

                <div class="detail-card">
                    <div class="detail-card-title">Playbook — reflection.md</div>
                    {% if not pyview.node.has_reflection %}
                        <div class="mem-empty">No reflection yet. The synthesizer writes one when it processes this node.</div>
                    {% elif pyview.node.playbook_legacy %}
                        <div class="mem-message err" style="margin-bottom:10px">
                            Legacy prose reflection. Nothing is injected from it; the node is upgraded to
                            the directive schema on its next synthesis.
                        </div>
                        <div class="mem-markdown" id="memReflection_{{ pyview.uid }}">{{ pyview.node.read_reflection() }}</div>
                        <script>
                            (function(){var el=document.getElementById('memReflection_{{ pyview.uid }}');if(el)el.innerHTML=marked.parse(el.textContent);})();
                        </script>
                    {% elif not pyview.node.directives %}
                        <div class="mem-empty">This playbook has no directives yet.</div>
                    {% else %}
                        {% for directive in pyview.node.active_directives %}
                        <div class="mem-directive">
                            <div class="mem-directive-head">
                                <span class="mem-badge ok">active</span>
                                <span class="mem-badge kind">{{ directive.routing }}</span>
                                <code class="mem-mono">{{ directive.id }}</code>
                                <span class="mem-badge">support {{ directive.support }}</span>
                            </div>
                            <div class="mem-directive-rule">
                                {% if directive.trigger %}<em>When {{ directive.trigger }}:</em> {% endif %}{{ directive.rule }}
                            </div>
                            {% if directive.capability %}<div class="mem-proposal-meta">Capability: {{ directive.capability }}</div>{% endif %}
                            {% if directive.verification %}<div class="mem-proposal-meta">Check: {{ directive.verification }}</div>{% endif %}
                            {% if directive.evidence %}<div class="mem-proposal-meta">Evidence: {{ directive.evidence|join(', ') }}</div>{% endif %}
                        </div>
                        {% endfor %}
                        {% for directive in pyview.node.candidate_directives %}
                        <div class="mem-directive">
                            <div class="mem-directive-head">
                                <span class="mem-badge warn">candidate</span>
                                <span class="mem-badge kind">{{ directive.routing }}</span>
                                <code class="mem-mono">{{ directive.id }}</code>
                                <span class="mem-badge">support {{ directive.support }}</span>
                            </div>
                            <div class="mem-directive-rule">
                                {% if directive.trigger %}<em>When {{ directive.trigger }}:</em> {% endif %}{{ directive.rule }}
                            </div>
                            {% if directive.evidence %}<div class="mem-proposal-meta">Evidence: {{ directive.evidence|join(', ') }}</div>{% endif %}
                        </div>
                        {% endfor %}
                        {% for directive in pyview.node.retired_directives %}
                        <div class="mem-directive">
                            <div class="mem-directive-head">
                                <span class="mem-badge">retired</span>
                                <code class="mem-mono">{{ directive.id }}</code>
                            </div>
                            <div class="mem-directive-rule mem-muted">{{ directive.rule }}</div>
                        </div>
                        {% endfor %}
                    {% endif %}
                </div>

                <div class="detail-card">
                    <div class="detail-card-title">Improvement proposals</div>
                    <div class="mem-section-head" style="margin-bottom:8px">
                        <div class="mem-section-sub">
                            Filing creates a backlog work item. It does not implement anything.
                        </div>
                        {% if pyview.queueable_count %}
                        <button class="btn primary" onclick="pyview.queue_all()">File all ({{ pyview.queueable_count }})</button>
                        {% endif %}
                    </div>
                    {% if not pyview.proposal_rows %}
                        <div class="mem-empty">No improvement proposals in this node.</div>
                    {% endif %}
                    {% for proposal in pyview.proposal_rows %}
                    <div class="mem-proposal">
                        <div class="mem-proposal-head">
                            <span class="mem-badge kind">{{ proposal.kind }}</span>
                            <span class="mem-badge{% if proposal.status == 'candidate' %} warn{% endif %}">{{ proposal.status }}</span>
                            <span class="mem-badge">{{ proposal.scope or 'task' }}</span>
                            <code class="mem-mono">{{ proposal.id }}</code>
                            {% if proposal.queued %}<span class="mem-badge ok">queued #{{ proposal.queued.id }}</span>{% endif %}
                        </div>
                        <div class="mem-proposal-summary">{{ proposal.summary }}</div>
                        {% if proposal.detail %}<div class="mem-proposal-detail">{{ proposal.detail }}</div>{% endif %}
                        {% if proposal.trigger %}<div class="mem-proposal-meta">Trigger: {{ proposal.trigger }}</div>{% endif %}
                        {% if proposal.acceptance %}<div class="mem-proposal-meta">Acceptance: {{ proposal.acceptance }}</div>{% endif %}
                        {% if proposal.evidence %}<div class="mem-proposal-meta">Evidence: {{ proposal.evidence|join(', ') }}</div>{% endif %}
                        <div class="mem-proposal-actions">
                            {% if proposal.queued %}
                            <span class="mem-muted">Already filed as work item #{{ proposal.queued.id }} ({{ proposal.queued.status }}).</span>
                            {% elif proposal.queueable %}
                            <button class="btn" onclick="pyview.queue_proposal('{{ proposal.fingerprint }}')">File as backlog</button>
                            {% else %}
                            <span class="mem-muted">Not queueable.</span>
                            {% endif %}
                        </div>
                    </div>
                    {% endfor %}
                </div>

                <div class="detail-card">
                    <div class="detail-card-title">Sources — as of the last memory walk</div>
                    {% if pyview.node.sources %}
                        <div class="mem-muted" style="margin-bottom:6px">Recorded {{ pyview.node.sources_as_of or 'unknown' }}. This page does not re-run the walker.</div>
                        <table class="mem-table">
                            <thead><tr><th>Path</th><th>Type</th><th>Status</th><th>Last processed</th><th>Current</th><th>Hours</th><th>Changed</th></tr></thead>
                            <tbody>
                            {% for source in pyview.node.sources %}
                            <tr>
                                <td class="mem-mono">{{ source.path }}</td>
                                <td class="mem-muted">{{ source.type }}</td>
                                <td><span class="mem-badge {% if source.status == 'pending' %}warn{% elif source.status == 'missing' %}err{% else %}ok{% endif %}">{{ source.status_label }}</span></td>
                                <td class="mem-mono">{{ source.last_processed_hash[:10] if source.last_processed_hash else '—' }}</td>
                                <td class="mem-mono">{{ source.current_hash[:10] if source.current_hash else '—' }}</td>
                                <td>{{ source.hours_label }}</td>
                                <td>{{ source.changed_chars }}</td>
                            </tr>
                            {% endfor %}
                            </tbody>
                        </table>
                    {% else %}
                        <div class="mem-empty">No source manifest. The memory walker records one on its next pass.</div>
                    {% endif %}
                </div>

                <div class="detail-card">
                    <div class="detail-card-title">Raw files</div>
                    <details class="mem-raw">
                        <summary>reflection.md</summary>
                        <pre>{{ pyview.reflection_raw or '(missing)' }}</pre>
                    </details>
                    <details class="mem-raw">
                        <summary>improvements.md</summary>
                        <pre>{{ pyview.improvements_raw or '(missing)' }}</pre>
                    </details>
                    <details class="mem-raw">
                        <summary>.memory_sources.md</summary>
                        <pre>{{ pyview.sources_raw or '(missing)' }}</pre>
                    </details>
                    <details class="mem-raw">
                        <summary>memory.md</summary>
                        <pre>{{ pyview.node.read_memory() or '(missing)' }}</pre>
                    </details>
                </div>

            </div>
        </div>
    '''


# ---------------------------------------------------------------------------
# Improvement proposals across the tree
# ---------------------------------------------------------------------------


class MemoryImprovementsView(_MemoryBase):
    """Every proposal in scope, deduplicated, filterable, and fileable."""

    def __init__(self, subject: Any, parent: Any, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.kind_filter = ""
        self.status_filter = ""
        self.scope_filter = ""
        self.search = ""
        self.hide_queued = False
        self._queued_cache: dict[str, dict[str, Any]] | None = None

    @property
    def queued(self) -> dict[str, dict[str, Any]]:
        if self._queued_cache is None:
            from runtime.memory_improvements import queued_work_items

            self._queued_cache = queued_work_items()
        return self._queued_cache

    @property
    def project_label(self) -> str:
        pid = self.project_id
        if pid is None:
            return "All projects"
        for scope in self.inventory.scopes:
            if scope.project_id == pid and scope.kind == "project":
                return scope.name
        return f"Project {pid}"

    @property
    def all_proposals(self) -> list[dict[str, Any]]:
        return unique_proposals(self.inventory.nodes)

    @property
    def kind_options(self) -> list[str]:
        return sorted({str(item.get("kind")) for item in self.all_proposals if item.get("kind")})

    @property
    def status_options(self) -> list[str]:
        return sorted(
            {str(item.get("status")) for item in self.all_proposals if item.get("status")}
        )

    @property
    def scope_options(self) -> list[str]:
        present = {
            str(item.get("source") or "").split(" · ")[0].lower()
            for item in self.all_proposals
        }
        return [item for item in ("global", "project", "workspace") if item in present]

    @property
    def proposals(self) -> list[dict[str, Any]]:
        rows = []
        needle = (self.search or "").strip().lower()
        for proposal in self.all_proposals:
            if self.kind_filter and proposal.get("kind") != self.kind_filter:
                continue
            if self.status_filter and proposal.get("status") != self.status_filter:
                continue
            if self.scope_filter:
                source = str(proposal.get("source") or "")
                if not source.lower().startswith(self.scope_filter):
                    continue
            if needle:
                haystack = " ".join(
                    str(proposal.get(key) or "")
                    for key in ("summary", "detail", "id", "source", "node_label", "trigger")
                ).lower()
                if needle not in haystack:
                    continue
            item = self.queued.get(str(proposal.get("fingerprint") or ""))
            row = {**proposal, "queued": item}
            if self.hide_queued and item:
                continue
            rows.append(row)
        return rows

    @property
    def counts(self) -> dict[str, int]:
        rows = self.proposals
        return {
            "total": len(rows),
            "queued": sum(1 for row in rows if row.get("queued")),
            "queueable": sum(
                1
                for row in rows
                if not row.get("queued")
                and row.get("kind") in self._queueable_kinds()
                and row.get("status") != "retired"
            ),
        }

    @staticmethod
    def _queueable_kinds() -> tuple[str, ...]:
        from runtime.memory_improvements import QUEUEABLE_KINDS

        return QUEUEABLE_KINDS

    @property
    def queueable_kinds(self) -> tuple[str, ...]:
        return self._queueable_kinds()

    def update(self, *args, **kwargs):
        self._queued_cache = None
        return super().update(*args, **kwargs)

    def refresh(self) -> None:
        self.message = ""
        self.update()

    def set_kind_filter(self, value: str) -> None:
        self.kind_filter = (value or "").strip()
        self.update()

    def set_status_filter(self, value: str) -> None:
        self.status_filter = (value or "").strip()
        self.update()

    def set_scope_filter(self, value: str) -> None:
        self.scope_filter = (value or "").strip()
        self.update()

    def set_search(self, value: str) -> None:
        self.search = (value or "").strip()
        self.update()

    def set_hide_queued(self, checked: Any) -> None:
        self.hide_queued = bool(checked)
        self.update()

    def queue_proposal(self, fingerprint: str) -> None:
        self._queue([str(fingerprint)])

    def queue_visible(self) -> None:
        self._queue(None)

    def _project_for(self, proposal: dict[str, Any]) -> Any:
        pid = proposal.get("project_id")
        if pid is None:
            pid = self.project_id
        if pid is None:
            return None
        from server.models.project import Project

        return Project.objects.filter(pk=pid).first()

    def _queue(self, fingerprints: list[str] | None) -> None:
        from runtime.memory_improvements import queue_proposals, queued_work_items

        groups: dict[Any, tuple[Any, list[dict[str, Any]]]] = {}
        for proposal in self.proposals:
            if fingerprints is not None and str(proposal.get("fingerprint")) not in fingerprints:
                continue
            if proposal.get("queued"):
                continue
            project = self._project_for(proposal)
            key = getattr(project, "pk", None)
            groups.setdefault(key, (project, []))[1].append(proposal)

        existing = queued_work_items()
        created: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for project, proposals in groups.values():
            group_created, group_skipped = queue_proposals(
                proposals, project=project, existing=existing
            )
            created.extend(group_created)
            skipped.extend(group_skipped)

        self._queued_cache = existing
        if created:
            self.message = f"Queued {len(created)} proposal(s) as backlog work items."
            self.message_ok = True
        elif skipped:
            self.message = f"Nothing queued: {skipped[0].get('reason')}."
            self.message_ok = False
        else:
            self.message = "Nothing to queue with the current filters."
            self.message_ok = False
        self.update()

    def open_node(self, node_id: str) -> None:
        node = find_node(self.inventory, str(node_id))
        if node is None:
            self.message, self.message_ok = "That memory node no longer exists.", False
            self.update()
            return
        self._open(MemoryNodeView, node)

    TEMPLATE_STR = '''
        <div class="main-view-header">
            <div class="main-view-title-row">
                <div class="main-view-title">Memory improvements</div>
                <span class="mem-badge kind">{{ pyview.project_label }}</span>
            </div>
            <div class="main-view-actions">
                {% if pyview.counts.queueable %}
                <button class="btn primary" onclick="pyview.queue_visible()">File visible ({{ pyview.counts.queueable }})</button>
                {% endif %}
                <button class="panel-head-btn" title="Refresh" onclick="pyview.refresh()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                </button>
            </div>
        </div>
        <div class="main-view-body">
            <div class="main-view-content mem-page">

                {% if pyview.message %}
                <div class="mem-message {% if pyview.message_ok %}ok{% else %}err{% endif %}">{{ pyview.message }}</div>
                {% endif %}

                <div class="mem-hero">
                    <div class="mem-stat">
                        <div class="mem-stat-label">Visible proposals</div>
                        <div class="mem-stat-value">{{ pyview.counts.total }}</div>
                        <div class="mem-stat-sub">deduplicated across scopes</div>
                    </div>
                    <div class="mem-stat {% if pyview.counts.queueable %}warn{% endif %}">
                        <div class="mem-stat-label">Waiting</div>
                        <div class="mem-stat-value">{{ pyview.counts.queueable }}</div>
                        <div class="mem-stat-sub">not filed yet</div>
                    </div>
                    <div class="mem-stat ok">
                        <div class="mem-stat-label">Filed</div>
                        <div class="mem-stat-value">{{ pyview.counts.queued }}</div>
                        <div class="mem-stat-sub">backlog work items</div>
                    </div>
                </div>

                <div class="mem-filter-bar">
                    <select onchange="pyview.set_kind_filter(this.value)">
                        <option value="">All kinds</option>
                        {% for kind in pyview.kind_options %}
                        <option value="{{ kind }}" {% if kind == pyview.kind_filter %}selected{% endif %}>{{ kind }}</option>
                        {% endfor %}
                    </select>
                    <select onchange="pyview.set_status_filter(this.value)">
                        <option value="">All statuses</option>
                        {% for status in pyview.status_options %}
                        <option value="{{ status }}" {% if status == pyview.status_filter %}selected{% endif %}>{{ status }}</option>
                        {% endfor %}
                    </select>
                    <select onchange="pyview.set_scope_filter(this.value)">
                        <option value="">All scopes</option>
                        {% for scope in pyview.scope_options %}
                        <option value="{{ scope }}" {% if scope == pyview.scope_filter %}selected{% endif %}>{{ scope }}</option>
                        {% endfor %}
                    </select>
                    <input type="text" placeholder="Search proposals..." value="{{ pyview.search }}" onchange="pyview.set_search(this.value)">
                    <label class="mem-filter-check">
                        <input type="checkbox" {% if pyview.hide_queued %}checked{% endif %} onchange="pyview.set_hide_queued(this.checked)">
                        Hide filed
                    </label>
                </div>

                {% if not pyview.proposals %}
                    <div class="mem-empty">
                        No proposals match these filters.
                        {% if not pyview.all_proposals %}Improvement proposals appear after a node is synthesized with something bigger than a directive.{% endif %}
                    </div>
                {% endif %}

                {% for proposal in pyview.proposals %}
                <div class="mem-proposal">
                    <div class="mem-proposal-head">
                        <span class="mem-badge kind">{{ proposal.kind }}</span>
                        <span class="mem-badge{% if proposal.status == 'candidate' %} warn{% endif %}">{{ proposal.status }}</span>
                        <span class="mem-badge">{{ proposal.source }}</span>
                        <code class="mem-mono">{{ proposal.id }}</code>
                        {% if proposal.queued %}<span class="mem-badge ok">filed #{{ proposal.queued.id }}</span>{% endif %}
                    </div>
                    <div class="mem-proposal-summary">{{ proposal.summary }}</div>
                    {% if proposal.detail %}<div class="mem-proposal-detail">{{ proposal.detail }}</div>{% endif %}
                    {% if proposal.trigger %}<div class="mem-proposal-meta">Trigger: {{ proposal.trigger }}</div>{% endif %}
                    {% if proposal.acceptance %}<div class="mem-proposal-meta">Acceptance: {{ proposal.acceptance }}</div>{% endif %}
                    {% if proposal.evidence %}<div class="mem-proposal-meta">Evidence: {{ proposal.evidence|join(', ') }}</div>{% endif %}
                    <div class="mem-proposal-meta">
                        From <span class="mem-mono">{{ proposal.node_label }}</span> · {{ proposal.path }}
                    </div>
                    <div class="mem-proposal-actions">
                        <button class="btn" onclick="pyview.open_node('{{ proposal.node_id }}')">Open node</button>
                        {% if proposal.queued %}
                        <span class="mem-muted">Already filed as #{{ proposal.queued.id }} ({{ proposal.queued.status }}).</span>
                        {% elif proposal.kind in pyview.queueable_kinds %}
                        <button class="btn primary" onclick="pyview.queue_proposal('{{ proposal.fingerprint }}')">File as backlog</button>
                        {% else %}
                        <span class="mem-muted">Not queueable.</span>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}

                <div class="detail-card">
                    <div class="detail-card-title">What filing does</div>
                    <div class="mem-ladder">
                        A filed proposal becomes a <strong>backlog</strong> work item with the full
                        spec, acceptance check and evidence. Backlog items do not dispatch. A
                        human promotes one to <em>ready</em> after reviewing it, and implementation
                        still goes through the normal coding/verification path.
                        <br><br>
                        This page never applies a proposal, edits a manifest, or runs the memory
                        walker. Duplicate fingerprints are shown once; the most specific scope wins.
                    </div>
                </div>

            </div>
        </div>
    '''
