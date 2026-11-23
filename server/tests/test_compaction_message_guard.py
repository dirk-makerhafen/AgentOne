"""Session-wide message fence while a compaction fork is running.

Reactive compaction used to be a barrier only for its own turn: a sibling live
root in the same session could keep producing assistant messages between the
"Compaction started" notice and the COMPACTION marker.  The fence lives on
``SessionModel`` so every worker sees it, and only compaction/reflection
scripts may write chat messages while it is held.
"""
# Tests exercise private setup hooks directly to keep the regression tight.
# pylint: disable=protected-access
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase

from runtime.context_manager import ContextTracker
from runtime.session.compaction_guard import (
    CompactionInProgress,
    begin_compaction,
    check_message_write,
    current_root_id,
    end_compaction,
    set_compaction_call,
    try_begin_compaction,
)
from runtime.session.session import Session
from runtime.tasks.call_scheduler import CallScheduler
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.enums.message_enums import MessageRole, MessageType
from server.models.message import Message
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel
from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail, TaskType
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion
from server.models.tasks.task_instance import TaskInstance

_COMPACT_IF_NEEDED_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / ".agentone" / "agents" / "internal" / "compaction-mixin" / "scripts" / "compact_if_needed.py"
)


def _load_compact_if_needed():
    spec = importlib.util.spec_from_file_location(
        "_manifest_compact_if_needed", _COMPACT_IF_NEEDED_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_run(task_name: str, root_id: int | None = 100) -> SimpleNamespace:
    return SimpleNamespace(
        agent_task_call=SimpleNamespace(session_root_task_id=root_id),
        task_definition_version=SimpleNamespace(
            task_definition=SimpleNamespace(name=task_name)
        ),
    )


class CompactionMessageGuardTest(TestCase):
    def setUp(self):
        agent = AgentModel.objects.create(name="guard-agent")
        self.settings = SettingsModel.objects.create()
        version = AgentVersionModel.objects.create(
            agent=agent,
            agent_settings=self.settings,
        )
        self.session_model = SessionModel.objects.create(name="guard-session")
        sv = SessionVersionModel.objects.create(
            session=self.session_model,
            agent=agent,
            pinned_agent_version=version,
        )
        SessionModel.objects.filter(pk=self.session_model.pk).update(latest_session_version=sv)
        self.session_model.refresh_from_db()
        self.session = Session(session_model=self.session_model)

    def _message(self, role=MessageRole.USER, message_type=MessageType.USER_CHAT):
        return Message.objects.create(
            session=self.session_model,
            session_version=self.session_model.latest_session_version,
            role=role,
            message_type=message_type,
        )

    def test_ordinary_message_is_blocked_while_compacting(self):
        begin_compaction(self.session, root_call_id=100)

        with self.assertRaises(CompactionInProgress):
            self._message()

    def test_compact_if_needed_opens_fence_before_dispatch(self):
        SettingsModel.objects.filter(pk=self.settings.pk).update(auto_compact_max_tokens=100)
        self.settings.refresh_from_db()

        session = Session(session_model=self.session_model)
        tracked_call = self._task_call("compact_turn")
        AgentTaskCall.objects.filter(pk=tracked_call.pk).update(
            session_root_task_id=tracked_call.pk
        )
        tracked_call.refresh_from_db()
        session._current_taskrun = _fake_run(
            "ingest_assistant_message", root_id=tracked_call.pk
        )
        message = self._message()
        response = SimpleNamespace(prompt_tokens=500)
        fake_bound_task = SimpleNamespace(delay=mock.Mock(return_value=tracked_call))

        module = _load_compact_if_needed()
        with mock.patch.object(session, "get_task", return_value=fake_bound_task):
            result = module.compact_if_needed(session, response, [], message)

        assert result["compact_call"] is tracked_call
        self.session_model.refresh_from_db()
        assert self.session_model.is_compacting is True
        assert self.session_model.compacting_call_id == tracked_call.pk
        assert self.session_model.compacting_root_task_id == tracked_call.pk
        with self.assertRaises(CompactionInProgress):
            self._message()

    def test_compaction_owned_writes_are_allowed(self):
        begin_compaction(self.session, root_call_id=100)

        with ContextTracker(_fake_run("ingest_compaction")):
            marker = self._message(role=MessageRole.USER, message_type=MessageType.COMPACTION)
        with ContextTracker(_fake_run("ingest_reflection_result")):
            report = self._message(role=MessageRole.INFO, message_type=MessageType.REFLECTION)
        with ContextTracker(_fake_run("ingest_user_message")):
            started = self._message(role=MessageRole.INFO, message_type=MessageType.INFO)

        assert marker.pk and report.pk and started.pk

    def test_sibling_turn_write_is_blocked_even_with_user_message_type(self):
        begin_compaction(self.session, root_call_id=100)

        with ContextTracker(_fake_run("ingest_user_message", root_id=999)):
            with self.assertRaises(CompactionInProgress):
                self._message(role=MessageRole.INFO, message_type=MessageType.INFO)

        with ContextTracker(_fake_run("ingest_assistant_message", root_id=999)):
            with self.assertRaises(CompactionInProgress):
                self._message(role=MessageRole.ASSISTANT, message_type=MessageType.ASSISTANT_MESSAGE)

    def test_slash_compact_chain_may_record_its_own_messages(self):
        begin_compaction(self.session, root_call_id=100)

        for task_name in ("process_slashcommand", "handle_slashcommand_response"):
            with ContextTracker(_fake_run(task_name)):
                message = self._message()
                assert message.pk

    def test_fence_reopens_after_compacting_call_ends(self):
        begin_compaction(self.session, root_call_id=100, call_id=456)
        end_compaction(self.session_model.pk, call_id=456)

        message = self._message()
        assert message.pk
        self.session_model.refresh_from_db()
        assert self.session_model.is_compacting is False
        assert self.session_model.compacting_call_id is None

    def test_check_helper_reports_state(self):
        run = _fake_run("ingest_compaction")
        check_message_write(self.session_model.pk, MessageType.COMPACTION, run)

        begin_compaction(self.session, root_call_id=100)
        assert current_root_id(Session(session_model=self.session_model)) is None
        check_message_write(self.session_model.pk, MessageType.COMPACTION, run)
        with self.assertRaises(CompactionInProgress):
            check_message_write(self.session_model.pk, MessageType.USER_CHAT, None)

    def test_only_one_compactor_can_acquire_fence(self):
        assert try_begin_compaction(self.session, root_call_id=100) is True
        assert try_begin_compaction(
            Session(session_model=self.session_model), root_call_id=999
        ) is False

        self.session_model.refresh_from_db()
        assert self.session_model.is_compacting is True
        assert self.session_model.compacting_root_task_id == 100

    def test_stale_fence_is_cleared_when_tracked_call_ended(self):
        call = self._task_call(
            "compact_turn",
            status=TaskCallStatus.ENDED,
            status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
        )
        begin_compaction(self.session, root_call_id=call.pk, call_id=call.pk)

        # Message.save() consults compaction_state(), which prunes the stale flag.
        message = self._message()
        assert message.pk
        self.session_model.refresh_from_db()
        assert self.session_model.is_compacting is False

    def test_call_end_releases_only_tracked_call(self):
        tracked = self._task_call("compact_turn")
        other = self._task_call("ingest_assistant_message")
        begin_compaction(self.session, root_call_id=tracked.pk, call_id=tracked.pk)

        CallScheduler._on_taskcall_ended(other.pk, 0, TaskCallStatusDetail.ENDED_SUCCESS)
        self.session_model.refresh_from_db()
        assert self.session_model.is_compacting is True

        CallScheduler._on_taskcall_ended(tracked.pk, 0, TaskCallStatusDetail.ENDED_SUCCESS)
        self.session_model.refresh_from_db()
        assert self.session_model.is_compacting is False
        assert self.session_model.compacting_call_id is None

    def test_retry_call_retargets_release(self):
        first = self._task_call("compact_turn")
        retry = self._task_call("compact_turn")
        begin_compaction(self.session, root_call_id=first.pk, call_id=first.pk)
        set_compaction_call(self.session, retry)

        CallScheduler._on_taskcall_ended(first.pk, 0, TaskCallStatusDetail.ENDED_SUCCESS)
        self.session_model.refresh_from_db()
        assert self.session_model.compacting_call_id == retry.pk

        CallScheduler._on_taskcall_ended(retry.pk, 0, TaskCallStatusDetail.ENDED_SUCCESS)
        self.session_model.refresh_from_db()
        assert self.session_model.is_compacting is False

    def _task_call(
        self,
        name: str,
        status: TaskCallStatus = TaskCallStatus.ACTIVE,
        status_detail: TaskCallStatusDetail = TaskCallStatusDetail.ACTIVE_RUNNING,
    ) -> AgentTaskCall:
        definition = TaskDefinition.objects.create(name=name)
        version = TaskDefinitionVersion.objects.create(
            task_definition=definition,
            description=name,
            function_schema={},
            task_type=TaskType.TOOL,
        )
        task_instance = TaskInstance.objects.create(
            task_definition_version=version,
            session=self.session_model,
            session_version=self.session_model.latest_session_version,
            requires_approval=False,
            max_retries=0,
            retry_delay=0,
            retry_requires_approval=False,
            max_subtask_errors=0,
            max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=0,
        )
        return AgentTaskCall.objects.create(
            task_instance=task_instance,
            task_definition=definition,
            task_definition_version=version,
            session=self.session_model,
            session_version=self.session_model.latest_session_version,
            requires_approval=False,
            max_retries=0,
            retry_delay=0,
            retry_requires_approval=False,
            max_subtask_errors=0,
            max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=0,
            status=status,
            status_detail=status_detail,
        )
