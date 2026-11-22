"""Tests for parent-scoped runtime collections and assistant wiring.

Each plural collection takes explicit parent kwargs and scopes ``all()``
accordingly; ``root()`` stays unscoped for UI callers; ``list_*()``
returns wrapped singular objects; ``get_source_dir()`` is pure path
resolution (stored ``manifest_dir`` first, conventional layout fallback);
``get_assistant_session()`` spawns the bound singleton.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase

from runtime.agents.agents import Agents
from runtime.cron.crons import Cronjobs
from runtime.project.projects import Projects
from runtime.session.sessions import Sessions
from runtime.skill.skills import Skills
from runtime.workitems.workitems import Workitems
from runtime.workspace.workspaces import Workspaces
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.cron import Cronjob
from server.models.project import Project
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel
from server.models.skills.skill import SkillModel
from server.models.skills.skill_version import SkillModelVersion
from server.models.workspace import WorkspaceModel
from server.models.workitems.work_item import WorkItem
from server.tests.helpers import AgentMdTestMixin, TESTPROJECT

# pylint: disable=protected-access
# (Assistant wiring tests inspect bound runtime session state.)


def _make_project(name="p", path="/tmp/p"):
    project = Project.objects.create(name=name)
    if path:
        ws = WorkspaceModel.objects.create(
            name=f"{name} project root", path=path, parent_project=project,
        )
        Project.objects.filter(pk=project.pk).update(main_workspace=ws)
        project.refresh_from_db()
    return project


def _make_skill(name, project=None, manifest_dir=""):
    skill = SkillModel.objects.create(
        name=name, parent_project=project, manifest_dir=manifest_dir
    )
    sv = SkillModelVersion.objects.create(skill=skill)
    SkillModel.objects.filter(pk=skill.pk).update(latest_skill_version=sv)
    return skill


def _make_agent(name, project=None, manifest_dir=""):
    agent = AgentModel.objects.create(
        name=name, parent_project=project, manifest_dir=manifest_dir
    )
    av = AgentVersionModel.objects.create(
        agent=agent, agent_settings=SettingsModel.objects.create()
    )
    AgentModel.objects.filter(pk=agent.pk).update(latest_agent_version=av)
    agent.refresh_from_db()
    return agent, av


def _make_session(agent, av, name="s-parent", project=None):
    session = SessionModel.objects.create(name=name, parent_project=project)
    sv = SessionVersionModel.objects.create(
        session=session, agent=agent, pinned_agent_version=av
    )
    SessionModel.objects.filter(pk=session.pk).update(latest_session_version=sv)
    session.refresh_from_db()
    from runtime.session.session import Session as RuntimeSession

    return RuntimeSession(session_model=session, pinned_session_version=sv)


class ProjectOfTest(TestCase):
    """Session.get_project returns the session project, None when global."""

    def test_project_session(self):
        project = _make_project()
        agent, av = _make_agent("po-b")
        rt = _make_session(agent, av, project=project)
        self.assertEqual(rt.get_project().pk, project.pk)

    def test_global_session_yields_none(self):
        agent, av = _make_agent("po-g")
        rt = _make_session(agent, av, name="po-global")
        self.assertIsNone(rt.get_project())


class AssistantWorkspaceTest(TestCase):
    """Singular get_assistant_workspace shares the session binding row."""

    def test_global_agent_workspace_is_agentone_home(self):
        from runtime.agents.agent import Agent as AgentRt
        from runtime.paths import agentone_home

        agent, _av = _make_agent("aw-a", manifest_dir="/tmp/aw-a")
        ws = AgentRt(agent_model=agent).get_assistant_workspace()
        self.assertEqual(ws.path, agentone_home().as_posix())
        self.assertEqual(ws.name, "AgentOne home")

    def test_global_skill_workspace_is_agentone_home(self):
        from runtime.paths import agentone_home
        from runtime.skill.skill import Skill as SkillRt

        skill = _make_skill("aw-s", manifest_dir="/tmp/aw-s")
        ws = SkillRt(skill_model=skill).get_assistant_workspace()
        self.assertEqual(ws.path, agentone_home().as_posix())

    def test_cron_workspace_matches_binding(self):
        from runtime.cron.cron import Cron as CronRt
        from runtime.workspace.workspaces import Workspaces

        project = _make_project(path="/tmp/aw-cron")
        job = Cronjob.objects.create(
            name="aw-job", schedule="* * * * *", parent_project=project
        )
        ws = CronRt(cronjob_model=job).get_assistant_workspace()
        self.assertEqual(ws.pk, Workspaces.for_project(project).pk)

    def test_project_workspace_is_project_root(self):
        from runtime.project.project import Project as ProjectRt
        from runtime.workspace.workspaces import Workspaces

        project = _make_project(path="/tmp/aw-proj")
        ws = ProjectRt(project_model=project).get_assistant_workspace()
        self.assertEqual(ws.pk, Workspaces.for_project(project).pk)


class PluralAssistantWorkspaceTest(TestCase):
    """Plural get_assistant_workspace mirrors the session bindings."""

    def test_global_rows_all_share_agentone_home(self):
        from runtime.agents.agents import Agents
        from runtime.cron.crons import Cronjobs
        from runtime.paths import agentone_home
        from runtime.project.projects import Projects
        from runtime.skill.skills import Skills
        from runtime.workitems.workitems import Workitems
        from runtime.workspace.workspaces import Workspaces

        home = Workspaces.agentone_home_workspace()
        self.assertEqual(home.path, agentone_home().as_posix())
        self.assertEqual(home.name, "AgentOne home")
        for collection in (Agents, Cronjobs, Projects, Skills, Workitems, Workspaces):
            self.assertEqual(collection().get_assistant_workspace().pk, home.pk)

    def test_legacy_system_row_is_renamed_in_place(self):
        from runtime.paths import agentone_home
        from runtime.workspace.workspaces import Workspaces
        from server.models.workspace import WorkspaceModel

        legacy = WorkspaceModel.objects.create(
            name="AgentOne system", path="/tmp/legacy-home", description="old"
        )
        home = Workspaces.agentone_home_workspace()
        self.assertEqual(home.pk, legacy.pk)
        legacy.refresh_from_db()
        self.assertEqual(legacy.name, "AgentOne home")
        self.assertEqual(legacy.path, agentone_home().as_posix())

    def test_project_scope_rows(self):
        from runtime.agents.agents import Agents
        from runtime.cron.crons import Cronjobs
        from runtime.skill.skills import Skills
        from runtime.workitems.workitems import Workitems
        from runtime.workspace.workspaces import Workspaces

        project = _make_project(path="/tmp/aw-plural")
        expected = Workspaces.for_project(project).pk
        self.assertEqual(Agents(parent_project=project).get_assistant_workspace().pk, expected)
        self.assertEqual(Skills(parent_project=project).get_assistant_workspace().pk, expected)
        self.assertEqual(Cronjobs(parent_project=project).get_assistant_workspace().pk, expected)
        self.assertEqual(Workitems(parent_project=project).get_assistant_workspace().pk, expected)


class SkillsScopeTest(TestCase):
    """Union scoping for projects, children for agent/skill parents."""

    def test_project_scope_is_union(self):
        project = _make_project()
        _make_skill("g-skill")
        _make_skill("p-skill", project=project)
        names = [s.name for s in Skills(parent_project=project).all()]
        self.assertEqual(names, ["g-skill", "p-skill"])

    def test_global_scope_excludes_project_skills(self):
        project = _make_project()
        _make_skill("g-skill")
        _make_skill("p-skill", project=project)
        self.assertEqual([s.name for s in Skills().all()], ["g-skill"])

    def test_agent_parent_selects_children(self):
        agent, _av = _make_agent("sk-owner")
        SkillModel.objects.create(name="child-skill", parent_agent=agent)
        _make_skill("other-skill")
        self.assertEqual(
            [s.name for s in Skills(parent_agent=agent).all()], ["child-skill"]
        )

    def test_list_skills_returns_wrappers(self):
        from runtime.skill.skill import Skill

        _make_skill("w-skill")
        listed = Skills().list_skills()
        self.assertEqual(len(listed), 1)
        self.assertIsInstance(listed[0], Skill)
        self.assertEqual(listed[0].name, "w-skill")

    def test_source_dir_prefers_stored_manifest_dir(self):
        skill = _make_skill("s-stored", manifest_dir="/tmp/custom/skilldir")
        from runtime.skill.skill import Skill

        self.assertEqual(
            Skill(skill).get_source_dir().as_posix(), "/tmp/custom/skilldir"
        )

    def test_source_dir_falls_back_to_conventional(self):
        project = _make_project(path="/tmp/conv-proj")
        skill = _make_skill("s-conv", project=project)
        from runtime.skill.skill import Skill

        self.assertEqual(
            Skill(skill).get_source_dir().as_posix(),
            "/tmp/conv-proj/.agentone/skills/s-conv",
        )

    def test_assistant_wiring(self):
        project = _make_project(path="/tmp/sk-ws-proj")
        self.assertEqual(Skills.ASSISTANT_NAMES, ("AgentOne", "AgentOne"))
        self.assertEqual(Skills().assistant_name, "AgentOne")
        self.assertIsNone(Skills().project)
        self.assertEqual(Skills(parent_project=project).project.pk, project.pk)
        self.assertTrue(Skills().get_source_dir().as_posix().endswith("skills"))


class AgentsScopeTest(TestCase):
    """Union scoping mirrors the skills behavior."""

    def test_project_scope_is_union(self):
        project = _make_project()
        _make_agent("g-agent")
        _make_agent("p-agent", project=project)
        names = [a.name for a in Agents(parent_project=project).all()]
        self.assertEqual(names, ["g-agent", "p-agent"])

    def test_global_scope_excludes_project_agents(self):
        project = _make_project()
        _make_agent("p-agent", project=project)
        self.assertEqual(list(Agents().all()), [])

    def test_root_stays_unscoped(self):
        # root() keeps its pre-existing meaning: top-level agents only
        # (no parent of any kind) — project children are excluded.
        project = _make_project()
        _make_agent("g-agent")
        _make_agent("p-agent", project=project)
        self.assertEqual({a.name for a in Agents().root()}, {"g-agent"})

    def test_list_agents_returns_wrappers(self):
        from runtime.agents.agent import Agent

        _make_agent("w-agent")
        listed = Agents().list_agents()
        self.assertEqual(len(listed), 1)
        self.assertIsInstance(listed[0], Agent)

    def test_cross_navigation(self):
        agent, _av = _make_agent("nav-agent")
        SkillModel.objects.create(name="nav-child-skill", parent_agent=agent)
        AgentModel.objects.create(name="nav-sub", parent_agent=agent)
        from runtime.agents.agent import Agent

        wrapper = Agent(agent)
        self.assertEqual(
            [s.name for s in wrapper.get_skills_runtime().all()], ["nav-child-skill"]
        )
        self.assertEqual(
            [a.name for a in wrapper.get_agents_runtime().all()], ["nav-sub"]
        )


class ProjectsTest(TestCase):
    """Top-level collection: parents raise, assistants are global."""

    def test_parent_kwarg_raises_type_error(self):
        with self.assertRaises(TypeError):
            Projects(parent_project=_make_project())

    def test_all_lists_everything(self):
        _make_project(name="b-proj", path="/tmp/b")
        _make_project(name="a-proj", path="/tmp/a")
        self.assertEqual([p.name for p in Projects().all()], ["a-proj", "b-proj"])

    def test_list_projects_returns_wrappers(self):
        from runtime.project.project import Project as ProjectScope

        _make_project(name="w-proj", path="/tmp/w")
        listed = Projects().list_projects()
        self.assertEqual(len(listed), 1)
        self.assertIsInstance(listed[0], ProjectScope)

    def test_project_child_navigation(self):
        project = _make_project(path="/tmp/nav-proj")
        _make_agent("nav-p-agent", project=project)
        _make_skill("nav-p-skill", project=project)
        from runtime.project.project import Project as ProjectScope

        wrapper = ProjectScope(project)
        self.assertEqual(
            [a.name for a in wrapper.get_agents_runtime().all()], ["nav-p-agent"]
        )
        self.assertEqual(
            [s.name for s in wrapper.get_skills_runtime().all()], ["nav-p-skill"]
        )
        self.assertEqual(wrapper.counts()["agents"], 1)
        self.assertEqual(wrapper.get_source_dir().as_posix(), "/tmp/nav-proj/.agentone")


class SessionsScopeTest(TestCase):
    """Project children vs session children vs all."""

    def test_project_scope(self):
        project = _make_project()
        agent, av = _make_agent("sess-a")
        _make_session(agent, av, name="in-proj", project=project)
        _make_session(agent, av, name="outside")
        self.assertEqual(
            [s.name for s in Sessions(parent_project=project).all()], ["in-proj"]
        )

    def test_session_parent_selects_children(self):
        agent, av = _make_agent("sess-b")
        parent = _make_session(agent, av, name="par")
        SessionModel.objects.create(name="kid", parent_session=parent.model)
        _make_session(agent, av, name="unrelated")
        self.assertEqual(
            [s.name for s in Sessions(parent_session=parent).all()], ["kid"]
        )


class WorkspacesScopeTest(TestCase):
    """Project workspaces, path-nested sub-workspaces, and helpers."""

    def test_project_scope(self):
        project = _make_project(path="")
        WorkspaceModel.objects.create(name="w1", path="/tmp/w1", parent_project=project)
        WorkspaceModel.objects.create(name="w2", path="/tmp/w2")
        self.assertEqual(
            [w.name for w in Workspaces(parent_project=project).all()], ["w1"]
        )

    def test_workspace_parent_selects_nested(self):
        base = WorkspaceModel.objects.create(name="base", path="/tmp/nest")
        WorkspaceModel.objects.create(name="kid", path="/tmp/nest/kid")
        WorkspaceModel.objects.create(name="else", path="/tmp/other")
        self.assertEqual(
            [w.name for w in Workspaces(parent_workspace=base).all()], ["kid"]
        )

    def test_ensure_named_idempotent(self):
        first = Workspaces.ensure_named("ws-x", "/tmp/ws-x", "d")
        second = Workspaces.ensure_named("ws-x", "/tmp/ws-x", "d-changed")
        self.assertEqual(first.pk, second.pk)
        second.refresh_from_db()
        self.assertEqual(second.description, "d-changed")

    def test_ensure_named_adopts_project(self):
        project = _make_project(path="")
        existing = WorkspaceModel.objects.create(name="adopt-me", path="/tmp/adopt-me")
        adopted = Workspaces.ensure_named(
            "adopt-me", "/tmp/adopt-me", parent_project=project
        )
        self.assertEqual(adopted.pk, existing.pk)
        adopted.refresh_from_db()
        self.assertEqual(adopted.parent_project_id, project.pk)

    def test_source_scope_preserves_path_hierarchy_and_migrates_data(self):
        from runtime.paths import central_workspaces_base

        with tempfile.TemporaryDirectory() as home, patch.dict(
            os.environ, {"AGENTONE_HOME": home}
        ):
            source = Path(home) / "checkout" / "agents" / "wiki"
            name = f"{source.as_posix()} assistant scope"
            old_dir = Path(home) / "workspaces" / "_flattened_scope"
            (old_dir / "memory").mkdir(parents=True)
            (old_dir / "memory" / "reflection.md").write_text(
                "existing memory", encoding="utf-8"
            )
            (old_dir / "memory" / ".git").mkdir()
            (old_dir / "memory" / ".git" / "config").write_text(
                "repository metadata", encoding="utf-8"
            )
            existing = WorkspaceModel.objects.create(
                name=name,
                path=source.as_posix(),
                agentone_dir=old_dir.as_posix(),
            )

            workspace = Workspaces.ensure_source_scope(
                name, source, "source scope for wiki"
            )

            expected = (
                central_workspaces_base()
                / "_assistant_scopes"
                / source.relative_to(source.anchor)
                / "assistant_scope"
            )
            workspace.refresh_from_db()
            self.assertEqual(workspace.pk, existing.pk)
            self.assertEqual(workspace.get_agentone_dir(), expected)
            self.assertFalse(old_dir.exists())
            self.assertEqual(
                (expected / "memory" / "reflection.md").read_text(
                    encoding="utf-8"
                ),
                "existing memory",
            )
            self.assertEqual(
                (expected / "memory" / ".git" / "config").read_text(
                    encoding="utf-8"
                ),
                "repository metadata",
            )
            self.assertEqual(
                Workspaces.ensure_source_scope(name, source).pk, existing.pk
            )

    def test_for_project_prefers_main_workspace(self):
        import tempfile

        tmp = Path(tempfile.mkdtemp()).as_posix()
        main_ws = WorkspaceModel.objects.create(name="main", path=tmp)
        project = Project.objects.create(
            name="p-main", main_workspace=main_ws
        )
        self.assertEqual(Workspaces.for_project(project).pk, main_ws.pk)

    def test_assistant_names(self):
        self.assertEqual(
            Workspaces.ASSISTANT_NAMES,
            ("AgentOne", "AgentOne"),
        )


class WorkitemsScopeTest(TestCase):
    """Strict project scoping, inbox globally, baked ordering."""

    def test_strict_project_scope(self):
        project = _make_project()
        WorkItem.objects.create(title="g-item", priority=10)
        WorkItem.objects.create(title="p-item", priority=10, project=project)
        self.assertEqual(
            [i.title for i in Workitems(parent_project=project).all()], ["p-item"]
        )

    def test_global_scope_is_inbox_only(self):
        project = _make_project()
        WorkItem.objects.create(title="g-item", priority=10)
        WorkItem.objects.create(title="p-item", priority=10, project=project)
        self.assertEqual([i.title for i in Workitems().all()], ["g-item"])

    def test_ordering_baked_in(self):
        # Mirrors WorkItem.Meta.ordering (["-priority", "created_at"]):
        # highest priority VALUE first (status-quo queue order).
        WorkItem.objects.create(title="low", priority=90)
        WorkItem.objects.create(title="high", priority=5)
        self.assertEqual([i.title for i in Workitems().all()], ["low", "high"])

    def test_list_workitems_returns_wrappers(self):
        from runtime.workitems.workitem import WorkItem as WorkItemScope

        WorkItem.objects.create(title="w-item", priority=10)
        listed = Workitems().list_workitems()
        self.assertEqual(len(listed), 1)
        self.assertIsInstance(listed[0], WorkItemScope)

    def test_rejects_agent_parent_kwarg(self):
        agent, _av = _make_agent("wi-a")
        with self.assertRaises(TypeError):
            Workitems(parent_agent=agent)  # pylint: disable=unexpected-keyword-arg


class CronScopeTest(TestCase):
    """Strict project scoping; due() stays scheduler-safe when bare."""

    def _make_job(self, name, project=None, active=True):
        import datetime

        from django.utils import timezone

        agent, _av = _make_agent(f"{name}-agent")
        return Cronjob.objects.create(
            name=name, schedule="* * * * *", agent=agent,
            parent_project=project, is_active=active,
            next_run_at=timezone.now() - datetime.timedelta(days=1),
        )

    def test_strict_project_scope(self):
        project = _make_project()
        self._make_job("g-job")
        self._make_job("p-job", project=project)
        self.assertEqual(
            [j.name for j in Cronjobs(parent_project=project).all()], ["p-job"]
        )

    def test_global_scope_excludes_project_jobs(self):
        project = _make_project()
        self._make_job("p-job", project=project)
        self.assertEqual(list(Cronjobs().all()), [])

    def test_due_unscoped_when_bare(self):
        project = _make_project()
        self._make_job("g-job")
        self._make_job("p-job", project=project)
        self.assertEqual(
            {j.name for j in Cronjobs().due()}, {"g-job", "p-job"}
        )

    def test_due_scoped_with_parent(self):
        project = _make_project()
        self._make_job("g-job")
        self._make_job("p-job", project=project)
        self.assertEqual(
            [j.name for j in Cronjobs(parent_project=project).due()], ["p-job"]
        )

    def test_rejects_agent_parent_kwarg(self):
        agent, _av = _make_agent("cron-a")
        with self.assertRaises(TypeError):
            Cronjobs(parent_agent=agent)  # pylint: disable=unexpected-keyword-arg

    def test_cron_wrapper_source_dir(self):
        from runtime.cron.cron import Cron

        project = _make_project(path="/tmp/cron-proj")
        job = self._make_job("src-job", project=project)
        self.assertEqual(
            Cron(job).get_source_dir().as_posix(),
            "/tmp/cron-proj/.agentone",
        )


class AssistantSessionTest(TestCase):
    """Singleton assistant sessions with project binding."""

    def setUp(self):
        self.agent, self.av = _make_agent("AgentOne")
        self.rt = _make_session(self.agent, self.av, name="as-parent")

    def test_unknown_assistant_returns_none(self):
        self.assertIsNone(Sessions().assistant_session("no-such", caller=self.rt))

    def test_global_singleton_reused(self):
        first = Skills().get_assistant_session(caller=self.rt)
        second = Skills().get_assistant_session(caller=self.rt)
        self.assertIsNotNone(first)
        self.assertEqual(first.model.pk, second.model.pk)
        self.assertEqual(first.model.name, "AgentOne - global")
        self.assertEqual(first.model.group_key, "assistant:AgentOne")
        self.assertIsNone(first.model.parent_project)

    def test_project_scope_binds_project(self):
        project = _make_project(name="as-proj", path="/tmp/as-proj")
        child = Skills(parent_project=project).get_assistant_session(caller=self.rt)
        self.assertIsNotNone(child)
        self.assertEqual(child.model.parent_project_id, project.pk)
        self.assertEqual(child.model.name, "AgentOne - as-proj")

    def test_singular_name_override(self):
        _make_agent("custom-helper")
        child = Skills().get_assistant_session(
            caller=self.rt, name="custom-helper"
        )
        self.assertIsNotNone(child)
        self.assertEqual(child.model.name, "custom-helper - global")

    def test_singular_item_label(self):
        agent, _av = _make_agent("labelled-agent")
        from runtime.agents.agent import Agent

        child = Agent(agent).get_assistant_session(caller=self.rt)
        self.assertIsNotNone(child)
        self.assertEqual(child.model.name, "AgentOne - labelled-agent")

    def test_owner_scoped_label(self):
        agent, _av = _make_agent("owner-agent")
        child = Skills(parent_agent=agent).get_assistant_session(caller=self.rt)
        self.assertIsNotNone(child)
        self.assertEqual(child.model.name, "AgentOne - agent owner-agent")

    def test_callerless_creation(self):
        child = Skills().get_assistant_session()
        self.assertIsNotNone(child)
        self.assertEqual(child.model.name, "AgentOne - global")
        self.assertEqual(child.model.group_key, "assistant:AgentOne")

    def test_spawn_project_binding_preserved(self):
        project = _make_project(path="/tmp/sp-proj")
        child = self.rt.spawn_subagent(self.av, name="sp-child", project=project)
        self.assertEqual(child.model.parent_project_id, project.pk)


class AssistantScopeLabelTest(TestCase):
    """``assistant_scope_label`` names every scope for sortable sessions."""

    def test_singular_labels_use_item_name(self):
        from runtime.agents.agent import Agent
        from runtime.cron.cron import Cron
        from runtime.project.project import Project as ProjectRt
        from runtime.skill.skill import Skill
        from runtime.workspace.workspace import Workspace as WorkspaceRt
        from runtime.workitems.workitem import WorkItem as WorkItemRt

        agent, _av = _make_agent("labelled-agent")
        self.assertEqual(Agent(agent).assistant_scope_label(), "labelled-agent")

        skill = _make_skill("labelled-skill")
        self.assertEqual(Skill(skill).assistant_scope_label(), "labelled-skill")

        project = _make_project(name="labelled-proj", path="/tmp/labelled-proj")
        self.assertEqual(ProjectRt(project).assistant_scope_label(), "labelled-proj")

        job = Cronjob.objects.create(name="labelled-job", schedule="* * * * *")
        self.assertEqual(Cron(job).assistant_scope_label(), "labelled-job")

        ws = WorkspaceModel.objects.create(name="labelled-ws", path="/tmp/labelled-ws")
        self.assertEqual(WorkspaceRt(ws).assistant_scope_label(), "labelled-ws")

        item = WorkItem.objects.create(title="fix the thing", priority=10)
        self.assertEqual(WorkItemRt(item).assistant_scope_label(), f"#{item.pk} fix the thing")

    def test_workspace_label_falls_back_to_path_basename(self):
        from runtime.workspace.workspace import Workspace as WorkspaceRt

        ws = WorkspaceModel.objects.create(name="", path="/tmp/basename-ws")
        self.assertEqual(WorkspaceRt(ws).assistant_scope_label(), "basename-ws")

    def test_plural_labels_use_project_name_or_global(self):
        project = _make_project(name="plural-proj", path="/tmp/plural-proj")
        self.assertEqual(Skills().assistant_scope_label(), "global")
        self.assertEqual(
            Skills(parent_project=project).assistant_scope_label(), "plural-proj"
        )
        self.assertEqual(Projects().assistant_scope_label(), "global")

    def test_plural_labels_use_owner_kind_and_name(self):
        agent, _av = _make_agent("owner-agent")
        self.assertEqual(
            Skills(parent_agent=agent).assistant_scope_label(), "agent owner-agent"
        )
        ws = WorkspaceModel.objects.create(name="owner-ws", path="/tmp/owner-ws")
        self.assertEqual(
            Agents(parent_workspace=ws).assistant_scope_label(), "workspace owner-ws"
        )


class ManifestDirLoaderTest(AgentMdTestMixin, TestCase):
    """The loaders stamp manifest_dir on agent/skill/cron rows."""

    @classmethod
    def setUpTestData(cls):
        cls.setup_global_tasks()
        cls.setup_install_repo()

    @classmethod
    def tearDownClass(cls):
        cls.teardown_install_repo()
        super().tearDownClass()

    def test_agent_manifest_dir_recorded(self):
        agent, _av = self.load_agent("base")
        self.assertEqual(
            Path(agent.manifest_dir).as_posix(),
            (TESTPROJECT / "agents" / "base").as_posix(),
        )

    def test_agent_manifest_dir_updated_on_reload(self):
        agent, _av = self.load_agent("base")
        first = agent.manifest_dir
        agent2, _av2 = self.load_agent("base")
        self.assertEqual(agent2.manifest_dir, first)
        self.assertTrue(first)

    def test_cron_manifest_dir_not_required(self):
        """Cron jobs are DB-canonical and do not require manifest files."""
        job = Cronjob.objects.create(name="scoped-cron", schedule="*/5 * * * *")
        self.assertEqual(job.manifest_dir, "")


class ScriptHelpersTest(TestCase):
    """Shared row builders, markdown renderers, and matchers."""

    def test_normalize_dir(self):
        from runtime.script_helpers import normalize_dir

        self.assertEqual(normalize_dir(""), "")
        self.assertEqual(normalize_dir(None), "")
        self.assertEqual(normalize_dir("/tmp/x/"), "/tmp/x")
        self.assertEqual(normalize_dir("~/x"), str(Path("~/x").expanduser().as_posix()))

    def test_rows_carry_plan_fields(self):
        from runtime.script_helpers import agent_row, skill_row

        agent, _av = _make_agent("row-a", manifest_dir="/tmp/row-a")
        row = agent_row(agent)
        self.assertEqual(row["path"], "/tmp/row-a")
        self.assertEqual(row["version_number"], 0)
        self.assertEqual(row["kind"], "root")
        skill = _make_skill("row-s", manifest_dir="/tmp/row-s")
        srow = skill_row(skill)
        self.assertEqual(srow["manifest_dir"], "/tmp/row-s")
        self.assertEqual(srow["version_number"], 0)
