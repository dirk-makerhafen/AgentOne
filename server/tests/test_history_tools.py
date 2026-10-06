"""Tests for the own-history tools (Phase 1: search + inspect)."""

from __future__ import annotations

import os
import sys

from django.test import TestCase

from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.enums.message_enums import MessageContentType, MessageRole
from server.models.enums.task_enums import (
    TaskCallStatus,
    TaskCallStatusDetail,
    TaskRunStatus,
    TaskType,
)
from server.models.message import Message
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_run import AgentTaskRun
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion
from server.models.tasks.task_instance import TaskInstance

HISTORY_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".agentone", "scripts", "history")
)
if HISTORY_DIR not in sys.path:
    sys.path.insert(0, HISTORY_DIR)

from inspect_history_item import inspect_history_item
from search_own_history import search_own_history

CALL_KWARGS = {
    "requires_approval": False,
    "max_subtask_errors": 0,
    "max_subtask_error_rate": 0,
    "limit_subtask_parallel_runs": 0,
    "limit_per_instance_parallel_runs": 0,
    "max_retries": 0,
    "retry_delay": 0,
    "retry_requires_approval": False,
}


class HistoryToolsTest(TestCase):
    def setUp(self):
        self.agent = AgentModel.objects.create(name="hist-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent, agent_settings=SettingsModel.objects.create()
        )
        self.session = self._make_session("hist-session", parent=None)
        self.rt = self.session.get_runtime()

    def _make_session(self, name, parent):
        s = SessionModel.objects.create(name=name, parent_session=parent)
        sv = SessionVersionModel.objects.create(
            session=s, agent=self.agent, pinned_agent_version=self.av
        )
        SessionModel.objects.filter(pk=s.pk).update(latest_session_version=sv)
        s.refresh_from_db()
        return s

    def _msg(self, session, text, role=MessageRole.USER, part_type="message", **kw):
        sv = session.latest_session_version
        msg = Message.objects.create(session=session, session_version=sv, role=role, **kw)
        msg.add_part(type=part_type, content_type=MessageContentType.TEXT, content=text)
        return msg

    def _tool_message(self, session, tool_name, result):
        td = TaskDefinition.objects.create(name=tool_name)
        tdv = TaskDefinitionVersion.objects.create(
            task_definition=td, description="t", function_schema={}, task_type=TaskType.TOOL
        )
        TaskDefinition.objects.filter(pk=td.pk).update(latest_task_version=tdv)
        ti = TaskInstance.objects.create(
            task_definition_version=tdv,
            session=session,
            session_version=session.latest_session_version,
            **CALL_KWARGS,
        )
        call = AgentTaskCall.objects.create(
            task_instance=ti,
            task_definition=td,
            task_definition_version=tdv,
            session=session,
            session_version=session.latest_session_version,
            carguments_json={"q": "x"},
            status=TaskCallStatus.ENDED,
            status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
            **CALL_KWARGS,
        )
        run = AgentTaskRun.objects.create(
            agent_task_call=call,
            task_instance=ti,
            task_definition_version=tdv,
            session=session,
            session_version=session.latest_session_version,
            status=TaskRunStatus.SUCCESS,
            result_json=result,
            requires_approval=False,
            max_subtask_errors=0,
            max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=0,
        )
        AgentTaskCall.objects.filter(pk=call.pk).update(taskcall_result_run=run)
        call.refresh_from_db()
        msg = Message.objects.create(
            session=session, session_version=session.latest_session_version, role=MessageRole.ASSISTANT
        )
        msg.add_part(
            type="toolcall", content_type=MessageContentType.TEXT, content="called", tool_call=call
        )
        return call, msg

    # -- search ---------------------------------------------------------

    def test_search_finds_own_text_with_preview(self):
        self._msg(self.session, "the lighthouse keeps flashing at midnight")
        self._msg(self.session, "unrelated weather report")
        out = search_own_history(self.rt, text="lighthouse")
        self.assertNotIn("error", out)
        self.assertEqual(out["total_count"], 1)
        self.assertEqual(len(out["results"]), 1)
        self.assertIn("lighthouse", out["results"][0]["preview"])
        self.assertFalse(out["has_more"])

    def test_search_empty_text_returns_all_own(self):
        self._msg(self.session, "alpha")
        self._msg(self.session, "beta")
        out = search_own_history(self.rt)
        self.assertEqual(out["total_count"], 2)

    def test_search_isolated_from_sibling_by_default(self):
        sibling = self._make_session("sibling", parent=None)
        self._msg(sibling, "sibling secret lighthouse")
        out = search_own_history(self.rt, text="lighthouse")
        self.assertEqual(out["total_count"], 0)

    def test_search_child_only_with_opt_in(self):
        child = self._make_session("child", parent=self.session)
        self._msg(child, "child lighthouse note")
        self.assertEqual(search_own_history(self.rt, text="lighthouse")["total_count"], 0)
        out = search_own_history(self.rt, text="lighthouse", include_subsessions=True)
        self.assertEqual(out["total_count"], 1)
        self.assertEqual(out["results"][0]["session_pk"], child.pk)
        self.assertIn("agent", out["results"][0])

    def test_role_filter_and_unknown_role(self):
        self._msg(self.session, "user says hi", role=MessageRole.USER)
        self._msg(self.session, "assistant replies", role=MessageRole.ASSISTANT)
        out = search_own_history(self.rt, role="assistant")
        self.assertEqual(out["total_count"], 1)
        self.assertEqual(out["results"][0]["role"], "assistant")
        self.assertIn("error", search_own_history(self.rt, role="bogus"))

    def test_part_type_filter_and_unknown(self):
        self._msg(self.session, "thinking out loud", role=MessageRole.ASSISTANT, part_type="reasoning")
        self._msg(self.session, "plain hello")
        out = search_own_history(self.rt, part_type="reasoning")
        self.assertEqual(out["total_count"], 1)
        self.assertIn("error", search_own_history(self.rt, part_type="bogus"))

    def test_tool_call_name_filter(self):
        self._tool_message(self.session, "deep_lookup", {"answer": 42})
        self._msg(self.session, "just chatting")
        out = search_own_history(self.rt, tool_call_name="deep_lookup")
        self.assertEqual(out["total_count"], 1)
        self.assertEqual(out["results"][0]["tool_call_name"], "deep_lookup")
        self.assertIn("tool_call_pk", out["results"][0])

    def test_hidden_excluded_unless_requested(self):
        self._msg(self.session, "hidden lighthouse note", hide_from_context=True)
        self.assertEqual(search_own_history(self.rt, text="lighthouse")["total_count"], 0)
        out = search_own_history(self.rt, text="lighthouse", include_hidden=True)
        self.assertEqual(out["total_count"], 1)
        self.assertTrue(out["results"][0]["hidden_from_llm"])

    def test_pagination_counts(self):
        for i in range(5):
            self._msg(self.session, f"note number {i}")
        page1 = search_own_history(self.rt, limit=2, offset=0)
        self.assertEqual(page1["total_count"], 5)
        self.assertTrue(page1["has_more"])
        self.assertEqual(page1["next_offset"], 2)
        page3 = search_own_history(self.rt, limit=2, offset=4)
        self.assertEqual(len(page3["results"]), 1)
        self.assertFalse(page3["has_more"])

    def test_preview_truncation_flag(self):
        self._msg(self.session, "x" * 2000)
        out = search_own_history(self.rt)
        self.assertTrue(out["results"][0]["preview_truncated"])
        self.assertLessEqual(len(out["results"][0]["preview"]), 600)

    def test_beyond_compaction_flagged(self):
        old = self._msg(self.session, "ancient lighthouse")
        self._msg(self.session, "summary", part_type="compaction")
        out = search_own_history(self.rt, text="ancient lighthouse")
        self.assertEqual(out["total_count"], 1)
        self.assertTrue(out["results"][0]["beyond_compaction"])
        self.assertGreaterEqual(old.pk, 1)

    def test_bad_date_and_order_rejected(self):
        self.assertIn("error", search_own_history(self.rt, date_from="not-a-date"))
        self.assertIn("error", search_own_history(self.rt, order="sideways"))

    # -- inspect --------------------------------------------------------

    def test_inspect_message_full_body(self):
        msg = self._msg(self.session, "full lighthouse story " * 10)
        out = inspect_history_item(self.rt, message_pk=msg.pk)
        self.assertEqual(out["type"], "message")
        self.assertIn("lighthouse", out["parts"][0]["body"])
        self.assertFalse(out["parts"][0]["truncated"])

    def test_inspect_rejects_outside_scope(self):
        sibling = self._make_session("sib2", parent=None)
        msg = self._msg(sibling, "sibling private")
        out = inspect_history_item(self.rt, message_pk=msg.pk)
        self.assertIn("error", out)

    def test_inspect_allows_subsession_message(self):
        child = self._make_session("child2", parent=self.session)
        msg = self._msg(child, "child detail")
        out = inspect_history_item(self.rt, message_pk=msg.pk)
        self.assertEqual(out["type"], "message")

    def test_inspect_requires_exactly_one(self):
        msg = self._msg(self.session, "hello")
        self.assertIn("error", inspect_history_item(self.rt))
        self.assertIn(
            "error", inspect_history_item(self.rt, message_pk=msg.pk, task_call_pk=999)
        )
        self.assertIn("error", inspect_history_item(self.rt, message_pk=999999))

    def test_inspect_tool_call_result_without_blocking(self):
        call, _msg = self._tool_message(self.session, "quick_math", {"answer": 42})
        out = inspect_history_item(self.rt, task_call_pk=call.pk)
        self.assertEqual(out["type"], "tool_call")
        self.assertEqual(out["task_name"], "quick_math")
        self.assertIn("42", out["result_preview"])

    def test_inspect_missing_tool_call(self):
        self.assertIn("error", inspect_history_item(self.rt, task_call_pk=999999))
