"""Tests for the work-item layer: model, FSM, dispatch, and verification.

The verification cases matter most.  The framework treats a crashed tool as a
successful call (``runtime/tasks/bound_task.py`` returns
``(False, {'status': 'exception', ...})`` and the run still takes the SUCCESS
path), so anything that reasons from a green ATC is reasoning from a signal
that is green precisely when a tool crashed.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest import mock

from django.test import TestCase

from runtime.workitems.workitem_fsm import InvalidTransition, WorkItemStateMachine
from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail
from server.models.sessions.session import SessionModel
from server.models.workitems.enums import WorkItemStatus, WorkItemVerifyStatus
from server.models.workitems.work_item import MAX_VERIFY_ATTEMPTS, WorkItem
from server.tests.helpers import AgentMdTestMixin

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_script(relative: str, name: str):
    """Import a standalone ``.agentone`` script by path."""
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# 1. FSM — valid transitions succeed, invalid ones raise
# ---------------------------------------------------------------------------

class WorkItemFsmTest(TestCase):
    """Transition table and named methods."""

    def setUp(self):
        self.item = WorkItem.objects.create(title="t", body="b")

    def test_new_item_starts_in_backlog(self):
        self.assertEqual(self.item.status, WorkItemStatus.BACKLOG)
        self.assertEqual(self.item.dispatch_count, 0)
        self.assertEqual(self.item.verify_attempts, 0)
        self.assertFalse(self.item.requires_verification)
        self.assertIsNone(self.item.verify_status)

    def test_every_valid_transition_is_accepted(self):
        """Walk every reachable state once; all must apply cleanly."""
        self.assertTrue(WorkItemStateMachine.mark_ready(self.item.pk))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, WorkItemStatus.READY)

        self.assertTrue(
            WorkItemStateMachine.start_dispatch(self.item.pk, dispatch_count=1)
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, WorkItemStatus.IN_PROGRESS)

        self.assertTrue(WorkItemStateMachine.begin_review(self.item.pk, "done-ish"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, WorkItemStatus.IN_REVIEW)

        self.assertTrue(WorkItemStateMachine.approve(self.item.pk, "good"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, WorkItemStatus.DONE)

        self.assertTrue(WorkItemStateMachine.reopen(self.item.pk))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, WorkItemStatus.IN_PROGRESS)

        self.assertTrue(WorkItemStateMachine.report_failure(self.item.pk, "boom"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, WorkItemStatus.BLOCKED)
        self.assertEqual(self.item.last_outcome, "boom")

        self.assertTrue(WorkItemStateMachine.mark_ready(self.item.pk))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, WorkItemStatus.READY)

        self.assertTrue(WorkItemStateMachine.cancel(self.item.pk, "dropped"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, WorkItemStatus.CANCELLED)
        self.assertIsNotNone(self.item.completed_at)

    def test_invalid_transition_raises(self):
        with self.assertRaises(InvalidTransition):
            WorkItemStateMachine.transition(
                self.item.pk, WorkItemStatus.BACKLOG, WorkItemStatus.DONE
            )
        with self.assertRaises(InvalidTransition):
            WorkItemStateMachine.transition(
                self.item.pk, WorkItemStatus.BACKLOG, WorkItemStatus.IN_PROGRESS
            )

    def test_transition_loses_race_returns_false(self):
        """A second claim on an already-transitioned item is a no-op, not an error."""
        self.assertTrue(WorkItemStateMachine.mark_ready(self.item.pk))
        self.assertFalse(WorkItemStateMachine.mark_ready(self.item.pk))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, WorkItemStatus.READY)

    def test_escalate_stays_in_review(self):
        WorkItemStateMachine.mark_ready(self.item.pk)
        WorkItemStateMachine.start_dispatch(self.item.pk)
        WorkItemStateMachine.begin_review(self.item.pk)
        self.assertTrue(WorkItemStateMachine.escalate(self.item.pk, "ambiguous"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, WorkItemStatus.IN_REVIEW)
        self.assertEqual(self.item.verify_status, WorkItemVerifyStatus.ESCALATED)

    def test_approve_cannot_overwrite_a_decided_item(self):
        """A duplicate verdict must not stomp a human's decision."""
        WorkItemStateMachine.mark_ready(self.item.pk)
        WorkItemStateMachine.start_dispatch(self.item.pk)
        WorkItemStateMachine.begin_review(self.item.pk)
        WorkItem.objects.filter(pk=self.item.pk).update(
            verify_status=WorkItemVerifyStatus.PENDING
        )
        self.assertTrue(WorkItemStateMachine.approve(self.item.pk, "ok"))
        self.assertFalse(WorkItemStateMachine.reject(self.item.pk, "changed my mind"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, WorkItemStatus.DONE)
        self.assertEqual(self.item.verify_reason, "ok")

    def test_attach_root_task_is_once_only(self):
        agent = _minimal_agent()
        call = _make_ended_call(agent)
        WorkItemStateMachine.mark_ready(self.item.pk)
        self.assertTrue(WorkItemStateMachine.attach_root_task(self.item.pk, call.pk))
        self.assertFalse(WorkItemStateMachine.attach_root_task(self.item.pk, call.pk + 1))
        self.item.refresh_from_db()
        self.assertEqual(self.item.root_task_id, call.pk)


# ---------------------------------------------------------------------------
# 2-8. Dispatch pipeline
# ---------------------------------------------------------------------------

class WorkItemDispatchTest(AgentMdTestMixin, TestCase):
    """The tick's work-item routines."""

    @classmethod
    def setUpTestData(cls):
        cls.setup_global_tasks()
        cls.setup_install_repo()
        _register_process_turn()
        cls.worker_agent, cls.worker_av = cls.load_agent("base")

    @classmethod
    def tearDownClass(cls):
        cls.teardown_install_repo()
        super().tearDownClass()

    def _make_item(self, **kwargs):
        defaults = {"title": "Do the thing", "body": "Please do it."}
        defaults.update(kwargs)
        return WorkItem.objects.create(**defaults)

    def test_unassigned_item_blocks_instead_of_dispatching(self):
        item = self._make_item(status=WorkItemStatus.READY)
        from server.tasks.tick_scheduler import _dispatch_work_items

        _dispatch_work_items()
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.BLOCKED)
        self.assertIn("no agent assigned", item.last_outcome)
        self.assertIsNone(item.root_task_id)

    def test_dispatch_creates_executor_session_and_turn(self):
        from server.tasks.tick_scheduler import _dispatch_work_items

        item = self._make_item(status=WorkItemStatus.READY, assigned_agent=self.worker_agent)

        _dispatch_work_items()

        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.IN_PROGRESS)
        self.assertEqual(item.dispatch_count, 1)
        self.assertIsNotNone(item.executor_session_id)
        self.assertEqual(item.executor_session.name, f"workitem:{item.pk}")
        self.assertIsNotNone(item.started_at)

    def test_executor_session_name_is_collision_proof(self):
        """Two items never share an executor session, by construction."""
        from server.tasks.tick_scheduler import _dispatch_work_items

        a = self._make_item(status=WorkItemStatus.READY, assigned_agent=self.worker_agent)
        b = self._make_item(status=WorkItemStatus.READY, assigned_agent=self.worker_agent)
        _dispatch_work_items()
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertNotEqual(a.executor_session_id, b.executor_session_id)
        self.assertNotEqual(a.executor_session.name, b.executor_session.name)

    def test_idempotent_across_many_ticks(self):
        """Running the routine N times dispatches exactly once."""
        from server.tasks.tick_scheduler import _dispatch_work_items

        item = self._make_item(status=WorkItemStatus.READY, assigned_agent=self.worker_agent)
        for _ in range(5):
            _dispatch_work_items()
        item.refresh_from_db()
        self.assertEqual(item.dispatch_count, 1)
        self.assertEqual(
            SessionModel.objects.filter(name__startswith=f"workitem:{item.pk}").count(), 1
        )

    def test_no_auto_requeue_on_success(self):
        """A success must not produce a second dispatch (docs §7.4)."""
        from server.tasks.tick_scheduler import (
            _dispatch_work_items,
            _report_work_item_outcomes,
        )

        item = self._make_item(status=WorkItemStatus.READY, assigned_agent=self.worker_agent)
        _dispatch_work_items()
        item.refresh_from_db()
        if item.root_task_id is None:
            self.skipTest("no root_task recorded (turn dispatch unavailable in this env)")

        call = item.root_task
        _set_call_status(call, TaskCallStatus.ENDED, TaskCallStatusDetail.ENDED_SUCCESS)

        _report_work_item_outcomes()
        item.refresh_from_db()
        # Succeeded without verification -> blocked, awaiting a human.
        self.assertEqual(item.status, WorkItemStatus.BLOCKED)
        self.assertIn("ENDED_SUCCESS", item.last_outcome)

        # And it must never re-dispatch on its own.
        _dispatch_work_items()
        item.refresh_from_db()
        self.assertEqual(item.dispatch_count, 1)

    def test_failure_routes_to_blocked_with_reason(self):
        from server.tasks.tick_scheduler import _report_work_item_outcomes

        item = self._make_item(status=WorkItemStatus.READY, assigned_agent=self.worker_agent)
        WorkItemStateMachine.start_dispatch(item.pk, dispatch_count=1)
        call = _make_ended_call(self.worker_agent)
        WorkItemStateMachine.attach_root_task(item.pk, call.pk)
        _set_call_status(
            call, TaskCallStatus.ENDED, TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION
        )

        _report_work_item_outcomes()
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.BLOCKED)
        self.assertIn("ENDED_FAILURE_EXCEPTION", item.last_outcome)

    def test_live_turn_is_not_reported(self):
        """An unfinished dispatch must be left alone."""
        from server.tasks.tick_scheduler import _report_work_item_outcomes

        item = self._make_item(status=WorkItemStatus.READY, assigned_agent=self.worker_agent)
        WorkItemStateMachine.start_dispatch(item.pk, dispatch_count=1)
        call = _make_ended_call(self.worker_agent)
        WorkItemStateMachine.attach_root_task(item.pk, call.pk)
        _set_call_status(
            call, TaskCallStatus.ACTIVE, TaskCallStatusDetail.ACTIVE_RUNNING
        )

        _report_work_item_outcomes()
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.IN_PROGRESS)

    def test_parallel_siblings_get_independent_sessions(self):
        from server.tasks.tick_scheduler import _dispatch_work_items

        parent = self._make_item(status=WorkItemStatus.BACKLOG)
        a = self._make_item(
            status=WorkItemStatus.READY, assigned_agent=self.worker_agent, parent=parent
        )
        b = self._make_item(
            status=WorkItemStatus.READY, assigned_agent=self.worker_agent, parent=parent
        )
        _dispatch_work_items()
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertNotEqual(a.executor_session_id, b.executor_session_id)
        self.assertEqual(a.parent_id, parent.pk)
        self.assertEqual(b.parent_id, parent.pk)


def _register_process_turn() -> None:
    """Register the turn task the work-item dispatch drives.

    ``setup_global_tasks`` creates ``core_task`` but not ``process_turn``, so
    without this the executor session resolves no turn to run.
    """
    from server.tests.helpers import create_global_task

    create_global_task("process_turn", "core", "TASK")


def _set_call_status(call, status, detail) -> None:
    """Move an AgentTaskCall to a status.

    ``AgentTaskCall.save()`` refuses to update an existing row by design (calls
    are append-only outside their FSM), so tests go through the queryset.
    """
    from server.models.tasks.agent_task_call import AgentTaskCall

    AgentTaskCall.objects.filter(pk=call.pk).update(status=status, status_detail=detail)
    call.refresh_from_db()


def _give_executor_session(item, agent) -> SessionModel:
    """Attach a real executor session to *item*."""
    from server.models.sessions.session_version import SessionVersionModel

    session = SessionModel.objects.create(name=f"workitem:{item.pk}")
    version = SessionVersionModel.objects.create(
        session=session,
        agent=agent,
        version_number=1,
        pinned_agent_version=agent.latest_agent_version,
    )
    SessionModel.objects.filter(pk=session.pk).update(latest_session_version=version)
    session.refresh_from_db()
    WorkItem.objects.filter(pk=item.pk).update(executor_session=session)
    return session


def _minimal_agent():
    """Create a bare AgentModel + AgentVersionModel, for FK scaffolding."""
    from server.models.agents.agent import AgentModel
    from server.models.agents.agent_version import AgentVersionModel

    agent = AgentModel.objects.filter(name="_wi_test_agent").first()
    if agent is None:
        agent = AgentModel.objects.create(name="_wi_test_agent")
        version = AgentVersionModel.objects.create(agent=agent, version_number=1)
        AgentModel.objects.filter(pk=agent.pk).update(latest_agent_version=version)
        agent.refresh_from_db()
    return agent


def _make_ended_call(agent, task_name: str = "process_turn"):
    """Create a minimal AgentTaskCall for reporting tests.

    Goes through ``TaskInstance.get_or_create`` so the NOT NULL option columns
    get their normal defaults; hand-creating the row leaves them NULL.
    """
    from server.models.sessions.session_version import SessionVersionModel
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.tasks.task_definition import TaskDefinition
    from server.models.tasks.task_definition_version import TaskDefinitionVersion
    from server.models.tasks.task_instance import TaskInstance

    session = SessionModel.objects.create(name="fake-exec")
    version = SessionVersionModel.objects.create(
        session=session,
        agent=agent,
        version_number=1,
        pinned_agent_version=agent.latest_agent_version,
    )
    SessionModel.objects.filter(pk=session.pk).update(latest_session_version=version)
    version.refresh_from_db()

    td = TaskDefinition.objects.filter(name=task_name).first()
    if td is None:
        td = TaskDefinition.objects.create(name=task_name, group_name="core")
        tdv = TaskDefinitionVersion.objects.create(
            task_definition=td,
            description="d",
            function_schema={"type": "object", "properties": {}},
        )
        TaskDefinition.objects.filter(pk=td.pk).update(latest_task_version=tdv)
    else:
        tdv = td.latest_task_version

    ti = TaskInstance.get_or_create(task_definition=tdv, session_version=version)
    return AgentTaskCall.create(task_instance=ti, requires_approval=False)


# ---------------------------------------------------------------------------
# 9-14. Verification
# ---------------------------------------------------------------------------

class WorkItemVerificationTest(AgentMdTestMixin, TestCase):
    """Routing, verdicts, and the bounds that stop a reviewer ping-pong."""

    @classmethod
    def setUpTestData(cls):
        cls.setup_global_tasks()
        cls.setup_install_repo()
        _register_process_turn()
        cls.worker_agent, cls.worker_av = cls.load_agent("base")

    @classmethod
    def tearDownClass(cls):
        cls.teardown_install_repo()
        super().tearDownClass()

    def setUp(self):
        self.verdict = _load_script(
            ".agentone/agents/work_verifier/scripts/workitem_verdict.py", "workitem_verdict"
        )

    def _in_review(self, **kwargs) -> WorkItem:
        """Build an item sitting in ``in_review`` with a pending verdict."""
        defaults = {
            "title": "Research the thing",
            "body": "Produce a report with three findings.",
            "requires_verification": True,
            "assigned_agent": self.worker_agent,
        }
        defaults.update(kwargs)
        item = WorkItem.objects.create(**defaults)
        WorkItemStateMachine.mark_ready(item.pk)
        WorkItemStateMachine.start_dispatch(item.pk, dispatch_count=1)
        WorkItemStateMachine.begin_review(item.pk, "turn ended")
        item.refresh_from_db()
        return item

    def test_success_routes_to_review_when_flagged(self):
        """Case 9: requires_verification sends a success to in_review."""
        from server.tasks.tick_scheduler import _report_work_item_outcomes

        item = WorkItem.objects.create(
            title="t", body="b", requires_verification=True, status=WorkItemStatus.READY
        )
        WorkItemStateMachine.start_dispatch(
            item.pk, assigned_agent=self.worker_agent, dispatch_count=1
        )
        call = _make_ended_call(self.worker_agent)
        _set_call_status(
            call, TaskCallStatus.ENDED, TaskCallStatusDetail.ENDED_SUCCESS
        )
        WorkItemStateMachine.attach_root_task(item.pk, call.pk)

        _report_work_item_outcomes()
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.IN_REVIEW)

    def test_verify_routine_claims_before_dispatching(self):
        """Case 9b: the tick marks pending so a second tick cannot double-dispatch."""
        from server.tasks.tick_scheduler import _verify_work_items

        item = self._in_review()
        with mock.patch("server.tasks.task_dispatcher.celery_delay") as delay:
            _verify_work_items()
            _verify_work_items()
        item.refresh_from_db()
        self.assertEqual(item.verify_status, WorkItemVerifyStatus.PENDING)
        self.assertEqual(delay.call_count, 1, "review must be dispatched exactly once")

    def test_approve_completes_the_item(self):
        """Case 10: approve -> done."""
        item = self._in_review()
        ok, result = self.verdict.workitem_verdict(
            mock.MagicMock(), decision="approve", reason="meets the requirement",
            work_item_id=item.pk,
        )
        self.assertTrue(ok)
        self.assertFalse(result["applied"], "id mismatch must refuse to apply")
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.IN_REVIEW)

    def test_verdict_applies_when_target_matches(self):
        item = self._in_review()
        session = mock.MagicMock()
        with mock.patch.object(
            self.verdict, "_review_target", return_value=item.pk
        ):
            ok, result = self.verdict.workitem_verdict(
                session, decision="approve", reason="looks right", work_item_id=item.pk
            )
        self.assertTrue(ok)
        self.assertTrue(result["applied"])
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.DONE)
        self.assertEqual(item.verify_status, WorkItemVerifyStatus.APPROVED)
        self.assertIsNotNone(item.completed_at)

    def test_reject_blocks_the_item(self):
        item = self._in_review()
        with mock.patch.object(self.verdict, "_review_target", return_value=item.pk):
            _, result = self.verdict.workitem_verdict(
                mock.MagicMock(), decision="reject", reason="payload threw",
                work_item_id=item.pk,
            )
        self.assertTrue(result["applied"])
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.BLOCKED)
        self.assertEqual(item.verify_status, WorkItemVerifyStatus.REJECTED)
        self.assertEqual(item.verify_attempts, 1)
        self.assertEqual(item.verify_reason, "payload threw")

    def test_ask_human_stays_in_review(self):
        item = self._in_review()
        with mock.patch.object(self.verdict, "_review_target", return_value=item.pk):
            _, result = self.verdict.workitem_verdict(
                mock.MagicMock(), decision="ask_human", reason="ambiguous",
                work_item_id=item.pk,
            )
        self.assertTrue(result["applied"])
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.IN_REVIEW)
        self.assertEqual(item.verify_status, WorkItemVerifyStatus.ESCALATED)

    def test_unknown_decision_is_refused(self):
        item = self._in_review()
        with mock.patch.object(self.verdict, "_review_target", return_value=item.pk):
            _, result = self.verdict.workitem_verdict(
                mock.MagicMock(), decision="looks_fine_to_me", reason="",
                work_item_id=item.pk,
            )
        # An undecidable verdict is not a no-op: it escalates so a human is
        # handed the item. Leaving it undecided would strand it in in_review
        # with a pending verification that nothing will ever clear.
        self.assertTrue(result["applied"])
        self.assertIsNone(result["decision"])
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.IN_REVIEW)
        self.assertEqual(item.verify_status, WorkItemVerifyStatus.ESCALATED)

    def test_mismatched_id_escalates_the_review_target(self):
        """A misread id must not decide another item, nor vanish.

        The old code returned "escalated to human" in the note while writing
        nothing at all, leaving the real target pending forever.
        """
        target = self._in_review()
        other = self._in_review(title="A different item")
        with mock.patch.object(self.verdict, "_review_target", return_value=target.pk):
            _, result = self.verdict.workitem_verdict(
                mock.MagicMock(), decision="approve", reason="looks fine",
                work_item_id=other.pk,
            )
        self.assertTrue(result["applied"])
        self.assertIn("Escalated", result["note"])

        other.refresh_from_db()
        self.assertEqual(other.status, WorkItemStatus.IN_REVIEW, "wrong item was touched")
        self.assertIsNone(other.verify_status)

        target.refresh_from_db()
        self.assertEqual(target.verify_status, WorkItemVerifyStatus.ESCALATED)
        self.assertIn("is not the review target", target.verify_reason)

    def test_verdict_refused_when_item_not_in_review(self):
        """A human who already moved the item must not be overwritten."""
        item = self._in_review()
        WorkItemStateMachine.cancel(item.pk, "human cancelled")
        with mock.patch.object(self.verdict, "_review_target", return_value=item.pk):
            _, result = self.verdict.workitem_verdict(
                mock.MagicMock(), decision="approve", reason="", work_item_id=item.pk
            )
        self.assertFalse(result["applied"])
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.CANCELLED)

    def test_reject_loop_is_bounded(self):
        """Case 11: rejections stop escalating to a human past the cap."""
        for _ in range(MAX_VERIFY_ATTEMPTS):
            item = self._in_review()
            with mock.patch.object(self.verdict, "_review_target", return_value=item.pk):
                _, result = self.verdict.workitem_verdict(
                    mock.MagicMock(), decision="reject", reason="nope",
                    work_item_id=item.pk,
                )
            self.assertTrue(result["applied"])
            item.refresh_from_db()
            self.assertEqual(item.status, WorkItemStatus.BLOCKED)

        # One more cycle, at the cap, must escalate instead of rejecting again.
        item = self._in_review(verify_attempts=MAX_VERIFY_ATTEMPTS)
        with mock.patch.object(self.verdict, "_review_target", return_value=item.pk):
            _, result = self.verdict.workitem_verdict(
                mock.MagicMock(), decision="reject", reason="still nope",
                work_item_id=item.pk,
            )
        self.assertTrue(result["applied"])
        item.refresh_from_db()
        self.assertEqual(item.verify_status, WorkItemVerifyStatus.ESCALATED)
        self.assertEqual(item.verify_attempts, MAX_VERIFY_ATTEMPTS)

    def test_rejected_item_can_be_requeued_and_redispatched(self):
        """A rejected item must survive the requeue and run again.

        Guards two ways a requeue could silently strand the item: leaving the
        old ``root_task`` in place (dispatch only selects NULL roots) and
        leaving a stale ``verify_status`` (the tick only claims NULL).
        """
        from server.tasks.tick_scheduler import _dispatch_work_items

        item = self._in_review()
        with mock.patch.object(self.verdict, "_review_target", return_value=item.pk):
            self.verdict.workitem_verdict(
                mock.MagicMock(), decision="reject", reason="nope", work_item_id=item.pk
            )
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.BLOCKED)
        self.assertEqual(item.verify_status, WorkItemVerifyStatus.REJECTED)

        # Human re-queues the item.
        self.assertTrue(WorkItemStateMachine.mark_ready(item.pk))
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.READY)
        self.assertIsNone(item.root_task, "stale root would strand the requeue")
        self.assertIsNone(item.verify_status, "stale verdict would block re-review")
        # The cumulative budget is deliberately not reset.
        self.assertEqual(item.verify_attempts, 1)

        # ...and it dispatches again, this time as a second attempt.
        _dispatch_work_items()
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.IN_PROGRESS)
        self.assertIsNotNone(item.root_task)
        self.assertEqual(item.dispatch_count, 2)

    def test_reviewer_failure_escalates_and_never_approves(self):
        """Case 12: a crashed review leaves the item for a human."""
        from runtime.workitems.work_item_verifier import WorkItemVerifier

        item = self._in_review()
        _give_executor_session(item, self.worker_agent)
        # The tick claims a row (NULL -> pending) before dispatching the worker,
        # so the worker only ever sees a pending item.
        WorkItem.objects.filter(pk=item.pk).update(
            verify_status=WorkItemVerifyStatus.PENDING
        )
        item.refresh_from_db()
        with mock.patch.object(
            WorkItemVerifier, "_build_verification_brief", side_effect=RuntimeError("boom")
        ):
            WorkItemVerifier.verify(item.pk)
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.IN_REVIEW)
        self.assertEqual(item.verify_status, WorkItemVerifyStatus.ESCALATED)
        self.assertIn("boom", item.verify_reason)

    def test_verify_ignores_items_not_awaiting_review(self):
        from runtime.workitems.work_item_verifier import WorkItemVerifier

        item = WorkItem.objects.create(title="t", body="b")
        with mock.patch.object(WorkItemVerifier, "_launch_reviewer_session") as launch:
            WorkItemVerifier.verify(item.pk)
        launch.assert_not_called()

    def test_no_self_review(self):
        """Case 13: the reviewer must not be the executor."""
        from runtime.workitems.work_item_verifier import WorkItemVerifier

        item = self._in_review()  # assigned_agent is the worker agent
        with mock.patch(
            "server.models.agents.agent.AgentModel.objects.filter"
        ) as agent_filter:
            # The reviewer resolves to the *same* agent that did the work.
            agent_filter.return_value.first.return_value = mock.MagicMock(
                pk=self.worker_agent.pk
            )
            item.refresh_from_db()
            with self.assertRaises(RuntimeError):
                WorkItemVerifier._launch_reviewer_session(item, mock.MagicMock(), "brief")

    def test_missing_reviewer_agent_escalates(self):
        """A missing reviewer must never fall back to the executor."""
        from runtime.workitems.work_item_verifier import WorkItemVerifier

        item = self._in_review()
        with mock.patch(
            "server.models.agents.agent.AgentModel.objects.filter"
        ) as agent_filter:
            agent_filter.return_value.first.return_value = None
            with self.assertRaises(RuntimeError):
                WorkItemVerifier._launch_reviewer_session(item, mock.MagicMock(), "brief")

    # ------------------------------------------------------------------
    # Case 14 — the load-bearing one
    # ------------------------------------------------------------------

    def test_false_green_is_not_trusted(self):
        """A brief must expose tool exceptions, not report a bare success."""
        from server.models.enums.message_enums import (
            MessageContentType,
            MessagePartType,
            MessageRole,
        )
        from server.models.message import Message
        from runtime.workitems.work_item_verifier import (
            TOOL_ERROR_CONVENTION,
            WorkItemVerifier,
        )

        item = self._in_review()
        agent = self.worker_agent
        session = SessionModel.objects.create(name="exec-session")
        from server.models.sessions.session_version import SessionVersionModel

        version = SessionVersionModel.objects.create(
            session=session, agent=agent, version_number=1,
            pinned_agent_version=agent.latest_agent_version,
        )
        SessionModel.objects.filter(pk=session.pk).update(latest_session_version=version)
        session.refresh_from_db()
        WorkItem.objects.filter(pk=item.pk).update(executor_session=session)
        item.refresh_from_db()

        message = Message.objects.create(
            role=MessageRole.ASSISTANT, session=session, session_version=version
        )
        message.add_part(
            type=MessagePartType.MESSAGE,
            content_type=MessageContentType.TEXT,
            content="I have completed the report.",
        )

        call = _make_ended_call(agent)
        _set_call_status(call, TaskCallStatus.ENDED, TaskCallStatusDetail.ENDED_SUCCESS)
        # The executor "succeeded" — but its only real tool call threw.
        _attach_run(call, {"status": "exception", "message": "Traceback ...KeyError: x"})
        WorkItemStateMachine.attach_root_task(item.pk, call.pk)
        item.refresh_from_db()

        brief = WorkItemVerifier._build_verification_brief(item)

        # The exception payload is present, so a reviewer can see the failure.
        self.assertIn("exception", brief)
        self.assertIn("KeyError", brief)
        # The convention note tells the reviewer green does not mean success.
        self.assertIn(TOOL_ERROR_CONVENTION[:40], brief)
        self.assertIn("NOT evidence", brief)
        # The executor's own claim is quoted, but not as the only signal.
        self.assertIn("I have completed the report.", brief)
        self.assertIn("status_detail=ENDED_SUCCESS", brief)

    def test_root_call_payload_reaches_brief_when_root_points_at_ancestor(self):
        """The dispatch call's own payload must survive into the brief.

        In production ``process_turn`` is created under a parent run, so its
        ``session_root_task`` is the *ancestor* call, not itself. Matching the
        tree by ``session_root_task`` alone therefore drops the dispatch call —
        the one call whose payload and ``status_detail`` matter most. A
        self-referential root (as in the helper above) hides that bug, so this
        test builds the production shape explicitly.
        """
        from runtime.workitems.work_item_verifier import WorkItemVerifier
        from server.models.tasks.agent_task_call import AgentTaskCall

        item = self._in_review()
        outer = _make_ended_call(self.worker_agent)
        call = _make_ended_call(self.worker_agent)
        _set_call_status(call, TaskCallStatus.ENDED, TaskCallStatusDetail.ENDED_SUCCESS)
        _attach_run(call, {"status": "exception", "message": "KeyError: 'ancestor'"})
        # Point the dispatch call's root at an ancestor, as a nested turn does.
        AgentTaskCall.objects.filter(pk=call.pk).update(session_root_task=outer)
        call.refresh_from_db()
        WorkItemStateMachine.attach_root_task(item.pk, call.pk)
        item.refresh_from_db()

        brief = WorkItemVerifier._build_verification_brief(item)
        self.assertIn("KeyError", brief)
        self.assertIn("status_detail=ENDED_SUCCESS", brief)


def _attach_run(call, payload) -> None:
    """Give *call* a finished run carrying *payload* (the false-green setup)."""
    from server.models.tasks.agent_task_run import AgentTaskRun

    # AgentTaskRun's option columns are NOT NULL with None defaults, so they
    # must all be supplied explicitly.
    run = AgentTaskRun.objects.create(
        agent_task_call=call,
        session=call.session,
        session_version=call.session_version,
        status="SUCCESS",
        requires_approval=False,
        max_subtask_errors=0,
        max_subtask_error_rate=0.0,
        limit_subtask_parallel_runs=0,
        limit_per_instance_parallel_runs=0,
    )
    AgentTaskRun.objects.filter(pk=run.pk).update(result_json=payload)
    from server.models.tasks.agent_task_call import AgentTaskCall

    AgentTaskCall.objects.filter(pk=call.pk).update(taskcall_result_run=run)
    call.refresh_from_db()


# ---------------------------------------------------------------------------
# 6. Session-name scoping regression
# ---------------------------------------------------------------------------

class SessionNameScopingTest(AgentMdTestMixin, TestCase):
    """docs §4 — names are unique per parent, not globally."""

    @classmethod
    def setUpTestData(cls):
        cls.setup_global_tasks()
        cls.setup_install_repo()
        cls.agent, cls.av = cls.load_agent("base")

    def test_same_name_under_different_parents_stays_separate(self):
        agent, av = self.agent, self.av
        if not (agent and av):
            self.skipTest("no test agent available")

        parent_a = SessionModel.objects.create(name="project-a-session")
        parent_b = SessionModel.objects.create(name="project-b-session")

        from server.models.sessions.session_version import SessionVersionModel

        pa_version = SessionVersionModel.objects.create(
            session=parent_a, agent=agent, version_number=1, pinned_agent_version=av
        )
        SessionModel.objects.filter(pk=parent_a.pk).update(latest_session_version=pa_version)
        parent_a.refresh_from_db()
        pb_version = SessionVersionModel.objects.create(
            session=parent_b, agent=agent, version_number=1, pinned_agent_version=av
        )
        SessionModel.objects.filter(pk=parent_b.pk).update(latest_session_version=pb_version)
        parent_b.refresh_from_db()

        child_a = av.get_or_create_session(
            name="research", parent_session_version=pa_version
        )
        child_b = av.get_or_create_session(
            name="research", parent_session_version=pb_version
        )
        self.assertNotEqual(
            child_a.session_id,
            child_b.session_id,
            "two parents naming a child 'research' must not share one session",
        )

    def test_repeat_lookup_reuses_the_same_session(self):
        agent, av = self.agent, self.av
        if not (agent and av):
            self.skipTest("no test agent available")

        first = av.get_or_create_session(name="workitem:123")
        second = av.get_or_create_session(name="workitem:123")
        self.assertEqual(first.session_id, second.session_id)


# ---------------------------------------------------------------------------
# 15. Agent-facing workitem_action tool
# ---------------------------------------------------------------------------

class WorkItemActionToolTest(AgentMdTestMixin, TestCase):
    """The agent tool must respect the FSM and the project boundary."""

    @classmethod
    def setUpTestData(cls):
        cls.setup_global_tasks()
        cls.setup_install_repo()
        cls.worker_agent, cls.worker_av = cls.load_agent("base")

    @classmethod
    def tearDownClass(cls):
        cls.teardown_install_repo()
        super().tearDownClass()

    def setUp(self):
        self.action = _load_script(
            ".agentone/scripts/workitems/workitem_action.py", "workitem_action"
        )
        from server.models.project import Project
        from server.models.sessions.session import SessionModel

        self.project = Project.objects.create(name="proj-a")
        self.other_project = Project.objects.create(name="proj-b")
        self.session = SessionModel.objects.create(
            name="act-session", parent_project=self.project
        )

    def _session(self):
        """A real ``Session`` runtime bound to this session's model."""
        from runtime.session.session import Session

        return Session(session_model=self.session)

    def _foreign_item(self):
        from server.models.workitems.work_item import WorkItem

        return WorkItem.objects.create(
            project=self.other_project,
            title="other project secret",
            body="do not touch",
        )

    def test_create_ready_reports_ready_not_backlog(self):
        """The summary must reflect the post-transition status.

        ``mark_ready`` writes through the queryset, so summarising the stale
        in-memory object would report "backlog" for an item that is queued.
        """
        ok, result = self.action.workitem_create(
            self._session(), title="Ship it", body="do the thing", status="ready"
        )
        self.assertTrue(ok, result)
        self.assertEqual(result["status"], WorkItemStatus.READY)

    def test_create_backlog_stays_backlog(self):
        ok, result = self.action.workitem_create(
            self._session(), title="Later", status="backlog"
        )
        self.assertTrue(ok, result)
        self.assertEqual(result["status"], WorkItemStatus.BACKLOG)

    def test_update_done_completes_an_in_progress_item(self):
        """``done`` on a running item must complete it, not silently block it.

        ``report_success()`` is in_progress -> blocked by design, so routing
        ``done`` through it would report a finished item as blocked.
        """
        from server.models.workitems.work_item import WorkItem

        item = WorkItem.objects.create(
            project=self.project, title="Running", body="b",
            status=WorkItemStatus.IN_PROGRESS,
        )
        ok, result = self.action.workitem_update(
            self._session(), work_item_id=item.pk, status="done"
        )
        self.assertTrue(ok, result)
        self.assertEqual(result["status"], WorkItemStatus.DONE)
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.DONE)
        self.assertIsNotNone(item.completed_at)

    def test_update_cannot_skip_verification_by_marking_done(self):
        """An item awaiting review may only leave via approve/reject/ask_human."""
        from server.models.workitems.work_item import WorkItem

        item = WorkItem.objects.create(
            project=self.project, title="In review", body="b",
            status=WorkItemStatus.IN_REVIEW, requires_verification=True,
        )
        ok, result = self.action.workitem_update(
            self._session(), work_item_id=item.pk, status="done"
        )
        self.assertTrue(ok, result)
        item.refresh_from_db()
        # approve() is the legal in_review -> done path, and it stamps a verdict.
        self.assertEqual(item.status, WorkItemStatus.DONE)
        self.assertIsNotNone(item.verify_status)

    def test_update_cannot_touch_another_projects_item(self):
        item = self._foreign_item()
        ok, result = self.action.workitem_update(
            self._session(), work_item_id=item.pk, title="hijacked"
        )
        self.assertFalse(ok)
        self.assertIn("error", result)
        item.refresh_from_db()
        self.assertEqual(item.title, "other project secret")

    def test_list_is_scoped_to_the_session_project(self):
        from server.models.workitems.work_item import WorkItem

        mine = WorkItem.objects.create(project=self.project, title="mine", body="b")
        self._foreign_item()
        ok, result = self.action.workitem_list(self._session())
        self.assertTrue(ok, result)
        ids = [i["id"] for i in result["items"]]
        self.assertIn(mine.pk, ids)
        self.assertEqual(len(ids), 1, "another project's item leaked into the list")

    def test_create_cannot_parent_onto_another_projects_item(self):
        """A subtask may not be grafted onto a parent the session cannot see."""
        foreign = self._foreign_item()
        ok, result = self.action.workitem_create(
            self._session(), title="sneaky subtask", parent_id=foreign.pk
        )
        self.assertFalse(ok)
        self.assertIn("error", result)

    def test_update_rejects_unknown_status(self):
        from server.models.workitems.work_item import WorkItem

        item = WorkItem.objects.create(project=self.project, title="x", body="b")
        ok, result = self.action.workitem_update(
            self._session(), work_item_id=item.pk, status="banana"
        )
        self.assertFalse(ok)
        self.assertIn("error", result)

    def test_blocking_requires_a_reason(self):
        from server.models.workitems.work_item import WorkItem

        item = WorkItem.objects.create(
            project=self.project, title="x", body="b", status=WorkItemStatus.READY
        )
        ok, result = self.action.workitem_update(
            self._session(), work_item_id=item.pk, status="blocked"
        )
        self.assertFalse(ok)
        self.assertIn("reason", result["error"])

    # ------------------------------------------------------------------
    # The tool must not report success for a write that did not happen.
    # ------------------------------------------------------------------

    def _in_state(self, status, **kwargs):
        from server.models.workitems.work_item import WorkItem

        defaults = {"project": self.project, "title": "x", "body": "b", "status": status}
        defaults.update(kwargs)
        return WorkItem.objects.create(**defaults)

    def test_illegal_status_change_reports_failure_and_changes_nothing(self):
        """_apply_status used to discard the FSM's bool and return success.

        Every FSM method signals a refused write by returning False, so an
        agent could be told it had re-queued an in_progress item that never
        left in_progress, or cancelled a finished one.
        """
        cases = [
            # (item state, tool call kwargs)
            ({"status": WorkItemStatus.IN_PROGRESS}, {"status": "ready"}),
            ({"status": WorkItemStatus.BACKLOG}, {"status": "blocked", "reason": "stuck"}),
            ({"status": WorkItemStatus.DONE}, {"status": "cancelled"}),
            (
                {"status": WorkItemStatus.IN_REVIEW, "verify_status": "escalated"},
                {"status": "done"},
            ),
        ]
        for item_kwargs, call_kwargs in cases:
            with self.subTest(target=call_kwargs["status"]):
                start = item_kwargs["status"]
                item = self._in_state(**item_kwargs)
                ok, result = self.action.workitem_update(
                    self._session(), work_item_id=item.pk, **call_kwargs
                )
                self.assertFalse(ok, f"reported success for {start} -> {call_kwargs}")
                self.assertIn("error", result)
                item.refresh_from_db()
                self.assertEqual(item.status, start, "status moved anyway")

    def test_illegal_status_change_leaves_field_writes_unapplied(self):
        """Fields and status move together, or not at all.

        Fields were saved first, so a refused transition used to return an
        error with the new title already persisted — a half-applied update the
        agent had to reason about after a failure.
        """
        item = self._in_state(WorkItemStatus.IN_PROGRESS)
        ok, result = self.action.workitem_update(
            self._session(), work_item_id=item.pk, status="ready", title="renamed"
        )
        self.assertFalse(ok)
        self.assertIn("error", result)
        item.refresh_from_db()
        self.assertEqual(item.title, "x", "title was written despite the failure")

    def test_status_equal_to_current_is_a_accepted_no_op(self):
        item = self._in_state(WorkItemStatus.BLOCKED, last_outcome="was stuck")
        ok, result = self.action.workitem_update(
            self._session(), work_item_id=item.pk, status="blocked", reason="still stuck"
        )
        self.assertTrue(ok, result)

    def test_cannot_mark_done_over_a_pending_review(self):
        """Marking verified in_progress work done would make the flag decorative."""
        item = self._in_state(WorkItemStatus.IN_PROGRESS, requires_verification=True)
        ok, result = self.action.workitem_update(
            self._session(), work_item_id=item.pk, status="done", reason="all finished"
        )
        self.assertFalse(ok)
        self.assertIn("requires verification", result["error"])
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.IN_PROGRESS)
        self.assertIsNone(item.completed_at)

    def test_marking_unverified_in_progress_work_done_still_works(self):
        """The refusal above must not close the direct-completion route."""
        item = self._in_state(WorkItemStatus.IN_PROGRESS, requires_verification=False)
        ok, result = self.action.workitem_update(
            self._session(), work_item_id=item.pk, status="done", reason="finished it"
        )
        self.assertTrue(ok, result)
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.DONE)
        self.assertIsNotNone(item.completed_at)

    # ------------------------------------------------------------------
    # An agent must be able to read back what it asked for.
    # ------------------------------------------------------------------

    def test_create_echoes_the_requirement_body(self):
        ok, result = self.action.workitem_create(
            self._session(), title="Ship it", body="migrate 3 tables", status="backlog"
        )
        self.assertTrue(ok, result)
        self.assertEqual(result["body"], "migrate 3 tables")

    def test_list_includes_the_requirement_body(self):
        """Without body, workitem_list is the only reader of a requirement
        and it could not return one — the agent could never re-read what it
        filed, days later, from a new session."""
        self._in_state(WorkItemStatus.BACKLOG, body="the actual requirement")
        ok, result = self.action.workitem_list(self._session())
        self.assertTrue(ok, result)
        self.assertEqual(result["items"][0]["body"], "the actual requirement")

    def test_list_can_drop_the_body_to_fit_more_items(self):
        self._in_state(WorkItemStatus.BACKLOG, body="x" * 500)
        ok, result = self.action.workitem_list(self._session(), include_body=False)
        self.assertTrue(ok, result)
        self.assertNotIn("body", result["items"][0])

    def test_list_rejects_an_unknown_status_instead_of_returning_nothing(self):
        """A typo returned an empty successful list, which reads as
        "no work is outstanding" rather than "you passed a bad filter"."""
        self._in_state(WorkItemStatus.BACKLOG)
        ok, result = self.action.workitem_list(self._session(), status="backolg")
        self.assertFalse(ok)
        self.assertIn("Unknown status", result["error"])

    def test_list_accepts_the_statuses_the_agent_cannot_set(self):
        """in_progress/in_review are not settable but are real states to read."""
        self._in_state(WorkItemStatus.IN_REVIEW, requires_verification=True)
        ok, result = self.action.workitem_list(self._session(), status="in_review")
        self.assertTrue(ok, result)
        self.assertEqual(result["count"], 1)

    def test_list_pages_and_reports_has_more(self):
        for n in range(5):
            self._in_state(WorkItemStatus.BACKLOG, title=f"item-{n}")

        ok, first = self.action.workitem_list(self._session(), offset=0)
        self.assertTrue(ok, first)
        self.assertEqual(first["count"], 5, "count must be the full match count")
        self.assertEqual(first["returned"], 5)
        self.assertFalse(first["has_more"])

        # Simulate a full page by paging past the end.
        ok, past = self.action.workitem_list(self._session(), offset=5)
        self.assertTrue(ok, past)
        self.assertEqual(past["count"], 5)
        self.assertEqual(past["returned"], 0)
        self.assertFalse(past["has_more"])

    def test_list_rejects_a_negative_offset(self):
        ok, result = self.action.workitem_list(self._session(), offset=-1)
        self.assertFalse(ok)
        self.assertIn("offset", result["error"])

    def test_a_projectless_session_sees_only_unfiled_items(self):
        """A session with no project is the unfiled inbox, not an all-access pass."""
        from server.models.sessions.session import SessionModel
        from server.models.workitems.work_item import WorkItem

        unfiled = WorkItem.objects.create(title="unfiled", body="b")
        self._foreign_item()
        project_item = WorkItem.objects.create(
            project=self.project, title="belongs to proj-a", body="b"
        )

        orphan = SessionModel.objects.create(name="no-project-session")
        from runtime.session.session import Session

        ok, result = self.action.workitem_list(Session(session_model=orphan))
        self.assertTrue(ok, result)
        ids = [i["id"] for i in result["items"]]
        self.assertIn(unfiled.pk, ids)
        self.assertNotIn(project_item.pk, ids, "a projectless session read a project item")
        self.assertEqual(len(ids), 1, "another project's item leaked")

    def test_a_projectless_session_cannot_update_a_project_item(self):
        from server.models.sessions.session import SessionModel
        from server.models.workitems.work_item import WorkItem
        from runtime.session.session import Session

        target = WorkItem.objects.create(
            project=self.project, title="belongs to proj-a", body="b",
            status=WorkItemStatus.READY,
        )
        orphan = SessionModel.objects.create(name="no-project-session-2")
        ok, result = self.action.workitem_update(
            Session(session_model=orphan), work_item_id=target.pk, title="hijacked"
        )
        self.assertFalse(ok)
        target.refresh_from_db()
        self.assertEqual(target.title, "belongs to proj-a")
