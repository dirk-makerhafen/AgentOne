"""Tests for the session activity lifecycle:

- a subsession that calls ``final_result`` becomes inactive
- sending a message to an inactive session reactivates it + stamps last_active_at
- the sidebar shows active + recently-active subsessions (capped)
- ``list_subsessions`` shows active + recently-ended subsessions
"""
import importlib.util
from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone

from runtime.session.session import Session
from server.models.agents.agent import AgentModel
from server.models.enums.message_enums import MessageRole
from server.models.enums.session_enums import SessionType
from server.models.message import Message
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel

_ROOT = Path(__file__).resolve().parents[2]


def _load_script(relpath: str):
    """Load a manifest script module the same way registry/loader does."""
    spec = importlib.util.spec_from_file_location(
        relpath.replace("/", "_").replace(".", "_"),
        _ROOT / relpath,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _make_session(name, *, parent=None, agent=None, is_active=True, last_active_at=None, is_archived=False, session_type=SessionType.SESSION):
    if agent is None:
        agent = AgentModel.objects.create(name=f"agent-{name}")
        from server.models.agents.agent_version import AgentVersionModel
        from server.models.settings import SettingsModel
        settings = SettingsModel.objects.create()
        av = AgentVersionModel.objects.create(agent=agent, agent_settings=settings)
        AgentModel.objects.filter(pk=agent.pk).update(latest_agent_version=av)
        agent.refresh_from_db()
    session = SessionModel.objects.create(
        name=name,
        parent_session=parent,
        is_active=is_active,
        last_active_at=last_active_at,
        is_archived=is_archived,
        session_type=session_type,
    )
    sv = SessionVersionModel.objects.create(session=session, agent=agent)
    session.latest_session_version = sv
    session.save()
    return session


def _add_user_message(session, sv, created_at):
    msg = Message.objects.create(
        session=session,
        session_version=sv,
        role=MessageRole.USER,
    )
    Message.objects.filter(pk=msg.pk).update(created_at=created_at)
    return msg


@pytest.mark.django_db
class TestSessionActivation:
    def test_message_reactivates_inactive_session(self):
        session = _make_session("child", is_active=False)
        assert session.is_active is False
        session.get_runtime().set_is_active(True)
        session.refresh_from_db()
        assert session.is_active is True
        assert session.last_active_at is not None

    def test_message_stamps_last_active_at_on_active_session(self):
        session = _make_session("child")
        session.get_runtime().set_is_active(True)
        session.refresh_from_db()
        assert session.last_active_at is not None


@pytest.mark.django_db
class TestFinalResultDeactivatesSubsession:
    def test_final_result_deactivates_subsession(self):
        decide_next_step = _load_script(".agentone/scripts/core/decide_next_step.py").decide_next_step
        parent = _make_session("parent")
        child = _make_session("child", parent=parent, session_type=SessionType.SUBTASK_FORK)
        rt = child.get_runtime()
        sv = rt.get_version_model()
        msg = Message.objects.create(session=child, session_version=sv, role=MessageRole.ASSISTANT)

        result = decide_next_step(rt, response=None, parts=[], message=msg, has_final_result=True)
        assert result == msg
        child.refresh_from_db()
        assert child.is_active is False
        assert child.last_active_at is not None

    def test_final_result_keeps_main_session_active(self):
        decide_next_step = _load_script(".agentone/scripts/core/decide_next_step.py").decide_next_step
        session = _make_session("main")
        rt = session.get_runtime()
        sv = rt.get_version_model()
        msg = Message.objects.create(session=session, session_version=sv, role=MessageRole.ASSISTANT)

        decide_next_step(rt, response=None, parts=[], message=msg, has_final_result=True)
        session.refresh_from_db()
        assert session.is_active is True

    def test_final_result_reactivates_then_deactivates(self):
        """final_result on a subsession beats any prior reactivation."""
        decide_next_step = _load_script(".agentone/scripts/core/decide_next_step.py").decide_next_step
        parent = _make_session("parent")
        child = _make_session("child", parent=parent, is_active=False, session_type=SessionType.SUBTASK_FORK)
        rt = child.get_runtime()
        rt.set_is_active(True)
        child.refresh_from_db()
        assert child.is_active is True

        sv = rt.get_version_model()
        msg = Message.objects.create(session=child, session_version=sv, role=MessageRole.ASSISTANT)
        decide_next_step(rt, response=None, parts=[], message=msg, has_final_result=True)
        child.refresh_from_db()
        assert child.is_active is False


@pytest.mark.django_db
class TestListSubsessions:
    def _parent_with_messages(self, times):
        parent = _make_session("parent")
        rt = parent.get_runtime()
        sv = rt.get_version_model()
        for t in times:
            _add_user_message(parent, sv, t)
        return parent, rt

    def test_shows_active_and_recent_only(self):
        list_subsessions = _load_script(".agentone/scripts/subagents/list_subsessions.py").list_subsessions
        now = timezone.now()
        parent, rt = self._parent_with_messages([now - timedelta(hours=2), now])

        active = _make_session("active-child", parent=parent, is_active=True)
        recent = _make_session("recent-child", parent=parent, is_active=False, last_active_at=now - timedelta(minutes=5))
        old = _make_session("old-child", parent=parent, is_active=False, last_active_at=now - timedelta(days=1))

        result = list_subsessions(rt)
        names = {s["session_name"] for s in result["subsessions"]}
        assert "active-child" in names
        assert "recent-child" in names
        assert "old-child" not in names
        statuses = {s["session_name"]: s["status"] for s in result["subsessions"]}
        assert statuses["active-child"] == "active"
        assert statuses["recent-child"] == "idle"

    def test_recently_ended_drops_out_after_few_turns(self):
        list_subsessions = _load_script(".agentone/scripts/subagents/list_subsessions.py").list_subsessions
        now = timezone.now()
        t1 = now - timedelta(hours=2)
        t2 = now - timedelta(hours=1)
        t3 = now - timedelta(minutes=30)
        parent, rt = self._parent_with_messages([t1, t2, t3])
        sv = rt.get_version_model()

        finished = _make_session("done-child", parent=parent, is_active=False, last_active_at=t2)
        assert any(s["session_name"] == "done-child" for s in list_subsessions(rt)["subsessions"])

        _add_user_message(parent, sv, now - timedelta(minutes=20))
        _add_user_message(parent, sv, now)
        assert not any(s["session_name"] == "done-child" for s in list_subsessions(rt)["subsessions"])

    def test_no_user_messages_shows_active_only(self):
        list_subsessions = _load_script(".agentone/scripts/subagents/list_subsessions.py").list_subsessions
        parent = _make_session("parent")
        _make_session("active-child", parent=parent, is_active=True)
        _make_session("idle-child", parent=parent, is_active=False, last_active_at=timezone.now())

        result = list_subsessions(parent.get_runtime())
        names = {s["session_name"] for s in result["subsessions"]}
        assert names == {"active-child"}


@pytest.mark.django_db
class TestSidebarVisibleChildren:
    def _visible(self, session, **kwargs):
        from ui.sidebar.panels.chats import visible_child_sessions
        return visible_child_sessions(session, **kwargs)

    def test_active_plus_recent_inactive(self):
        parent = _make_session("parent")
        now = timezone.now()
        active = _make_session("a", parent=parent)
        recent = _make_session("b", parent=parent, is_active=False, last_active_at=now - timedelta(minutes=5))
        old = _make_session("c", parent=parent, is_active=False, last_active_at=now - timedelta(hours=2))

        names = {c.name for c in self._visible(parent)}
        assert names == {"a", "b"}

    def test_inactive_capped(self):
        parent = _make_session("parent")
        now = timezone.now()
        active = _make_session("a", parent=parent)
        for i in range(8):
            _make_session(
                f"recent-{i}",
                parent=parent,
                is_active=False,
                last_active_at=now - timedelta(minutes=1 + i),
            )

        visible = self._visible(parent)
        inactive = [c for c in visible if not c.is_active]
        assert active.name in {c.name for c in visible}
        assert len(inactive) == 5
        assert len(visible) == 6

    def test_window_parameter_widens(self):
        parent = _make_session("parent")
        now = timezone.now()
        _make_session("b", parent=parent, is_active=False, last_active_at=now - timedelta(hours=2))
        names = {c.name for c in self._visible(parent, window=timedelta(hours=3))}
        assert names == {"b"}

    def test_archived_child_hidden_by_default(self):
        parent = _make_session("parent")
        now = timezone.now()
        active = _make_session("active", parent=parent)
        _make_session(
            "archived", parent=parent, is_active=False,
            last_active_at=now, is_archived=True,
        )

        visible = self._visible(parent)
        assert active.name in {c.name for c in visible}
        assert "archived" not in {c.name for c in visible}

    def test_archived_child_shown_when_include_archived(self):
        parent = _make_session("parent")
        now = timezone.now()
        active = _make_session("active", parent=parent)
        archived = _make_session(
            "archived", parent=parent, is_active=False,
            last_active_at=now, is_archived=True,
        )

        visible = self._visible(parent, include_archived=True)
        names = {c.name for c in visible}
        assert active.name in names
        assert archived.name in names
