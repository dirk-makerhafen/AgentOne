"""Tests for the Memory UI: data layer, proposal flow, and template smoke.

The data layer is filesystem-first, so every test builds a tiny memory tree in
a temporary directory.  The queue test uses the real DB through the shared
:mod:`runtime.memory_improvements` helpers — the same path the agent tool and
the UI use.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

import jinja2
import yaml
from django.test import TestCase

from runtime.memory_improvements import (
    MARKER,
    collect_proposals,
    queued_work_items,
    queue_proposals,
)


class MemoryView:
    TEMPLATE_STR = """\n        <div class="main-view">\n            <div class="main-view-header">\n                <div class="main-view-title">Memory</div>\n            </div>\n            <div class="main-view-body">\n                <div class="main-view-content mem-page">\n                    {{ pyview.message }}\n                </div>\n            </div>\n        </div>\n    """


class MemoryNodeView:
    TEMPLATE_STR = """\n        <div class="main-view">\n            <div class="main-view-header">\n                <div class="main-view-title">Node</div>\n            </div>\n            <div class="main-view-body">\n                <div class="main-view-content mem-page">\n                    {{ pyview.message }}\n                </div>\n            </div>\n        </div>\n    """


class MemoryImprovementsView:
    TEMPLATE_STR = """\n        <div class="main-view">\n            <div class="main-view-header">\n                <div class="main-view-title">Memory improvements</div>\n            </div>\n            <div class="main-view-body">\n                <div class="main-view-content mem-page">\n                    {{ pyview.message }}\n                </div>\n            </div>\n        </div>\n    """



from ui.main.memory.memory_data import (
    MemoryScopeRef,
    build_inventory,
    unique_proposals,
)
from ui.sidebar.panels.memory import SidebarPanelMemory


def _render(template_str, **context):
    env = jinja2.Environment(autoescape=True)
    return env.from_string(template_str).render(**context)


def _frontmatter(payload: dict) -> str:
    return "---\n" + yaml.safe_dump(payload, sort_keys=False) + "---\n"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _playbook(*directives) -> str:
    return _frontmatter(
        {"schema": "agentone.playbook/1", "directives": list(directives)}
    )


def _improvements(*proposals) -> str:
    return _frontmatter(
        {"schema": "agentone.improvements/1", "proposals": list(proposals)}
    )


def _sources(*rows) -> str:
    return _frontmatter(
        {
            "kind": "agent",
            "type": "global-agent",
            "key": "7",
            "name": "7",
            "sources": list(rows),
            "generated_at": "2026-11-01T10:00:00+00:00",
        }
    )


PROPOSAL = {
    "id": "IMP-1",
    "fingerprint": "harness-settings-override",
    "kind": "harness",
    "scope": "global",
    "status": "candidate",
    "summary": "Fix the transient settings override.",
    "detail": "spawn_subagent nests settings_overrides.",
    "acceptance": "No workaround rule remains.",
}


class _TreeTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self._build_tree()

    def _build_tree(self):
        _write(
            self.root / "memory.md",
            "# Scope memory\n\nThis scope covers the whole instance.\n",
        )
        _write(self.root / "reflection.md", "# Legacy reflection\n\nOld prose.\n")

        agent = self.root / "agents" / "7"
        _write(agent / "memory.md", "# Agent memory\n\nThe agent remembers things.\n")
        _write(
            agent / "reflection.md",
            _playbook(
                {
                    "id": "PB-1",
                    "fingerprint": "always-check",
                    "rule": "Check the queue before dispatching.",
                    "trigger": "the queue looks empty",
                    "routing": "prompt",
                    "status": "active",
                    "support": 2,
                    "evidence": ["saw it twice"],
                },
                {
                    "id": "PB-2",
                    "fingerprint": "maybe-skill",
                    "rule": "Consider a skill for this procedure.",
                    "routing": "skill",
                    "status": "candidate",
                    "support": 1,
                },
            ),
        )
        _write(agent / "improvements.md", _improvements(PROPOSAL))
        _write(
            agent / ".memory_sources.md",
            _sources(
                {
                    "path": "tasks/",
                    "type": "global-agent-tasks",
                    "last_processed_hash": "aaa",
                    "current_hash": "bbb",
                    "hours_since_processed": 2.5,
                    "changed_chars": 42,
                },
                {
                    "path": "gone/",
                    "type": "global-agent-gone",
                    "last_processed_hash": "ccc",
                    "current_hash": None,
                },
            ),
        )

        _write(
            agent / "tasks" / "task_default" / "memory.md",
            "# Task memory\n\nA task-level fact.\n",
        )

    def _inventory(self):
        return build_inventory(
            refs=[MemoryScopeRef("global", "global", "Global", self.root)]
        )


class TestInventoryDiscovery(_TreeTest):
    def test_finds_scope_agent_and_task_nodes(self):
        inventory = self._inventory()

        assert [scope.kind for scope in inventory.scopes] == ["global"]
        assert [node.kind for node in inventory.nodes] == ["scope", "agent", "task"]
        assert inventory.totals["nodes"] == 3
        assert inventory.totals["agents"] == 1
        assert inventory.totals["tasks"] == 1

    def test_stable_node_ids(self):
        inventory = self._inventory()
        assert [node.id for node in inventory.nodes] == [
            "memory:global:global:.",
            "memory:global:global:agents/7",
            "memory:global:global:agents/7/tasks/task_default",
        ]

    def test_pending_and_missing_sources_are_counted(self):
        inventory = self._inventory()
        agent = next(node for node in inventory.nodes if node.kind == "agent")

        assert agent.pending_count == 1
        assert agent.missing_count == 1
        assert agent.status == "missing"
        assert inventory.totals["pending"] == 1
        assert inventory.totals["missing"] == 1
        assert inventory.totals["stale"] == 1
        assert [node.id for node in inventory.stale_nodes] == [agent.id]
        assert agent.sources_as_of == "2026-11-01 10:00"

    def test_playbook_directives_are_parsed(self):
        inventory = self._inventory()
        agent = next(node for node in inventory.nodes if node.kind == "agent")
        scope = next(node for node in inventory.nodes if node.kind == "scope")

        assert agent.playbook_legacy is False
        assert agent.directive_count == 2
        assert [item["id"] for item in agent.active_directives] == ["PB-1"]
        assert [item["id"] for item in agent.candidate_directives] == ["PB-2"]
        assert scope.playbook_legacy is True
        assert inventory.totals["legacy"] == 1
        assert inventory.totals["directives"] == 2
        assert inventory.totals["active_directives"] == 1

    def test_memory_excerpt_skips_headings(self):
        inventory = self._inventory()
        agent = next(node for node in inventory.nodes if node.kind == "agent")
        assert agent.memory_excerpt == "The agent remembers things."
        assert agent.has_memory is True


class TestProposalCollection(_TreeTest):
    def test_duplicate_fingerprint_is_shown_once_most_specific_wins(self):
        # A project node restates the global proposal.
        project_root = self.root / "project-memory"
        _write(
            project_root / "agents" / "7" / "improvements.md",
            _improvements(
                {
                    **PROPOSAL,
                    "summary": "Fix the transient settings override (project copy).",
                }
            ),
        )
        inventory = build_inventory(
            refs=[
                MemoryScopeRef("global", "global", "Global", self.root),
                MemoryScopeRef("project", "1", "Site", project_root, project_id=1),
            ]
        )

        proposals = unique_proposals(inventory.nodes)

        assert len(proposals) == 1
        assert proposals[0]["source"] == "Project · Site"
        assert "project copy" in proposals[0]["summary"]
        assert proposals[0]["project_id"] == 1

    def test_collect_proposals_annotates_source_and_path(self):
        proposals, warnings = collect_proposals(
            [("global", self.root)]
        )

        assert warnings == []
        assert proposals[0]["fingerprint"] == PROPOSAL["fingerprint"]
        assert proposals[0]["source"] == "global"
        assert proposals[0]["path"].endswith("improvements.md")


class TestQueueIntegration(_TreeTest):
    def test_queue_files_a_backlog_item_with_the_marker(self):
        from server.models.workitems.enums import WorkItemStatus
        from server.models.workitems.work_item import WorkItem

        proposals = unique_proposals(self._inventory().nodes)
        created, skipped = queue_proposals(proposals)

        assert skipped == []
        assert len(created) == 1
        item = WorkItem.objects.get(pk=created[0]["work_item_id"])
        assert item.status == WorkItemStatus.BACKLOG
        assert item.priority == 60
        assert MARKER.format(fingerprint=PROPOSAL["fingerprint"]) in item.body
        assert "No workaround rule remains." in item.body

    def test_queue_is_idempotent_and_queued_map_is_readable(self):
        from server.models.workitems.work_item import WorkItem

        proposals = unique_proposals(self._inventory().nodes)
        queue_proposals(proposals)
        created, skipped = queue_proposals(proposals)

        assert created == []
        assert skipped[0]["reason"] == "already queued"
        assert WorkItem.objects.count() == 1
        assert PROPOSAL["fingerprint"] in queued_work_items()


class TestOverviewTemplate(_TreeTest):
    def test_renders_health_attention_and_tree(self):
        view = MemoryView.__new__(MemoryView)
        view.root_view = SimpleNamespace(sidebar=None)
        view._inventory = self._inventory()
        view.message = ""
        view.message_ok = True

        html = _render(MemoryView.TEMPLATE_STR, pyview=view)

        assert "Memory" in html
        assert "Needs a walk" in html
        assert "Needs attention" in html
        assert "Agent #7" in html
        assert "1 changed" in html
        assert "1 missing" in html
        assert "How memory works" in html
        assert "backlog" in html

    def test_empty_tree_explains_itself(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        empty = Path(tmp.name) / "memory"
        empty.mkdir()
        view = MemoryView.__new__(MemoryView)
        view.root_view = SimpleNamespace(sidebar=None)
        view._inventory = build_inventory(
            refs=[MemoryScopeRef("global", "global", "Global", empty)]
        )
        view.message = ""
        view.message_ok = True

        html = _render(MemoryView.TEMPLATE_STR, pyview=view)

        assert "No memory has been written yet" in html
        assert "Every node is current" in html


class TestNodeTemplate(_TreeTest):
    def _view(self, node):
        view = MemoryNodeView.__new__(MemoryNodeView)
        view._node = node
        view.message = ""
        view.message_ok = True
        view.uid = "pvtest"
        view._queued_cache = {}
        return view

    def test_renders_facts_directives_proposals_and_sources(self):
        inventory = self._inventory()
        agent = next(node for node in inventory.nodes if node.kind == "agent")

        html = _render(MemoryNodeView.TEMPLATE_STR, pyview=self._view(agent))

        assert "The agent remembers things." in html
        assert "Check the queue before dispatching." in html
        assert "Consider a skill for this procedure." in html
        assert "Fix the transient settings override." in html
        assert "File as backlog" in html
        assert "as of the last memory walk" in html
        assert "Changed" in html and "Missing" in html
        assert "Already filed" not in html

    def test_legacy_playbook_is_called_out(self):
        inventory = self._inventory()
        scope = next(node for node in inventory.nodes if node.kind == "scope")

        html = _render(MemoryNodeView.TEMPLATE_STR, pyview=self._view(scope))

        assert "Legacy prose reflection" in html
        assert "Nothing is injected from it" in html

    def test_filed_proposal_is_not_offered_again(self):
        inventory = self._inventory()
        agent = next(node for node in inventory.nodes if node.kind == "agent")
        queue_proposals(unique_proposals(inventory.nodes))

        view = self._view(agent)
        view._queued_cache = queued_work_items()
        html = _render(MemoryNodeView.TEMPLATE_STR, pyview=view)

        assert "Already filed" in html
        assert "File all" not in html


class TestImprovementsTemplate(_TreeTest):
    def test_lists_proposals_with_filters_and_actions(self):
        view = MemoryImprovementsView.__new__(MemoryImprovementsView)
        view.root_view = SimpleNamespace(sidebar=None)
        view._inventory = self._inventory()
        view.message = ""
        view.message_ok = True
        view._queued_cache = {}
        view.kind_filter = ""
        view.status_filter = ""
        view.scope_filter = ""
        view.search = ""
        view.hide_queued = False

        html = _render(MemoryImprovementsView.TEMPLATE_STR, pyview=view)

        assert "Fix the transient settings override." in html
        assert 'value="harness"' in html
        assert "File as backlog" in html
        assert "File visible" in html
        assert "What filing does" in html
        assert "backlog" in html

    def test_hide_queued_removes_the_row(self):
        inventory = self._inventory()
        queue_proposals(unique_proposals(inventory.nodes))

        view = MemoryImprovementsView.__new__(MemoryImprovementsView)
        view.root_view = SimpleNamespace(sidebar=None)
        view._inventory = inventory
        view.message = ""
        view.message_ok = True
        view._queued_cache = queued_work_items()
        view.kind_filter = ""
        view.status_filter = ""
        view.scope_filter = ""
        view.search = ""
        view.hide_queued = True

        html = _render(MemoryImprovementsView.TEMPLATE_STR, pyview=view)

        assert "Fix the transient settings override." not in html
        assert "No proposals match these filters." in html


class TestSidebarPanelTemplate(_TreeTest):
    def test_renders_scope_tree_and_ledger_link(self):
        view = SidebarPanelMemory.__new__(SidebarPanelMemory)
        view.root_view = SimpleNamespace(
            main_panel=SimpleNamespace(selected_tab_view=None)
        )
        view._inventory = self._inventory()
        view._queued_cache = {}
        view.search = ""

        html = _render(SidebarPanelMemory.TEMPLATE_STR, pyview=view)

        assert "Memory" in html
        assert "Global" in html
        assert "Agent #7" in html
        assert "Improvement proposals" in html
        assert "1 changed" in html
        assert "pyview.open_node(" in html

    def test_search_filter_hides_non_matches(self):
        view = SidebarPanelMemory.__new__(SidebarPanelMemory)
        view.root_view = SimpleNamespace(
            main_panel=SimpleNamespace(selected_tab_view=None)
        )
        view._inventory = self._inventory()
        view._queued_cache = {}
        view.search = "task_default"

        html = _render(SidebarPanelMemory.TEMPLATE_STR, pyview=view)

        assert "Task · default" in html
        assert "Agent #7" not in html


class TestWiring(TestCase):
    def test_sidebar_registers_the_memory_panel(self):
        import inspect

        from ui.sidebar import sidebar

        source = inspect.getsource(sidebar.SidebarView.__init__)
        assert "SidebarPanelMemory" in source
        assert "memory = SidebarPanelMemory" in source

    def test_memory_nav_is_visible_in_rail_and_mobile_nav(self):
        from ui.sidebar import rail, sidebar

        rail_block = rail.RailView.TEMPLATE_STR.split('data-panel="memory"')[1].split(
            "</button>"
        )[0]
        assert 'style="display:none"' not in rail_block

        mobile_tag = sidebar.SidebarView.TEMPLATE_STR.split('data-panel="memory"')[1].split(
            ">"
        )[0]
        assert 'style="display:none"' not in mobile_tag

    def test_panel_activated_opens_the_overview(self):
        assert callable(SidebarPanelMemory.panel_activated)
        import inspect

        source = inspect.getsource(SidebarPanelMemory.panel_activated)
        assert "open_overview" in source

    def test_main_view_refreshes_the_memory_list(self):
        import inspect

        from ui.main.main_view import MainView

        assert "'memory_list'" in inspect.getsource(MainView._update_sidebar_active)

    def test_titlebar_has_memory_categories(self):
        from ui.app_view import AppTitlebar

        assert AppTitlebar.CATEGORIES["MemoryView"] == "MEMORY"
        assert AppTitlebar.CATEGORIES["MemoryNodeView"] == "MEMORY"
        assert AppTitlebar.CATEGORIES["MemoryImprovementsView"] == "MEMORY"
