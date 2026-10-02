"""Tests for the Work Items board UI (sidebar list + main board).

Split in two halves:

* pure-logic tests over :mod:`ui.main.workitems.board_data` — column order,
  scoping, action legality — which need no DOM;
* template stub-render tests that assert the views emit the *existing* Kanban
  classes from ``ui/static/css/main.css`` and nothing that was never styled,
  plus DB tests for :func:`apply_action`, which is the only write path the UI
  is allowed to use.

The action tests are the important ones: ``WorkItem.status`` is written solely
by :class:`runtime.workitems.workitem_fsm.WorkItemStateMachine`
(``docs/work-items.md`` §2.2), so a UI that writes the column directly would
break the FSM's atomic filters without any test failing otherwise.
"""
from __future__ import annotations

from types import SimpleNamespace

import re

import jinja2
from django.test import TestCase

from runtime.workitems.workitem_fsm import WorkItemStateMachine
from server.models.workitems.enums import WorkItemStatus, WorkItemVerifyStatus
from server.models.workitems.work_item import WorkItem
from ui.main.workitems.board_data import (
    HUMAN_ACTIONS,
    STATUS_COLUMNS,
    TERMINAL_STATUSES,
    actions_for,
    apply_action,
    count_by_status,
    group_by_status,
    item_row,
    status_label,
)
from ui.main.workitems.board import WorkItemsBoard
from ui.sidebar.panels.workitems import SidebarPanelWorkItem, SidebarPanelWorkItems

#: Every class the board/sidebar emit that must already exist in the stylesheet.
#: Guards the "no new UI stuff" constraint: adding a class here without a
#: matching rule in main.css is a silent visual regression.
EXISTING_KANBAN_CLASSES = {
    "main-view-header", "main-view-title-row", "main-view-title", "main-view-actions",
    "kanban-pane", "kanban-filter-stack", "kanban-check", "kanban-summary",
    "kanban-stats-grid", "kanban-stat-cell", "kanban-board-wrap", "kanban-board",
    "kanban-column", "kanban-column-head", "kanban-count", "kanban-column-body",
    "kanban-card", "kanban-card-topline", "kanban-card-id", "kanban-badge",
    "kanban-card-title", "kanban-card-body", "kanban-card-meta", "kanban-card-assignee",
    "kanban-task-preview", "kanban-task-preview-header", "kanban-task-preview-title",
    "kanban-task-preview-body", "kanban-status-actions", "kanban-empty",
    "kanban-detail-section", "kanban-detail-row", "kanban-detail-row-main",
    "kanban-detail-row-meta", "kanban-list-item", "kanban-list-status",
    "kanban-list-title", "kanban-list", "kanban-new-task-row", "kanban-readonly",
    "panel-head", "panel-head-actions", "panel-head-btn", "panel-view", "btn",
}


def _render(template_str, **context):
    env = jinja2.Environment(autoescape=True)
    return env.from_string(template_str).render(**context)


def _item(**overrides):
    """A WorkItem-ish stub for the pure helpers."""
    base = dict(
        pk=1, title="Ship the thing", body="Some detail", status=WorkItemStatus.READY,
        priority=0, project_id=None, parent_id=None, assigned_agent=None,
        requires_verification=False, verify_status=None, verify_reason="",
        verify_attempts=0, dispatch_count=0, last_outcome="", started_at=None,
        completed_at=None, created_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _board_pyview(**overrides):
    rows = overrides.pop("rows", [item_row(_item())])
    base = dict(
        scope_label="All projects", agent_options=[], agent_filter="", verify_filter="",
        show_terminal=True, only_actionable=False, columns=STATUS_COLUMNS,
        counts=count_by_status(rows), message="", message_ok=True, empty_board=False,
        grouped=group_by_status(rows), selected=rows[0] if rows else None,
        selected_id=rows[0]["id"] if rows else None, children=[],
        selected_actions=actions_for(rows[0]) if rows else [], uid="pvtest",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _panel_pyview(**overrides):
    base = dict(
        workitem_list=SimpleNamespace(render=lambda: ""), statuses=STATUS_COLUMNS,
        status_filter="", count=2, active_count=1,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestColumnDefinition:
    def test_all_seven_statuses_have_a_column(self):
        assert [value for value, _ in STATUS_COLUMNS] == [
            "backlog", "ready", "in_progress", "in_review", "blocked", "done", "cancelled",
        ]

    def test_pipeline_order_puts_backlog_first_and_terminal_last(self):
        values = [value for value, _ in STATUS_COLUMNS]
        assert values[0] == WorkItemStatus.BACKLOG
        assert set(values[-2:]) == TERMINAL_STATUSES

    def test_labels_are_humanised_not_raw(self):
        assert status_label("in_progress") == "In Progress"
        assert status_label("in_review") == "In Review"
        assert status_label("nonexistent") == "Nonexistent"

    def test_group_by_status_seeds_empty_columns(self):
        grouped = group_by_status([item_row(_item(status="ready"))])
        assert all(isinstance(v, list) for v in grouped.values())
        assert len(grouped["ready"]) == 1
        assert grouped["blocked"] == []
        assert sum(count_by_status([item_row(_item())]).values()) == 1


class TestItemRow:
    def test_maps_model_fields_without_attribute_errors(self):
        row = item_row(_item(pk=7, title="T", priority=3, status="blocked"))
        assert row["id"] == 7
        assert row["title"] == "T"
        assert row["status_label"] == "Blocked"
        assert row["priority"] == 3

    def test_assignee_read_through_fk_or_none(self):
        assert item_row(_item())["assignee"] is None
        with_agent = item_row(_item(assigned_agent=SimpleNamespace(name="Helper")))
        assert with_agent["assignee"] == "Helper"

    def test_null_verify_status_becomes_empty_string(self):
        # NULL is the "not reviewed yet" signal; the template needs a falsy str.
        assert item_row(_item(verify_status=None))["verify_status"] == ""

    def test_whitespace_only_text_is_normalised(self):
        row = item_row(_item(body="  \n ", last_outcome="  ", verify_reason=" "))
        assert row["body"] == "" and row["last_outcome"] == "" and row["verify_reason"] == ""


class TestHumanActions:
    def test_every_status_declares_actions(self):
        for value, _ in STATUS_COLUMNS:
            assert value in HUMAN_ACTIONS, value

    def test_actions_for_accepts_row_dict_and_model(self):
        assert [a["key"] for a in actions_for({"status": "backlog"})] == ["mark_ready", "cancel"]
        assert [a["key"] for a in actions_for(_item(status="backlog"))] == ["mark_ready", "cancel"]

    def test_unknown_status_has_no_actions(self):
        assert actions_for({"status": "not_a_status"}) == []

    def test_scheduler_owned_transitions_are_not_exposed(self):
        # ready->in_progress and in_progress->in_review belong to the tick.
        ready_keys = {k for k, _, _ in HUMAN_ACTIONS[WorkItemStatus.READY]}
        assert "start_dispatch" not in ready_keys
        progress_keys = {k for k, _, _ in HUMAN_ACTIONS[WorkItemStatus.IN_PROGRESS]}
        assert "begin_review" not in progress_keys

    def test_cannot_cancel_a_done_item(self):
        # cancel() only matches non-terminal states; exposing the button would
        # be a guaranteed no-op at worst and a stale-read bug at worst.
        done_keys = {k for k, _, _ in HUMAN_ACTIONS[WorkItemStatus.DONE]}
        assert done_keys == {"reopen"}

    def test_only_cancel_is_danger_flagged_in_review(self):
        by_key = {a["key"]: a for a in actions_for({"status": "in_review"})}
        assert by_key["cancel"]["danger"] is True
        assert by_key["approve"]["danger"] is False
        assert by_key["reject"]["danger"] is False


class TestApplyActionGuards(TestCase):
    """The write path, against the real DB."""

    def setUp(self):
        self.item = WorkItem.objects.create(
            title="Guard test", status=WorkItemStatus.READY,
        )

    def test_rejects_unknown_action_key(self):
        ok, message = apply_action(self.item.pk, "nuke_everything")
        assert ok is False
        assert "nuke_everything" in message
        self.item.refresh_from_db()
        assert self.item.status == WorkItemStatus.READY

    def test_rejects_action_illegal_from_current_status(self):
        # approve is only legal from in_review; from ready it must be refused.
        ok, message = apply_action(self.item.pk, "approve")
        assert ok is False
        assert "not available" in message
        self.item.refresh_from_db()
        assert self.item.status == WorkItemStatus.READY

    def test_missing_item_returns_error_not_exception(self):
        ok, message = apply_action(99999999, "mark_ready")
        assert ok is False and "not found" in message

    def test_legal_action_routes_through_fsm(self):
        ok, message = apply_action(self.item.pk, "defer", "waiting on infra")
        assert ok is True, message
        self.item.refresh_from_db()
        assert self.item.status == WorkItemStatus.BACKLOG
        assert self.item.last_outcome == "waiting on infra"

    def test_block_records_the_reason(self):
        ok, message = apply_action(self.item.pk, "block", "no agent available")
        assert ok is True, message
        self.item.refresh_from_db()
        assert self.item.status == WorkItemStatus.BLOCKED
        assert self.item.last_outcome == "no agent available"

    def test_requeue_clears_stale_verdict_and_root_task(self):
        item = WorkItem.objects.create(
            title="Stale", status=WorkItemStatus.BLOCKED,
            verify_status=WorkItemVerifyStatus.REJECTED, verify_reason="old",
        )
        ok, message = apply_action(item.pk, "mark_ready")
        assert ok is True, message
        item.refresh_from_db()
        assert item.status == WorkItemStatus.READY
        assert item.verify_status is None and item.verify_reason == ""

    def test_finish_from_in_progress_marks_verification_skipped(self):
        item = WorkItem.objects.create(title="Unverified", status=WorkItemStatus.IN_PROGRESS)
        ok, message = apply_action(item.pk, "finish", "done by hand")
        assert ok is True, message
        item.refresh_from_db()
        assert item.status == WorkItemStatus.DONE
        assert item.verify_status == WorkItemVerifyStatus.SKIPPED
        assert item.completed_at is not None

    def test_approve_from_in_review_sets_approved(self):
        item = WorkItem.objects.create(
            title="Review me", status=WorkItemStatus.IN_REVIEW, requires_verification=True,
        )
        ok, message = apply_action(item.pk, "approve", "looks right")
        assert ok is True, message
        item.refresh_from_db()
        assert item.status == WorkItemStatus.DONE
        assert item.verify_status == WorkItemVerifyStatus.APPROVED

    def test_reject_consumes_a_verify_attempt(self):
        item = WorkItem.objects.create(
            title="Review me", status=WorkItemStatus.IN_REVIEW, requires_verification=True,
        )
        ok, message = apply_action(item.pk, "reject", "not sufficient")
        assert ok is True, message
        item.refresh_from_db()
        assert item.status == WorkItemStatus.BLOCKED
        assert item.verify_status == WorkItemVerifyStatus.REJECTED
        assert item.verify_attempts == 1

    def test_reject_reports_failure_when_the_verdict_was_already_decided(self):
        # The board's legality table offers reject from in_review; a reviewer
        # may have escalated it since the render. reject_or_escalate's inner
        # reject() is guarded on the verdict being undecided, so the write
        # no-ops — and the UI must not claim it landed.
        item = WorkItem.objects.create(
            title="Review me", status=WorkItemStatus.IN_REVIEW, requires_verification=True,
            verify_status=WorkItemVerifyStatus.ESCALATED,
        )
        ok, message = apply_action(item.pk, "reject", "still not good enough")
        assert ok is False
        assert "changed state" in message
        item.refresh_from_db()
        assert item.verify_status == WorkItemVerifyStatus.ESCALATED
        assert item.status == WorkItemStatus.IN_REVIEW

    def test_resume_clears_the_verdict_for_a_fresh_attempt(self):
        item = WorkItem.objects.create(
            title="Review me", status=WorkItemStatus.IN_REVIEW, requires_verification=True,
            verify_status=WorkItemVerifyStatus.ESCALATED, verify_reason="ping",
        )
        ok, message = apply_action(item.pk, "resume")
        assert ok is True, message
        item.refresh_from_db()
        assert item.status == WorkItemStatus.IN_PROGRESS
        assert item.verify_status is None and item.verify_reason == ""

    def test_reopen_done_item_returns_it_to_in_progress(self):
        item = WorkItem.objects.create(title="Shipped", status=WorkItemStatus.DONE)
        ok, message = apply_action(item.pk, "reopen")
        assert ok is True, message
        item.refresh_from_db()
        assert item.status == WorkItemStatus.IN_PROGRESS
        assert item.completed_at is None

    def test_stale_board_cannot_overwrite_a_settled_verdict(self):
        # The board was rendered while the item sat in review; the agent
        # reviewer then approved it.  A click on the stale "Approve" button
        # must not resurrect the transition.
        item = WorkItem.objects.create(
            title="Race", status=WorkItemStatus.IN_REVIEW, requires_verification=True,
        )
        WorkItemStateMachine.approve(item.pk, "reviewer approved")
        ok, message = apply_action(item.pk, "approve", "stale click")
        assert ok is False
        item.refresh_from_db()
        assert item.status == WorkItemStatus.DONE
        assert item.verify_status == WorkItemVerifyStatus.APPROVED
        assert item.last_outcome == "reviewer approved"


class TestBoardTemplate:
    def test_renders_with_existing_kanban_classes_only(self):
        html = _render(WorkItemsBoard.TEMPLATE_STR, pyview=_board_pyview())
        for cls in ("kanban-board", "kanban-column", "kanban-card", "kanban-summary"):
            assert cls in html, cls
        assert "btn primary" in html

    def test_emits_no_unstyled_kanban_prefixed_class(self):
        html = _render(WorkItemsBoard.TEMPLATE_STR, pyview=_board_pyview())
        used = set(re.findall(r"kanban-[a-z-]+", html))
        # Every kanban-* class the template emits must exist in the stylesheet.
        with open("ui/static/css/main.css", encoding="utf-8") as handle:
            css = handle.read()
        unstyled = {c for c in used if f".{c}" not in css}
        assert not unstyled, f"classes with no CSS rule: {sorted(unstyled)}"

    def test_board_uses_the_existing_kanban_vocabulary(self):
        # Proves the board leans on the shipped stylesheet rather than
        # inventing a parallel set of names.
        html = _render(WorkItemsBoard.TEMPLATE_STR, pyview=_board_pyview())
        used = EXISTING_KANBAN_CLASSES & set(re.findall(r'[a-z][a-z0-9-]+', html))
        assert len(used) >= 20, f"only used {len(used)} of the existing classes"

    def test_all_seven_columns_render_when_terminal_shown(self):
        html = _render(WorkItemsBoard.TEMPLATE_STR, pyview=_board_pyview())
        for _, label in STATUS_COLUMNS:
            assert f"<span>{label}</span>" in html, label

    def test_card_shows_title_assignee_and_dispatch_count(self):
        rows = [item_row(_item(pk=4, title="Fix login", assigned_agent=SimpleNamespace(name="Ana")))]
        html = _render(WorkItemsBoard.TEMPLATE_STR, pyview=_board_pyview(rows=rows))
        assert "Fix login" in html
        assert "Ana" in html
        assert "dispatch(es)" in html

    def test_unassigned_card_says_so(self):
        html = _render(WorkItemsBoard.TEMPLATE_STR, pyview=_board_pyview())
        assert "Unassigned" in html

    def test_body_html_is_escaped(self):
        rows = [item_row(_item(title="<script>alert(1)</script>", body="<b>bold</b>"))]
        html = _render(WorkItemsBoard.TEMPLATE_STR, pyview=_board_pyview(rows=rows))
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_selected_card_gets_selected_class(self):
        html = _render(WorkItemsBoard.TEMPLATE_STR, pyview=_board_pyview())
        assert "kanban-card selected" in html

    def test_detail_pane_offers_only_legal_actions(self):
        rows = [item_row(_item(status=WorkItemStatus.IN_REVIEW))]
        html = _render(WorkItemsBoard.TEMPLATE_STR, pyview=_board_pyview(rows=rows))
        assert "pyview.run_action('approve'" in html
        assert "pyview.run_action('cancel'" in html
        # defer/block are ready-only, must not appear for an in_review item.
        assert "pyview.run_action('defer'" not in html
        assert "pyview.run_action('block'" not in html

    def test_action_button_passes_the_reason_field(self):
        rows = [item_row(_item(status=WorkItemStatus.READY))]
        html = _render(WorkItemsBoard.TEMPLATE_STR, pyview=_board_pyview(rows=rows))
        assert "document.getElementById('wiReason_pvtest')" in html

    def test_danger_actions_get_the_danger_class(self):
        rows = [item_row(_item(status=WorkItemStatus.BACKLOG))]
        html = _render(WorkItemsBoard.TEMPLATE_STR, pyview=_board_pyview(rows=rows))
        assert 'btn danger' in html

    def test_verify_state_surfaces_on_the_card(self):
        rows = [item_row(_item(requires_verification=True, verify_status="pending"))]
        html = _render(WorkItemsBoard.TEMPLATE_STR, pyview=_board_pyview(rows=rows))
        assert "verify: pending" in html

    def test_empty_board_message(self):
        html = _render(
            WorkItemsBoard.TEMPLATE_STR,
            pyview=_board_pyview(rows=[], empty_board=True, selected=None, selected_id=None),
        )
        assert "No work items match these filters." in html

    def test_error_message_is_styled_with_danger_colour(self):
        html = _render(
            WorkItemsBoard.TEMPLATE_STR,
            pyview=_board_pyview(message="nope", message_ok=False),
        )
        assert "var(--danger)" in html

    def test_scope_label_is_shown_as_a_badge(self):
        html = _render(
            WorkItemsBoard.TEMPLATE_STR, pyview=_board_pyview(scope_label="Website")
        )
        assert "Website" in html

    def test_children_render_when_present(self):
        children = [item_row(_item(pk=9, title="Sub-task"))]
        html = _render(WorkItemsBoard.TEMPLATE_STR, pyview=_board_pyview(children=children))
        assert "Sub-task" in html and "Sub-items" in html

    def test_readonly_note_present_on_the_detail_pane(self):
        html = _render(WorkItemsBoard.TEMPLATE_STR, pyview=_board_pyview())
        assert "dispatched and verified by the scheduler" in html


class TestSidebarPanelTemplate:
    def test_renders_list_and_summary(self):
        html = _render(SidebarPanelWorkItems.TEMPLATE_STR, pyview=_panel_pyview())
        assert "kanban-list" in html
        assert "Work Items" in html
        assert "2 item(s)" in html
        assert "1 needing a human" in html

    def test_status_filter_offers_every_column(self):
        html = _render(SidebarPanelWorkItems.TEMPLATE_STR, pyview=_panel_pyview())
        for _, label in STATUS_COLUMNS:
            assert f">{label}</option>" in html, label

    def test_search_input_uses_the_existing_new_task_row_style(self):
        html = _render(SidebarPanelWorkItems.TEMPLATE_STR, pyview=_panel_pyview())
        assert "kanban-new-task-row" in html
        assert "pyview.set_search(this.value)" in html

    def test_active_status_filter_is_marked_selected(self):
        html = _render(
            SidebarPanelWorkItems.TEMPLATE_STR, pyview=_panel_pyview(status_filter="ready")
        )
        assert '<option value="ready" selected>' in html


class TestSidebarRowView:
    def test_row_classes_are_the_styled_list_item(self):
        view = SidebarPanelWorkItem.__new__(SidebarPanelWorkItem)
        view.root_view = SimpleNamespace(main_panel=SimpleNamespace(selected_tab_view=None))
        view._subject_ref = _item(pk=3, status="ready")
        assert view.DOM_ELEMENT_CLASS == "kanban-list-item"
        assert view.title == "Ship the thing"
        assert view.status_label == "Ready"

    def test_row_titled_by_id_when_item_has_no_title(self):
        view = SidebarPanelWorkItem.__new__(SidebarPanelWorkItem)
        view.root_view = SimpleNamespace(main_panel=SimpleNamespace(selected_tab_view=None))
        view._subject_ref = _item(pk=11, title="")
        assert view.title == "Work item 11"

    def test_selected_row_highlight_tracks_the_board_selection(self):
        view = SidebarPanelWorkItem.__new__(SidebarPanelWorkItem)
        view._subject_ref = _item(pk=3)
        view.root_view = SimpleNamespace(
            main_panel=SimpleNamespace(selected_tab_view=SimpleNamespace(selected_id=3))
        )
        assert view.DOM_ELEMENT_CLASS == "kanban-list-item selected"
        view.root_view.main_panel.selected_tab_view = SimpleNamespace(selected_id=99)
        assert view.DOM_ELEMENT_CLASS == "kanban-list-item"

    def test_row_template_uses_styled_status_and_title_lines(self):
        view = SidebarPanelWorkItem.__new__(SidebarPanelWorkItem)
        view._subject_ref = _item(pk=3, status="blocked", title="Blocked thing")
        html = _render(SidebarPanelWorkItem.TEMPLATE_STR, pyview=view)
        assert "kanban-list-status" in html
        assert "kanban-list-title" in html
        assert "Blocked" in html and "Blocked thing" in html


class TestMainViewSidebarRefresh:
    def test_workitem_list_is_in_the_refreshed_attribute_tuple(self):
        import inspect

        from ui.main.main_view import MainView

        source = inspect.getsource(MainView._update_sidebar_active)
        assert "'workitem_list'" in source


class TestBoardViewFiltering(TestCase):
    """The board view's own ``_rows`` pipeline, against the real DB.

    ``_rows`` is where scoping, terminal hiding, assignee, verification and
    actionable-only filtering intersect, so it is the part most likely to
    silently drop rows.  The view is constructed with ``__new__`` because
    ``ModelView.__init__`` needs a live pyHtmlGui instance; every attribute
    the tested methods read is set explicitly below.
    """

    def _board(self, project_id=None, **attrs):
        view = WorkItemsBoard.__new__(WorkItemsBoard)
        view.root_view = SimpleNamespace(
            sidebar=SimpleNamespace(selected_project_id=project_id)
        )
        view.agent_filter = ""
        view.verify_filter = ""
        view.show_terminal = False
        view.only_actionable = False
        view.selected_id = None
        for key, value in attrs.items():
            setattr(view, key, value)
        return view

    def setUp(self):
        from server.models.project import Project

        self.project = Project.objects.create(name="Site", path="/tmp/site")
        self.other = Project.objects.create(name="Other", path="/tmp/other")
        self._make("Backlog one", WorkItemStatus.BACKLOG, project=self.project)
        self._make("Ready one", WorkItemStatus.READY, project=self.project)
        self._make("Done one", WorkItemStatus.DONE, project=self.project)
        self._make("Elsewhere", WorkItemStatus.READY, project=self.other)
        self._make("Unfiled", WorkItemStatus.BACKLOG, project=None)

    def _make(self, title, status, project=None, **extra):
        return WorkItem.objects.create(title=title, status=status, project=project, **extra)

    def _titles(self, view):
        return sorted(row["title"] for row in view._rows())

    def test_hides_terminal_states_by_default(self):
        view = self._board(project_id=self.project.pk)
        titles = self._titles(view)
        assert "Backlog one" in titles and "Ready one" in titles
        assert "Done one" not in titles

    def test_show_terminal_reveals_done(self):
        view = self._board(project_id=self.project.pk, show_terminal=True)
        assert "Done one" in self._titles(view)

    def test_all_projects_is_the_union_not_the_unfiled_inbox(self):
        view = self._board(project_id=None)
        titles = self._titles(view)
        assert {"Backlog one", "Ready one", "Elsewhere", "Unfiled"} <= set(titles)

    def test_project_scope_excludes_other_projects_and_unfiled(self):
        view = self._board(project_id=self.project.pk)
        titles = self._titles(view)
        assert "Elsewhere" not in titles
        assert "Unfiled" not in titles

    def test_agent_filter_is_exact_not_substring(self):
        from server.models.agents.agent import AgentModel

        ana = AgentModel.objects.create(name="Ana")
        ann = AgentModel.objects.create(name="Ann")
        self._make("By Ana", WorkItemStatus.BACKLOG, project=self.project, assigned_agent=ana)
        self._make("By Ann", WorkItemStatus.BACKLOG, project=self.project, assigned_agent=ann)
        view = self._board(project_id=self.project.pk, agent_filter="Ana")
        assert "By Ana" in self._titles(view)
        assert "By Ann" not in self._titles(view)

    def test_verify_filter_required(self):
        self._make("Needs check", WorkItemStatus.IN_REVIEW, project=self.project,
                   requires_verification=True)
        view = self._board(project_id=self.project.pk, verify_filter="required",
                           show_terminal=True)
        assert "Needs check" in self._titles(view)
        assert "Ready one" not in self._titles(view)

    def test_verify_filter_pending_matches_null_and_pending(self):
        self._make("Unreviewed", WorkItemStatus.IN_REVIEW, project=self.project,
                   requires_verification=True, verify_status=None)
        self._make("Awaiting", WorkItemStatus.IN_REVIEW, project=self.project,
                   requires_verification=True, verify_status=WorkItemVerifyStatus.PENDING)
        self._make("Approved", WorkItemStatus.IN_REVIEW, project=self.project,
                   requires_verification=True, verify_status=WorkItemVerifyStatus.APPROVED)
        view = self._board(project_id=self.project.pk, verify_filter="pending")
        titles = self._titles(view)
        assert "Unreviewed" in titles and "Awaiting" in titles
        assert "Approved" not in titles

    def test_only_actionable_keeps_ready_in_review_blocked(self):
        self._make("Waiting", WorkItemStatus.IN_REVIEW, project=self.project)
        self._make("Stuck", WorkItemStatus.BLOCKED, project=self.project)
        view = self._board(project_id=self.project.pk, only_actionable=True)
        titles = self._titles(view)
        assert "Waiting" in titles and "Stuck" in titles and "Ready one" in titles
        assert "Backlog one" not in titles

    def test_columns_narrow_when_terminal_hidden(self):
        view = self._board(project_id=self.project.pk)
        values = [value for value, _ in view.columns]
        assert WorkItemStatus.DONE not in values
        view.show_terminal = True
        assert WorkItemStatus.DONE in [value for value, _ in view.columns]

    def test_selected_resolves_a_row_then_reports_none_when_filtered_out(self):
        item = WorkItem.objects.get(title="Ready one")
        view = self._board(project_id=self.project.pk, selected_id=item.pk)
        assert view.selected["title"] == "Ready one"
        assert [a["key"] for a in view.selected_actions] == ["defer", "block", "cancel"]
        view.agent_filter = "Nobody"
        assert view.selected is None
        assert view.selected_actions == []

    def test_children_only_lists_direct_children(self):
        parent = WorkItem.objects.get(title="Ready one")
        child = self._make("Child", WorkItemStatus.BACKLOG, project=self.project, parent=parent)
        self._make("Grandchild", WorkItemStatus.BACKLOG, project=self.project, parent=child)
        view = self._board(project_id=self.project.pk, selected_id=parent.pk)
        titles = [c["title"] for c in view.children]
        assert titles == ["Child"]

    def test_counts_and_grouped_agree(self):
        view = self._board(project_id=self.project.pk, show_terminal=True)
        assert sum(view.counts.values()) == len(view._rows())
        assert sum(len(v) for v in view.grouped.values()) == len(view._rows())

    def test_empty_board_when_nothing_matches(self):
        view = self._board(project_id=self.project.pk, agent_filter="Nobody")
        assert view.empty_board is True

    def test_scope_label_reads_the_project_name(self):
        view = self._board(project_id=self.project.pk)
        assert view.scope_label == "Site"
        assert self._board(project_id=None).scope_label == "All projects"


class TestSidebarPanelFiltering(TestCase):
    """The sidebar panel's queryset/filter-function pair against the real DB."""

    def _panel(self, project_id=None, **attrs):
        panel = SidebarPanelWorkItems.__new__(SidebarPanelWorkItems)
        panel.root_view = SimpleNamespace(main_panel=SimpleNamespace(selected_tab_view=None))
        panel.project_id = project_id
        panel.status_filter = ""
        panel.search = ""
        for key, value in attrs.items():
            setattr(panel, key, value)
        return panel

    def setUp(self):
        from server.models.project import Project

        self.project = Project.objects.create(name="Site", path="/tmp/site")
        WorkItem.objects.create(title="Alpha task", status=WorkItemStatus.BACKLOG,
                                project=self.project)
        WorkItem.objects.create(title="Beta task", status=WorkItemStatus.READY,
                                project=self.project)

    def test_counts_reflect_the_scope(self):
        panel = self._panel(project_id=self.project.pk)
        assert panel.count == 2
        assert panel.active_count == 0

    def test_active_count_covers_review_and_blocked(self):
        WorkItem.objects.create(title="Waiting", status=WorkItemStatus.IN_REVIEW,
                                project=self.project)
        WorkItem.objects.create(title="Stuck", status=WorkItemStatus.BLOCKED,
                                project=self.project)
        assert self._panel(project_id=self.project.pk).active_count == 2

    def test_status_filter_narrows_the_queryset(self):
        panel = self._panel(project_id=self.project.pk, status_filter=WorkItemStatus.READY)
        assert [i.title for i in panel._scoped] == ["Beta task"]

    def test_search_is_case_insensitive_substring(self):
        panel = self._panel(project_id=self.project.pk, search="alpha")
        assert [i.title for i in panel._scoped] == ["Alpha task"]

    def test_status_filter_and_search_compose(self):
        """Both filters apply together — SQL is the only filter now."""
        panel = self._panel(
            project_id=self.project.pk,
            status_filter=WorkItemStatus.READY,
            search="beta",
        )
        assert [i.title for i in panel._scoped] == ["Beta task"]
        assert panel.count == 1

    def test_the_list_query_is_the_filtered_queryset(self):
        """_refresh_list must install _scoped, or filters never reach the list."""
        panel = self._panel(project_id=self.project.pk, status_filter=WorkItemStatus.READY)
        panel.workitem_list = SimpleNamespace(query=None, _recreate=lambda: None)
        panel._refresh_list()
        assert [i.title for i in panel.workitem_list.query] == ["Beta task"]


class WorkItemActionLabelTest(TestCase):
    """The direct-completion button must not claim a review happened."""

    def _item(self, **kwargs):
        from server.models.workitems.enums import WorkItemStatus
        from server.models.workitems.work_item import WorkItem

        defaults = {"title": "x", "status": WorkItemStatus.IN_PROGRESS}
        defaults.update(kwargs)
        return WorkItem.objects.create(**defaults)

    def test_finish_says_skip_review_when_verification_is_owed(self):
        from ui.main.workitems.board_data import actions_for

        labels = {a["key"]: a["label"] for a in actions_for(self._item(requires_verification=True))}
        assert labels["finish"] == "Skip review and mark done"

    def test_finish_says_mark_done_when_no_review_is_owed(self):
        from ui.main.workitems.board_data import actions_for

        labels = {a["key"]: a["label"] for a in actions_for(self._item(requires_verification=False))}
        assert labels["finish"] == "Mark done"

    def test_label_works_from_a_row_dict_too(self):
        from ui.main.workitems.board_data import actions_for

        row = {"status": WorkItemStatus.IN_PROGRESS, "requires_verification": True}
        labels = {a["key"]: a["label"] for a in actions_for(row)}
        assert labels["finish"] == "Skip review and mark done"


class WorkItemsBoardCacheTest(TestCase):
    """One board query per render, not one per template property read."""

    def _board(self):
        from ui.main.workitems.board import WorkItemsBoard

        view = WorkItemsBoard.__new__(WorkItemsBoard)
        view.root_view = SimpleNamespace(sidebar=SimpleNamespace(selected_project_id=None))
        view.agent_filter = ""
        view.verify_filter = ""
        view.show_terminal = False
        view.only_actionable = False
        view.selected_id = 1
        return view

    def setUp(self):
        from server.models.workitems.enums import WorkItemStatus
        from server.models.workitems.work_item import WorkItem

        for n in range(3):
            WorkItem.objects.create(title=f"i{n}", body="b", status=WorkItemStatus.BACKLOG)
        self.view = self._board()

    def test_repeated_property_reads_hit_the_queryset_once(self):
        from unittest import mock

        from ui.main.workitems import board as board_mod

        with mock.patch.object(
            board_mod, "scoped_queryset", wraps=board_mod.scoped_queryset
        ) as spy:
            # Every one of these reads _rows() through a different property.
            for _ in range(5):
                self.view.grouped
                self.view.counts
                self.view.selected
                self.view.selected_actions
                self.view._still_visible(1)
            assert spy.call_count == 1, f"{spy.call_count} board queries in one render"

    def test_cache_is_dropped_when_a_filter_changes(self):
        from unittest import mock

        from ui.main.workitems import board as board_mod

        with mock.patch.object(board_mod, "scoped_queryset") as spy:
            spy.return_value = []
            self.view._rows()
            self.view._rows()
            assert spy.call_count == 1
            self.view._rows_cache = None  # what update() does
            self.view._rows()
            assert spy.call_count == 2, "stale rows survived a re-render"


class WorkItemsBoardObserverTest(TestCase):
    """The board must re-render when a Celery worker moves an item."""

    def _app(self):
        from ui.model_observer import ModelObserver

        app = SimpleNamespace(model_observer=ModelObserver())
        return app

    def _board(self, app):
        from ui.main.workitems.board import WorkItemsBoard

        view = WorkItemsBoard.__new__(WorkItemsBoard)
        view.root_view = SimpleNamespace(sidebar=SimpleNamespace(selected_project_id=None))
        view.agent_filter = ""
        view.verify_filter = ""
        view.show_terminal = False
        view.only_actionable = False
        view.selected_id = None
        view._rows_cache = ["stale"]
        view._rows_signature = ("stale",)
        view._scope_label_cache = "stale"
        view.update = lambda *a, **k: None
        return view

    def test_subscribing_registers_a_work_item_watch(self):
        from server.models.workitems.work_item import WorkItem

        app = self._app()
        view = self._board(app)
        view._watch_work_items(app)
        assert len(app.model_observer._subscriptions["workitem"]) == 1

    def test_reopening_a_tab_does_not_double_subscribe(self):
        app = self._app()
        view = self._board(app)
        view._watch_work_items(app)
        view._watch_work_items(app)
        assert len(app.model_observer._subscriptions["workitem"]) == 1, "leaked a subscription"

    def test_a_model_event_clears_the_caches_and_rerenders(self):
        from server.models.workitems.work_item import WorkItem

        app = self._app()
        view = self._board(app)
        view._watch_work_items(app)
        rendered = []
        view.update = lambda *a, **k: rendered.append(1)

        # publish_model_event sends _meta.model_name (lowercase), and
        # ModelObserver.watch keys its subscriptions the same way.
        app.model_observer.dispatch("workitem", "update", 7, {"id": 7, "project": None})

        assert view._rows_cache is None, "served stale rows after a worker moved an item"
        assert view._scope_label_cache is None
        assert rendered, "no re-render"

    def test_missing_observer_leaves_the_board_usable(self):
        """A board must still render if registration fails."""
        view = self._board(SimpleNamespace())
        view._watch_work_items(SimpleNamespace())  # no model_observer attribute
        view._watch_work_items(SimpleNamespace(model_observer=None))
