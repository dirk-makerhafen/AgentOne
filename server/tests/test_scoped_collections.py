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
        self.assertEqual(rt.get_project().pk, project.pk)
        self.assertEqual(
            [s.pk for s in mod._scoped_skills(rt)],
            [s.pk for s in Skills(parent_project=project).all()],
        )
        rt_global = _make_session(agent, av, name="par-g")
        self.assertIsNone(rt_global.get_project())
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


def _make_ws_session(agent, av, workspace, name="ws-sess", project=None):
    session = SessionModel.objects.create(
        name=name, parent_project=project
    )
    sv = SessionVersionModel.objects.create(
        session=session, agent=agent, pinned_agent_version=av, workspace=workspace
    )
    SessionModel.objects.filter(pk=session.pk).update(latest_session_version=sv)
    session.refresh_from_db()
    from runtime.session.session import Session as RuntimeSession

    return RuntimeSession(session_model=session, pinned_session_version=sv)


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

    def test_markdown_shapes(self):
        from runtime.script_helpers import (
            agent_list_item,
            as_markdown_list,
            skill_list_item,
            workitem_list_item,
        )

        agent, _av = _make_agent("md-a", manifest_dir="/tmp/md-a")
        text = agent_list_item(agent)
        self.assertIn("**md-a**", text)
        self.assertIn("/tmp/md-a", text)
        self.assertEqual(as_markdown_list([], agent_list_item), "(none)")
        self.assertEqual(
            as_markdown_list([agent], agent_list_item), agent_list_item(agent)
        )
        skill = _make_skill("md-s", manifest_dir="/tmp/md-s")
        self.assertIn("**md-s**", skill_list_item(skill))
        item = WorkItem.objects.create(title="md-item", priority=10)
        self.assertIn(f"#{item.pk}", workitem_list_item(item))
        self.assertIn("backlog", workitem_list_item(item))

    def test_match_manifest_dir(self):
        from runtime.script_helpers import match_manifest_dir, unbound_error

        _make_agent("mm-a", manifest_dir="/tmp/mm-a")
        found = match_manifest_dir(AgentModel.objects.all(), "/tmp/mm-a")
        self.assertEqual([a.name for a in found], ["mm-a"])
        self.assertEqual(match_manifest_dir(AgentModel.objects.all(), "/tmp/nope"), [])
        err = unbound_error("a project scope")
        self.assertEqual(err["status"], "error")
        self.assertIn("not bound", err["message"])


class SubListToolsTest(TestCase):
    """New bound list_* tools resolve children via the session scope."""

    def test_agent_lists(self):
        project = _make_project()
        agent, av = _make_agent("sub-a", project=project, manifest_dir="/tmp/sub-a")
        SkillModel.objects.create(
            name="kid-skill", parent_project=project, parent_agent=agent,
            manifest_dir="/tmp/kid-skill",
        )
        AgentModel.objects.create(
            name="kid-agent", parent_project=project, parent_agent=agent,
            manifest_dir="/tmp/kid-agent",
        )
        Cronjob.objects.create(
            name="kid-job", schedule="* * * * *", agent=agent,
            parent_project=project,
        )
        ws = WorkspaceModel.objects.create(name="sub-ws", path="/tmp/sub-a")
        rt = _make_ws_session(agent, av, ws, project=project)
        mod = _load_script(
            "agents/internal/agent_assistant/scripts/agent.py", "sub_agent"
        )
        ok, skills = mod.list_skills(rt)
        self.assertTrue(ok, skills)
        self.assertEqual([s["name"] for s in skills["skills"]], ["kid-skill"])
        self.assertEqual(skills["count"], 1)
        self.assertTrue(skills["scope"].endswith("/skills/"))
        ok, agents = mod.list_agents(rt)
        self.assertTrue(ok, agents)
        self.assertEqual([a["name"] for a in agents["agents"]], ["kid-agent"])
        ok, jobs = mod.list_cronjobs(rt)
        self.assertTrue(ok, jobs)
        self.assertEqual([j["name"] for j in jobs["cronjobs"]], ["kid-job"])

    def test_skill_lists(self):
        skill = _make_skill("sub-s", manifest_dir="/tmp/sub-s")
        SkillModel.objects.create(
            name="grand-skill", parent_skill=skill, manifest_dir="/tmp/grand-skill"
        )
        AgentModel.objects.create(
            name="owned-agent", parent_skill=skill, manifest_dir="/tmp/owned-agent"
        )
        agent, av = _make_agent("sub-s-host")
        ws = WorkspaceModel.objects.create(name="sub-s-ws", path="/tmp/sub-s")
        rt = _make_ws_session(agent, av, ws)
        mod = _load_script(
            "agents/internal/skill_assistant/scripts/skill.py", "sub_skill"
        )
        ok, skills = mod.list_skills(rt)
        self.assertTrue(ok, skills)
        self.assertEqual([s["name"] for s in skills["skills"]], ["grand-skill"])
        ok, agents = mod.list_agents(rt)
        self.assertTrue(ok, agents)
        self.assertEqual([a["name"] for a in agents["agents"]], ["owned-agent"])

    def test_project_lists(self):
        project = _make_project(path="/tmp/proj-lists")
        _make_agent("proj-agent", project=project)
        _make_skill("proj-skill", project=project)
        agent, av = _make_agent("proj-host")
        Cronjob.objects.create(
            name="proj-job", schedule="* * * * *",
            parent_project=project,
        )
        rt = _make_session(agent, av, name="proj-rt", project=project)
        mod = _load_script(
            "agents/internal/project_assistant/scripts/project.py", "sub_project"
        )
        ok, agents = mod.list_agents(rt)
        self.assertTrue(ok, agents)
        self.assertEqual(
            {a["name"] for a in agents["agents"]}, {"proj-agent", "proj-host"}
        )
        self.assertTrue(agents["scope"].endswith("/.agentone/agents/"))
        ok, skills = mod.list_skills(rt)
        self.assertTrue(ok, skills)
        self.assertEqual([s["name"] for s in skills["skills"]], ["proj-skill"])
        ok, jobs = mod.list_cronjobs(rt)
        self.assertTrue(ok, jobs)
        self.assertEqual([j["name"] for j in jobs["cronjobs"]], ["proj-job"])
        rt_global = _make_session(agent, av, name="proj-g")
        ok, err = mod.list_agents(rt_global)
        self.assertFalse(ok)
        self.assertIn("not bound", err["message"])

    def test_workspace_lists(self):
        project = _make_project(path="/tmp/ws-lists")
        _make_agent("ws-agent", project=project)
        _make_skill("ws-skill", project=project)
        agent, av = _make_agent("ws-host")
        ws = WorkspaceModel.objects.create(
            name="ws-scope", path="/tmp/ws-lists", parent_project=project
        )
        rt = _make_ws_session(agent, av, ws, project=project)
        mod = _load_script(
            "agents/internal/workspace_assistant/scripts/workspaces.py", "sub_ws"
        )
        ok, skills = mod.list_skills(rt)
        self.assertTrue(ok, skills)
        self.assertIn("ws-skill", [s["name"] for s in skills["skills"]])
        ok, agents = mod.list_agents(rt)
        self.assertTrue(ok, agents)
        self.assertIn("ws-agent", [a["name"] for a in agents["agents"]])

    def test_existing_lists_extended(self):
        project = _make_project()
        _make_agent("ext-a", project=project, manifest_dir="/tmp/ext-a")
        _make_skill("ext-s", project=project, manifest_dir="/tmp/ext-s")
        agent, av = _make_agent("ext-host")
        rt = _make_session(agent, av, name="ext-rt", project=project)
        agents_mod = _load_script(
            "agents/internal/agents_assistant/scripts/agents.py", "ext_agents"
        )
        ok, result = agents_mod.list_agents(rt)
        self.assertTrue(ok, result)
        self.assertIn("scope", result)
        row = next(a for a in result["agents"] if a["name"] == "ext-a")
        self.assertEqual(row["path"], "/tmp/ext-a")
        skills_mod = _load_script(
            "agents/internal/skills_assistant/scripts/skills.py", "ext_skills"
        )
        ok, sresult = skills_mod.list_skills(rt)
        self.assertTrue(ok, sresult)
        self.assertIn("scope", sresult)
        srow = next(s for s in sresult["skills"] if s["name"] == "ext-s")
        self.assertEqual(srow["manifest_dir"], "/tmp/ext-s")
        ws_mod = _load_script(
            "agents/internal/workspaces_assistant/scripts/workspaces.py", "ext_ws"
        )
        ws = WorkspaceModel.objects.create(name="ext-ws", path="/tmp/ext-ws")
        _make_ws_session(agent, av, ws, name="ext-bound")
        ok, wresult = ws_mod.list_workspaces(rt)
        self.assertTrue(ok, wresult)
        self.assertIn("scope", wresult)
        wrow = next(w for w in wresult["workspaces"] if w["name"] == "ext-ws")
        self.assertEqual(wrow["session_count"], 1)


class DetailsToolsTest(TestCase):
    """*_details tools return beyond-file summaries with a status envelope."""

    def test_agent_details(self):
        project = _make_project(path="/tmp/det-proj")
        agent, av = _make_agent("det-a", project=project, manifest_dir="/tmp/det-a")
        SkillModel.objects.create(
            name="det-skill", parent_project=project, parent_agent=agent,
            manifest_dir="/tmp/det-skill",
        )
        AgentModel.objects.create(
            name="det-sub", parent_project=project, parent_agent=agent,
            manifest_dir="/tmp/det-sub",
        )
        Cronjob.objects.create(
            name="det-job", schedule="* * * * *", agent=agent,
            parent_project=project,
        )
        ws = WorkspaceModel.objects.create(name="det-ws", path="/tmp/det-a")
        rt = _make_ws_session(agent, av, ws, project=project)
        mod = _load_script(
            "agents/internal/agent_assistant/scripts/agent.py", "det_agent"
        )
        ok, info = mod.agent_details(rt)
        self.assertTrue(ok, info)
        self.assertEqual(info["status"], "success")
        self.assertEqual(info["name"], "det-a")
        self.assertEqual(info["path"], "/tmp/det-a")
        self.assertEqual(info["kind"], "root")
        self.assertEqual(info["skills_count"], 1)
        self.assertEqual(info["subagents_count"], 1)
        self.assertEqual(info["cronjobs_count"], 1)
        self.assertEqual(info["sessions_total"], 1)
        self.assertEqual(info["version_count"], 1)

    def test_skill_details(self):
        skill = _make_skill("det-s", manifest_dir="/tmp/det-s")
        SkillModel.objects.create(
            name="det-kid", parent_skill=skill, manifest_dir="/tmp/det-kid"
        )
        AgentModel.objects.create(
            name="det-owned", parent_skill=skill, manifest_dir="/tmp/det-owned"
        )
        agent, av = _make_agent("det-s-host")
        ws = WorkspaceModel.objects.create(name="det-s-ws", path="/tmp/det-s")
        rt = _make_ws_session(agent, av, ws)
        mod = _load_script(
            "agents/internal/skill_assistant/scripts/skill.py", "det_skill"
        )
        ok, info = mod.skill_details(rt)
        self.assertTrue(ok, info)
        self.assertEqual(info["status"], "success")
        self.assertEqual(info["name"], "det-s")
        self.assertEqual(info["child_skills_count"], 1)
        self.assertEqual(info["agents_count"], 1)
        self.assertEqual(info["total_loads"], 0)

    def test_cronjob_details(self):
        project = _make_project(path="/tmp/det-cron")
        agent, av = _make_agent("det-c-agent")
        Cronjob.objects.create(
            name="det-c-job", schedule="0 9 * * *", agent=agent,
            parent_project=project,
        )
        rt = _make_session(agent, av, name="det-c-rt", project=project)
        mod = _load_script(
            "agents/internal/cronjob_assistant/scripts/cronjob.py", "det_cron"
        )
        ok, info = mod.cronjob_details(rt, "det-c-job")
        self.assertTrue(ok, info)
        self.assertEqual(info["status"], "success")
        self.assertEqual(info["schedule"], "0 9 * * *")
        ok, err = mod.cronjob_details(rt, "missing-job")
        self.assertFalse(ok)
        self.assertEqual(err["status"], "error")

    def test_workitem_details_envelope(self):
        project = _make_project(path="/tmp/det-wi")
        item = WorkItem.objects.create(title="det-item", priority=10, project=project)
        agent, av = _make_agent("det-wi-host")
        rt = _make_session(agent, av, name="det-wi-rt", project=project)
        mod = _load_script(
            "agents/internal/workitem_assistant/scripts/workitem.py", "det_wi"
        )
        ok, info = mod.workitem_details(rt, item.pk)
        self.assertTrue(ok, info)
        self.assertEqual(info["status"], "success")
        self.assertEqual(info["item_status"], "backlog")
        ok, missing = mod.workitem_details(rt, 999999)
        self.assertFalse(ok)
        self.assertEqual(missing["status"], "error")

    def test_workspace_details(self):
        project = _make_project(path="/tmp/det-ws2")
        _make_agent("det-ws-agent", project=project)
        agent, av = _make_agent("det-ws-host")
        ws = WorkspaceModel.objects.create(
            name="det-ws2", path="/tmp/det-ws2", parent_project=project
        )
        WorkspaceModel.objects.create(
            name="det-ws-kid", path="/tmp/det-ws2/kid", parent_project=project
        )
        rt = _make_ws_session(agent, av, ws, project=project)
        mod = _load_script(
            "agents/internal/workspace_assistant/scripts/workspaces.py", "det_ws"
        )
        ok, info = mod.workspace_details(rt)
        self.assertTrue(ok, info)
        self.assertEqual(info["status"], "success")
        self.assertEqual(info["subworkspaces_count"], 1)
        self.assertEqual(info["sessions_total"], 1)
        self.assertEqual(info["agents_count"], 2)


class CreateToolsTest(TestCase):
    """create_agent / create_skill write valid manifests into scope dirs."""

    @staticmethod
    def _frontmatter(manifest: Path) -> dict:
        import yaml

        text = manifest.read_text()
        parts = text.split("---")
        return yaml.safe_load(parts[1])

    def test_create_agent_in_project(self):
        import shutil

        project = _make_project(name="create-proj", path="/tmp/create-proj")
        agent, av = _make_agent("create-host")
        rt = _make_session(agent, av, name="create-rt", project=project)
        mod = _load_script(
            "agents/internal/agents_assistant/scripts/agents.py", "create_agents"
        )
        ok, result = mod.create_agent(rt, "brand-new-agent", description="A test agent.")
        self.assertTrue(ok, result)
        manifest = Path(result["path"])
        self.assertTrue(manifest.name == "agent.md")
        self.assertTrue(str(manifest).startswith("/tmp/create-proj/"))
        self.assertEqual(self._frontmatter(manifest)["name"], "brand-new-agent")
        ok, dup = mod.create_agent(rt, "brand-new-agent")
        self.assertFalse(ok)
        self.assertIn("already exists", dup["message"])
        ok, bad = mod.create_agent(rt, "bad name!")
        self.assertFalse(ok)
        shutil.rmtree("/tmp/create-proj", ignore_errors=True)

    def test_create_skill_in_project(self):
        import shutil

        project = _make_project(name="create-sproj", path="/tmp/create-sproj")
        agent, av = _make_agent("create-s-host")
        rt = _make_session(agent, av, name="create-s-rt", project=project)
        mod = _load_script(
            "agents/internal/skills_assistant/scripts/skills.py", "create_skills"
        )
        ok, result = mod.create_skill(rt, "brand-new-skill", description="A test skill.")
        self.assertTrue(ok, result)
        manifest = Path(result["path"])
        self.assertTrue(str(manifest).startswith("/tmp/create-sproj/"))
        self.assertEqual(self._frontmatter(manifest)["name"], "brand-new-skill")
        ok, dup = mod.create_skill(rt, "brand-new-skill")
        self.assertFalse(ok)
        self.assertIn("already exists", dup["message"])
        ok, bad = mod.create_skill(rt, "")
        self.assertFalse(ok)
        shutil.rmtree("/tmp/create-sproj", ignore_errors=True)


class RenameToolsTest(TestCase):
    """Renamed tools keep their behavior under the new names."""

    def test_project_details(self):
        project = _make_project(name="ren-proj", path="/tmp/ren-proj")
        agent, av = _make_agent("ren-host")
        rt = _make_session(agent, av, name="ren-rt", project=project)
        mod = _load_script(
            "agents/internal/projects_assistant/scripts/projects.py", "ren_projects"
        )
        self.assertTrue(hasattr(mod, "project_details"))
        self.assertFalse(hasattr(mod, "describe_project"))
        ok, info = mod.project_details(rt, "ren-proj")
        self.assertTrue(ok, info)
        self.assertEqual(info["status"], "success")

    def test_edit_and_split_workitem(self):
        project = _make_project(path="/tmp/ren-wi")
        item = WorkItem.objects.create(title="ren-item", priority=10, project=project)
        agent, av = _make_agent("ren-wi-host")
        rt = _make_session(agent, av, name="ren-wi-rt", project=project)
        mod = _load_script(
            "agents/internal/workitem_assistant/scripts/workitem.py", "ren_wi"
        )
        self.assertTrue(hasattr(mod, "edit_workitem"))
        self.assertTrue(hasattr(mod, "create_child_workitem"))
        self.assertFalse(hasattr(mod, "update_workitem"))
        self.assertFalse(hasattr(mod, "add_child_workitem"))
        ok, info = mod.edit_workitem(rt, item.pk, title="renamed", status="ready")
        self.assertTrue(ok, info)
        self.assertEqual(info["status"], "success")
        self.assertEqual(info["item_status"], "ready")
        self.assertEqual(info["title"], "renamed")
        ok, child = mod.create_child_workitem(rt, item.pk, title="piece one")
        self.assertTrue(ok, child)
        self.assertEqual(child["status"], "success")
        self.assertEqual(child["item_status"], "ready")

    def test_create_workitem_envelope(self):
        project = _make_project(path="/tmp/ren-wc")
        agent, av = _make_agent("ren-wc-host")
        rt = _make_session(agent, av, name="ren-wc-rt", project=project)
        mod = _load_script(
            "agents/internal/workitems_assistant/scripts/workitems.py", "ren_wc"
        )
        ok, info = mod.create_workitem(rt, title="fresh item")
        self.assertTrue(ok, info)
        self.assertEqual(info["status"], "success")
        self.assertEqual(info["item_status"], "backlog")
