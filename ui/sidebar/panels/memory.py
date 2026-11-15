"""Memory sidebar panel — the scope tree, one compact row per node.

The panel is a navigator, not an editor: clicking the header opens the
overview, clicking a node opens its detail tab, and the improvement ledger is
one click away.  Rows carry only the numbers a user acts on (changed sources,
proposals) so the list stays scannable.
"""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from ui.lib.model_view import ModelView
# Tab identifiers for the memory panel navigation
OVERVIEW_TAB = "overview"
IMPROVEMENTS_TAB = "improvements"

# MINIMAL view classes for template rendering (pyhtmlgui deprecated)
class MemoryView:
    pass


class MemoryNodeView:
    pass


class MemoryImprovementsView:
    pass



from ui.main.memory.memory_data import (
    MemoryInventory,
    build_inventory,
    unique_proposals,
)

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.app_view import UiAppView
    from ui.sidebar.sidebar import SidebarView


class SidebarPanelMemory(ModelView):
    DOM_ELEMENT_CLASS = "panel-view"
    CSS_STR = ""
    TEMPLATE_STR = '''
        <div class="panel-head">
            <span>Memory</span>
            <div class="panel-head-actions">
                <button class="panel-head-btn" onclick="pyview.open_overview()" title="Memory overview" aria-label="Memory overview">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2z"/></svg>
                </button>
                <button class="panel-head-btn" onclick="pyview.open_improvements()" title="Improvement proposals" aria-label="Improvement proposals">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 18h6"/><path d="M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z"/></svg>
                </button>
                <button class="panel-head-btn" onclick="pyview.reload()" title="Reload from disk" aria-label="Reload from disk">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                </button>
            </div>
        </div>

        <div class="mem-panel-summary">
            {{ pyview.totals.nodes }} node(s) · {{ pyview.proposal_count }} proposal(s)
            {% if pyview.totals.pending %} · <span style="color:var(--warning,#f59e0b)">{{ pyview.totals.pending }} changed</span>{% endif %}
            {% if pyview.totals.missing %} · <span style="color:var(--danger)">{{ pyview.totals.missing }} missing</span>{% endif %}
        </div>

        <div class="mem-panel-search">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
            <input placeholder="Search memory..." value="{{ pyview.search }}" oninput="pyview.set_search(this.value)">
        </div>

        {% if not pyview.totals.nodes %}
            <div class="mem-empty">
                No memory yet. Synthesized scope, agent and task nodes appear here.
            </div>
        {% elif not pyview.scopes %}
            <div class="mem-empty">No node matches “{{ pyview.search }}”.</div>
        {% endif %}

        {% for scope in pyview.scopes %}
            <div class="mem-panel-section">
                {{ scope.label }}
                <span class="mem-badge">{{ scope.nodes|length }}</span>
                {% if scope.pending_count %}<span class="mem-badge warn">{{ scope.pending_count }} changed</span>{% endif %}
                {% if scope.missing_count %}<span class="mem-badge err">{{ scope.missing_count }} missing</span>{% endif %}
            </div>
            {% for node in scope.nodes %}
            <div class="mem-row{% if node.id == pyview.selected_id %} active{% endif %}" onclick="pyview.open_node('{{ node.id }}')">
                <span class="mem-row-kind">{{ node.kind_label }}</span>
                <div class="mem-row-main">
                    <div class="mem-row-label">{{ node.label }}</div>
                    <div class="mem-row-sub">{{ node.relative_path }}</div>
                </div>
                <div class="mem-row-badges">
                    {% if node.pending_count %}<span class="mem-badge warn" title="changed sources">{{ node.pending_count }}</span>{% endif %}
                    {% if node.missing_count %}<span class="mem-badge err" title="missing sources">!</span>{% endif %}
                    {% if node.directive_count %}<span class="mem-badge ok" title="directives">{{ node.directive_count }}d</span>{% endif %}
                    {% if node.proposal_count %}<span class="mem-badge warn" title="proposals">{{ node.proposal_count }}p</span>{% endif %}
                </div>
            </div>
            {% endfor %}
        {% endfor %}

        <div class="mem-panel-section">Ledger</div>
        <div class="mem-row" onclick="pyview.open_improvements()">
            <span class="mem-row-kind">Ledger</span>
            <div class="mem-row-main">
                <div class="mem-row-label">Improvement proposals</div>
                <div class="mem-row-sub">{{ pyview.proposal_count }} open · {{ pyview.queued_count }} filed</div>
            </div>
        </div>
    '''

    def __init__(self, subject: "UiApp", parent: "SidebarView", **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.root_view
        self.project_id: int | None = getattr(parent, "selected_project_id", None)
        self.search = ""
        self._inventory: MemoryInventory | None = None
        self._queued_cache: dict[str, dict[str, Any]] | None = None
        self._overview_subject = OVERVIEW_TAB
        self._improvements_subject = IMPROVEMENTS_TAB

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    @property
    def inventory(self) -> MemoryInventory:
        if self._inventory is None:
            self._inventory = build_inventory(self.project_id)
        return self._inventory

    @property
    def totals(self) -> dict[str, int]:
        return self.inventory.totals

    @property
    def selected_id(self) -> str | None:
        panel = getattr(self.root_view, "main_panel", None)
        tab = getattr(panel, "selected_tab_view", None) if panel else None
        subject = getattr(tab, "subject", None) if tab else None
        return getattr(subject, "id", None)

    @property
    def queued_count(self) -> int:
        if self._queued_cache is None:
            from runtime.memory_improvements import queued_work_items

            self._queued_cache = queued_work_items()
        return sum(
            1
            for proposal in unique_proposals(self.inventory.nodes)
            if str(proposal.get("fingerprint") or "") in self._queued_cache
        )

    @property
    def proposal_count(self) -> int:
        return len(unique_proposals(self.inventory.nodes))

    def _matches(self, node) -> bool:
        needle = (self.search or "").strip().lower()
        if not needle:
            return True
        return needle in " ".join(
            (
                node.label,
                node.scope.label,
                node.relative_path,
                node.agent_name or "",
                node.group_key or "",
            )
        ).lower()

    @property
    def scopes(self):
        out = []
        for scope in self.inventory.scopes:
            nodes = [node for node in scope.nodes if self._matches(node)]
            if nodes:
                out.append(replace(scope, nodes=nodes))
        return out

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    @property
    def memory_list(self):
        """Hook for ``MainView._update_sidebar_active``: re-render this panel.

        The panel is a plain rendered list (no QuerySetView), so the shared
        "refresh the selected panel's list" loop just calls ``update()`` on
        whatever object this attribute returns.
        """
        return self

    def _reload(self) -> None:
        self._inventory = None
        self._queued_cache = None

    def reload(self) -> None:
        self._reload()
        self.update()

    def set_search(self, value: str) -> None:
        self.search = (value or "").strip()
        self.update()

    def set_project_filter(self, project_id: int | None) -> None:
        self.project_id = project_id
        self._reload()
        self.update()
        self._refresh_open_tab()

    def _panel(self):
        return getattr(self.root_view, "main_panel", None)

    def _open(self, view_class: type, subject: Any) -> None:
        panel = self._panel()
        if panel is None or not hasattr(panel, "create_and_open_tab"):
            return
        panel.create_and_open_tab(view_class, subject)

    def open_node(self, node_id: str) -> None:
        node = next(
            (node for node in self.inventory.nodes if node.id == str(node_id)), None
        )
        if node is not None:
            self._open(MemoryNodeView, node)

    def open_overview(self) -> None:
        self._open(MemoryView, self._overview_subject)

    def open_improvements(self) -> None:
        self._open(MemoryImprovementsView, self._improvements_subject)

    def _refresh_open_tab(self) -> None:
        panel = self._panel()
        tab = getattr(panel, "selected_tab_view", None) if panel else None
        if isinstance(tab, (MemoryView, MemoryImprovementsView)):
            try:
                tab.update()
            except Exception:  # pylint: disable=broad-exception-caught
                pass

    def panel_activated(self) -> None:
        """Clicking the Memory rail icon opens the overview."""
        try:
            self.open_overview()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
