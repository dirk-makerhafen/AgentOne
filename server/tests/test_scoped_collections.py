"""Tests for parent-scoped runtime collections and assistant wiring.

Each plural collection takes explicit parent kwargs and scopes ``all()``
accordingly; ``root()`` stays unscoped for UI callers; ``list_*()``
returns wrapped singular objects; ``get_source_dir()`` is pure path
resolution (stored ``manifest_dir`` first, conventional layout fallback);
``get_assistant_session()`` spawns the bound singleton.
"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from django.test import TestCase

from runtime.agents.agents import Agents
from runtime.cron.crons import Cronjobs
from runtime.project.projects import Projects, project_of
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
# (ScriptParityTest intentionally exercises the scripts' private helpers.)


def _make_project(name="p", path="/tmp/p"):
    return Project.objects.create(name=name, path=path)


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
    """project_of unwraps sessions, passes projects, tolerates the rest."""

    def test_none_stays_none(self):
        self.assertIsNone(project_of(None))

    def test_project_passes_through(self):
        project = _make_project()
        self.assertEqual(project_of(project).pk, project.pk)

    def test_session_model_unwraps(self):
        project = _make_project()
        agent, av = _make_agent("po-a")
        rt = _make_session(agent, av, project=project)
        self.assertEqual(project_of(rt.model).pk, project.pk)

    def test_runtime_session_unwraps(self):
        project = _make_project()
        agent, av = _make_agent("po-b")
        rt = _make_session(agent, av, project=project)
        self.assertEqual(project_of(rt).pk, project.pk)

    def test_unknown_parent_yields_none(self):
        self.assertIsNone(project_of(object()))
        self.assertIsNone(project_of(SimpleNamespace()))


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
        self.assertEqual(Skills.ASSISTANT_NAMES, ("skill_assistant", "skills_assistant"))
        self.assertEqual(Skills().assistant_name, "skills_assistant")
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

    def test_project_of_helper(self):
        project = _make_project()
        agent, av = _make_agent("sess-c")
        rt = _make_session(agent, av, project=project)
        self.assertEqual(Sessions.project_of(rt).pk, project.pk)
        self.assertIsNone(Sessions.project_of(SimpleNamespace()))


class WorkspacesScopeTest(TestCase):
    """Project workspaces, path-nested sub-workspaces, and helpers."""

    def test_project_scope(self):
        project = _make_project()
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

    def test_for_project_prefers_main_workspace(self):
        import tempfile

        tmp = Path(tempfile.mkdtemp()).as_posix()
        main_ws = WorkspaceModel.objects.create(name="main", path=tmp)
        project = Project.objects.create(
            name="p-main", path=f"{tmp}/proj", main_workspace=main_ws
        )
        self.assertEqual(Workspaces.for_project(project).pk, main_ws.pk)

    def test_assistant_names(self):
        self.assertEqual(
            Workspaces.ASSISTANT_NAMES,
            ("workspace_assistant", "workspaces_assistant"),
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
            "/tmp/cron-proj/.agentone/cronjobs",
        )


class AssistantSessionTest(TestCase):
    """Singleton assistant sessions with project binding."""

    def setUp(self):
        self.agent, self.av = _make_agent("skills_assistant")
        self.rt = _make_session(self.agent, self.av, name="as-parent")

    def test_unknown_assistant_returns_none(self):
        self.assertIsNone(Sessions().assistant_session("no-such", caller=self.rt))

    def test_global_singleton_reused(self):
        first = Skills().get_assistant_session(caller=self.rt)
        second = Skills().get_assistant_session(caller=self.rt)
        self.assertIsNotNone(first)
        self.assertEqual(first.model.pk, second.model.pk)
        self.assertEqual(first.model.name, "skills_assistant:global")
        self.assertIsNone(first.model.parent_project)

    def test_project_scope_binds_project(self):
        project = _make_project(path="/tmp/as-proj")
        child = Skills(parent_project=project).get_assistant_session(caller=self.rt)
        self.assertIsNotNone(child)
        self.assertEqual(child.model.parent_project_id, project.pk)
        self.assertTrue(child.model.name.startswith("skills_assistant:/tmp/as-proj"))

    def test_singular_name_override(self):
        _make_agent("skill_assistant")
        child = Skills().get_assistant_session(
            caller=self.rt, name="skill_assistant"
        )
        self.assertIsNotNone(child)
        self.assertEqual(child.model.name, "skill_assistant:global")

    def test_callerless_creation(self):
        child = Skills().get_assistant_session()
        self.assertIsNotNone(child)
        self.assertEqual(child.model.name, "skills_assistant:global")

    def test_spawn_project_binding_preserved(self):
        project = _make_project(path="/tmp/sp-proj")
        child = self.rt.spawn_subagent(self.av, name="sp-child", project=project)
        self.assertEqual(child.model.parent_project_id, project.pk)


def _load_script(relative_path, module_name):
    """Load an assistant script file by repo-relative path (no package)."""
    full = Path(".agentone") / relative_path
    spec = importlib.util.spec_from_file_location(module_name, full)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ScriptParityTest(TestCase):
    """Refactored assistant scripts return what the old helpers did."""

    def test_skills_helpers_match_collections(self):
        project = _make_project()
        _make_skill("g-skill")
        _make_skill("p-skill", project=project)
        agent, av = _make_agent("par-a")
        rt = _make_session(agent, av, project=project)
        mod = _load_script("agents/internal/skills_assistant/scripts/skills.py", "par_skills")
        self.assertEqual(mod._session_project(rt).pk, project.pk)
        self.assertEqual(
            [s.pk for s in mod._scoped_skills(rt)],
            [s.pk for s in Skills(parent_project=project).all()],
        )
        rt_global = _make_session(agent, av, name="par-g")
        self.assertIsNone(mod._session_project(rt_global))
        self.assertEqual(
            [s.pk for s in mod._scoped_skills(rt_global)],
            [s.pk for s in Skills().all()],
        )

    def test_agents_helpers_match_collections(self):
        project = _make_project()
        _make_agent("g-agent")
        _make_agent("p-agent", project=project)
        agent, av = _make_agent("par-b")
        rt = _make_session(agent, av, project=project)
        mod = _load_script("agents/internal/agents_assistant/scripts/agents.py", "par_agents")
        self.assertEqual(
            [a.pk for a in mod._scoped_agents(rt)],
            [a.pk for a in Agents(parent_project=project).all()],
        )

    def test_cron_helpers_match_collections(self):
        project = _make_project()
        agent, av = _make_agent("par-cron")
        Cronjob.objects.create(
            name="g-job", schedule="* * * * *", agent=agent
        )
        Cronjob.objects.create(
            name="p-job", schedule="* * * * *", agent=agent,
            parent_project=project,
        )
        rt = _make_session(agent, av, project=project)
        mod = _load_script(
            "agents/internal/cronjobs_assistant/scripts/cronjobs.py", "par_crons"
        )
        self.assertEqual(
            [j.pk for j in mod._scoped_jobs(rt)],
            [j.pk for j in Cronjobs(parent_project=project).all()],
        )

    def test_workitems_helpers_match_collections(self):
        project = _make_project()
        WorkItem.objects.create(title="g-item", priority=10)
        item = WorkItem.objects.create(title="p-item", priority=10, project=project)
        agent, av = _make_agent("par-c")
        rt = _make_session(agent, av, project=project)
        mod = _load_script(
            "agents/internal/workitems_assistant/scripts/workitems.py", "par_workitems"
        )
        self.assertEqual(
            [i.pk for i in mod._visible_items(rt)],
            [i.pk for i in Workitems(parent_project=project).all()],
        )
        single = _load_script(
            "agents/internal/workitem_assistant/scripts/workitem.py", "par_workitem"
        )
        self.assertEqual([i.pk for i in single._visible_items(rt, item.pk)], [item.pk])

    def test_project_counts_match_strict_queries(self):
        project = _make_project()
        agent, av = _make_agent("par-d")
        _make_session(agent, av, name="par-sess", project=project)
        _make_agent("owned-agent", project=project)
        _make_skill("owned-skill", project=project)
        mod = _load_script(
            "agents/internal/projects_assistant/scripts/projects.py", "par_projects"
        )
        counts = mod._project_counts(project)
        self.assertEqual(counts["agents"], 1)
        self.assertEqual(counts["skills"], 1)
        self.assertEqual(counts["sessions"], 1)
        self.assertEqual(counts["cronjobs"], 0)
        self.assertEqual(counts["workitems"], 0)
        self.assertEqual(SessionModel.objects.filter(parent_project=project).count(), 1)


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

    def test_cron_manifest_dir_recorded(self):
        from registry.loader.load_cron_manifest import load_cron_manifest

        job = load_cron_manifest(
            TESTPROJECT / "cronjobs" / "health_check.md",
            install_repo=self.__class__._install_repo,
        )
        self.assertEqual(
            Path(job.manifest_dir).as_posix(),
            (TESTPROJECT / "cronjobs").as_posix(),
        )
