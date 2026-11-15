"""Tests for session-time playbook resolution and rendering."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from django.test import TestCase

from runtime import memory_playbook


def _playbook(path: Path, directives: list[dict]) -> Path:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(
        {"schema": memory_playbook._playbook_module().PLAYBOOK_SCHEMA,
         "directives": directives},
        sort_keys=False,
    )
    path.write_text(f"---\n{body}---\n", encoding="utf-8")
    return path


class _FakeAgent:
    name = "worker"

    def __init__(self) -> None:
        self.model = SimpleNamespace(pk=34)


class _FakeScope:
    def __init__(self, name: str, agentone_dir: Path, *, workspace: bool) -> None:
        self.name = name
        self.pk = 1
        self.agentone_dir = agentone_dir.as_posix()
        if workspace:
            self.parent_project = None

    def get_agentone_dir(self) -> Path:
        return Path(self.agentone_dir)


class _FakeSession:
    def __init__(
        self,
        *,
        workspace_root: Path | None = None,
        project_root: Path | None = None,
        config: object = True,
        group_key: str = "memory:test",
        skills: dict[str, str] | None = None,
    ) -> None:
        self._config = config
        self.group_key = group_key
        self.agent = _FakeAgent()
        self.workspace = (
            _FakeScope("ws", workspace_root, workspace=True)
            if workspace_root is not None
            else None
        )
        self.project = (
            _FakeScope("proj", project_root, workspace=False)
            if project_root is not None
            else None
        )
        self._skills = dict(skills or {})

    def _get_session_setting(self, name: str):
        assert name == "memory_playbook"
        return self._config

    def get_project(self):
        return self.project

    @property
    def allowedSkillNames(self):
        return list(self._skills)

    def get_skill(self, name: str):
        return SimpleNamespace(description=self._skills.get(name, ""))


@pytest.fixture()
def roots(tmp_path, monkeypatch):
    workspace = tmp_path / "ws-agentone"
    project = tmp_path / "proj-agentone"
    global_root = tmp_path / "global-memory"
    monkeypatch.setattr(memory_playbook, "_user_memory_root", lambda: global_root)
    return SimpleNamespace(workspace=workspace, project=project, global_=global_root)


def _session(roots, **kw) -> _FakeSession:
    return _FakeSession(
        workspace_root=roots.workspace, project_root=roots.project, **kw
    )


def _task_playbook(roots, directives, group_key="memory:test") -> Path:
    return _playbook(
        roots.workspace
        / "memory"
        / "agents"
        / "34"
        / "tasks"
        / f"task_{group_key}"
        / "reflection.md",
        directives,
    )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def test_playbook_is_off_by_default(roots):
    session = _session(roots, config=None)
    _task_playbook(roots, [{"rule": "Do the thing.", "status": "active", "support": 2}])

    assert memory_playbook.is_enabled(session) is False
    assert memory_playbook.render(session) is None


def test_boolean_and_mapping_config_are_normalized(roots):
    assert memory_playbook.is_enabled(_session(roots, config=True)) is True
    assert memory_playbook.is_enabled(_session(roots, config=False)) is False
    cfg = memory_playbook.get_config(
        _session(roots, config={"enabled": True, "maxDirectives": 3})
    )
    assert cfg["enabled"] is True
    assert cfg["maxDirectives"] == 3
    assert cfg["maxChars"] == memory_playbook.DEFAULTS["maxChars"]


def test_manifest_block_validation():
    assert memory_playbook.validate_memory_playbook_block(True) == {"enabled": True}
    assert memory_playbook.validate_memory_playbook_block(
        {"enabled": True, "maxDirectives": 5, "includeSkills": False}
    ) == {"enabled": True, "maxDirectives": 5, "includeSkills": False}
    with pytest.raises(ValueError):
        memory_playbook.validate_memory_playbook_block("yes")
    with pytest.raises(ValueError):
        memory_playbook.validate_memory_playbook_block({"maxDirectives": -1})
    with pytest.raises(ValueError):
        memory_playbook.validate_memory_playbook_block({"nope": 1})


# ---------------------------------------------------------------------------
# Resolution and precedence
# ---------------------------------------------------------------------------


def test_task_playbook_wins_over_identical_scope_directive(roots):
    _task_playbook(
        roots,
        [
            {
                "rule": "Stop after two empty dispatches.",
                "trigger": "running a memory tick",
                "status": "active",
                "support": 2,
            }
        ],
    )
    _playbook(
        roots.global_ / "reflection.md",
        [
            {
                "rule": "stop after two empty dispatches",
                "status": "active",
                "support": 2,
            }
        ],
    )

    directives = memory_playbook.collect(_session(roots))

    assert len(directives) == 1
    assert directives[0]["_layer"] == "task"
    assert directives[0]["trigger"] == "running a memory tick"


def test_agent_and_scope_playbooks_are_all_considered(roots):
    _playbook(
        roots.workspace / "memory" / "agents" / "34" / "reflection.md",
        [{"rule": "Agent rule.", "status": "active", "support": 1}],
    )
    _playbook(
        roots.global_ / "reflection.md",
        [{"rule": "Global rule.", "status": "active", "support": 1}],
    )

    rules = [d["rule"] for d in memory_playbook.collect(_session(roots))]

    assert rules == ["Agent rule.", "Global rule."]


def test_retired_harness_and_memory_directives_are_not_injected(roots):
    _task_playbook(
        roots,
        [
            {"rule": "Retired rule.", "status": "retired"},
            {"rule": "Harness fix.", "routing": "harness", "status": "active", "support": 1},
            {"rule": "A fact.", "routing": "memory", "status": "active", "support": 1},
            {"rule": "Keep me.", "status": "active", "support": 1},
        ],
    )

    rules = [d["rule"] for d in memory_playbook.collect(_session(roots))]

    assert rules == ["Keep me."]


def test_candidates_are_opt_in(roots):
    _task_playbook(
        roots,
        [{"rule": "Unproven idea.", "status": "candidate"}],
    )

    assert memory_playbook.collect(_session(roots)) == []
    opted_in = _session(roots, config={"enabled": True, "includeCandidates": True})
    assert len(memory_playbook.collect(opted_in)) == 1


def test_scope_roots_dedupe_a_workspace_inside_its_project(roots):
    session = _session(roots)
    session.workspace = _FakeScope("shared", roots.project, workspace=True)
    session.project = _FakeScope("proj", roots.project, workspace=False)

    kinds = [kind for kind, _label, _root in memory_playbook.scope_roots(session)]

    assert kinds == ["workspace", "global"]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def test_render_respects_directive_cap_and_reports_omissions(roots):
    _task_playbook(
        roots,
        [
            {"rule": f"Rule {index}.", "status": "active", "support": 1}
            for index in range(5)
        ],
    )
    session = _session(roots, config={"enabled": True, "maxDirectives": 2})

    text = memory_playbook.render(session)

    assert text.count("- Rule ") == 2
    assert "+3 more directive" in text


def test_render_respects_char_budget(roots):
    _task_playbook(
        roots,
        [{"rule": "x" * 500, "status": "active", "support": 1}],
    )
    session = _session(roots, config={"enabled": True, "maxChars": 120})

    assert memory_playbook.render(session) is None


def test_render_includes_skill_catalog(roots):
    session = _session(
        roots,
        skills={"memory-tick-cycle": "Run a complete memory tick."},
    )

    text = memory_playbook.render(session)

    assert 'load_skill("<name>")' in text
    assert "memory-tick-cycle — Run a complete memory tick." in text


def test_render_omits_skill_catalog_when_disabled(roots):
    session = _session(
        roots,
        config={"enabled": True, "includeSkills": False},
        skills={"memory-tick-cycle": "Run a complete memory tick."},
    )

    assert memory_playbook.render(session) is None


def test_render_includes_capability_pointer(roots):
    _task_playbook(
        roots,
        [
            {
                "rule": "Follow the tick procedure.",
                "status": "active",
                "support": 1,
                "routing": "skill",
                "capability": "memory-tick-cycle",
            }
        ],
    )

    text = memory_playbook.render(_session(roots))

    assert "[use: memory-tick-cycle]" in text


def test_payload_reports_candidates(roots):
    _task_playbook(roots, [{"rule": "Rule.", "status": "active", "support": 1}])

    data = memory_playbook.payload(_session(roots))

    assert data["enabled"] is True
    assert any(item["exists"] for item in data["candidates"])
    assert data["directives"][0]["source"].startswith("task (")


# ---------------------------------------------------------------------------
# Bootstrap integration
# ---------------------------------------------------------------------------


class MemoryPlaybookBootstrapTest(TestCase):
    def setUp(self):
        import tempfile

        from runtime import guidance_files

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

        from runtime import memory_playbook as playbook_module

        self._old_user_root = playbook_module._user_memory_root
        playbook_module._user_memory_root = lambda: self.root / "global-memory"
        self.addCleanup(
            setattr, playbook_module, "_user_memory_root", self._old_user_root
        )

        from server.models.agents.agent import AgentModel
        from server.models.agents.agent_version import AgentVersionModel
        from server.models.content import GenericContent
        from server.models.sessions.session import SessionModel
        from server.models.sessions.session_version import SessionVersionModel
        from server.models.settings import SettingsModel
        from server.models.workspace import WorkspaceModel

        settings = SettingsModel.objects.create(
            session_bootstrap=GenericContent.from_text("workspace: {{workspace_dir}}"),
            memory_playbook={"enabled": True},
        )
        self.agent = AgentModel.objects.create(name="playbook-bootstrap-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent, agent_settings=settings
        )
        AgentModel.objects.filter(pk=self.agent.pk).update(
            latest_agent_version=self.av
        )
        self.workspace = WorkspaceModel.objects.create(
            name="playbook-ws",
            path=self.tmp.name,
            agentone_dir=(self.root / "agentone").as_posix(),
        )
        self.session_model = SessionModel.objects.create(name="playbook-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session_model,
            agent=self.agent,
            pinned_agent_version=self.av,
            workspace=self.workspace,
            version_number=1,
        )
        SessionModel.objects.filter(pk=self.session_model.pk).update(
            latest_session_version=self.sv
        )
        self.session_model.refresh_from_db()

        from runtime.session.session import Session

        self.runtime = Session(session_model=self.session_model)
        guidance_files.clear_guidance_cache(self.session_model.pk)
        self.addCleanup(
            guidance_files.clear_guidance_cache, self.session_model.pk
        )

    def _write_task_playbook(self):
        path = (
            self.root
            / "agentone"
            / "memory"
            / "agents"
            / str(self.agent.pk)
            / "tasks"
            / "task_test"
            / "reflection.md"
        )
        _playbook(
            path,
            [
                {
                    "rule": "Stop after two empty dispatches.",
                    "status": "active",
                    "support": 2,
                }
            ],
        )

    def _bootstrap_bodies(self):
        from server.models.enums.message_enums import (
            MessageContentType,
            MessagePartType,
            MessageRole,
        )
        from server.models.message import Message, MessagePart

        message = Message.objects.create(
            session=self.sv.session,
            session_version=self.sv,
            role=MessageRole.USER,
        )
        MessagePart.objects.create(
            message=message,
            type=MessagePartType.MESSAGE,
            content=GenericContent_from_text("hello"),
            content_type=MessageContentType.TEXT,
        )
        from runtime.session_bootstrap import ensure_session_bootstrap

        created = ensure_session_bootstrap(self.runtime, message)
        return [
            str(part.content.get())
            for item in created
            for part in item.parts.order_by("pk")
        ]

    def test_playbook_is_pinned_with_the_bootstrap(self):
        self.runtime.set_group_key("test")
        self._write_task_playbook()

        bodies = self._bootstrap_bodies()

        playbook_text = next(
            body for body in bodies if body.startswith("[Memory playbook")
        )
        assert "Stop after two empty dispatches." in playbook_text

    def test_no_playbook_message_when_no_directives_exist(self):
        self.runtime.set_group_key("test")

        bodies = self._bootstrap_bodies()

        assert not any(body.startswith("[Memory playbook") for body in bodies)


def GenericContent_from_text(text: str):
    from server.models.content import GenericContent

    return GenericContent.from_text(text)
