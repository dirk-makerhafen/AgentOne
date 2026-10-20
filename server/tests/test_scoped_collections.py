"""Tests for parent-scoped runtime collections and assistant wiring.

Each plural collection takes explicit parent kwargs and scopes ``all()``
accordingly; ``root()`` stays unscoped for UI callers; ``list_*()``
returns wrapped singular objects; ``get_source_dir()`` is pure path
resolution (stored ``manifest_dir`` first, conventional layout fallback);
``get_assistant_session()`` spawns the bound singleton.
"""

import importlib.util
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
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
# (ScriptParityTest intentionally exercises the scripts' private helpers.)


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

    def test_agent_workspace_is_source_dir(self):
        from runtime.agents.agent import Agent as AgentRt

        agent, _av = _make_agent("aw-a", manifest_dir="/tmp/aw-a")
        ws = AgentRt(agent_model=agent).get_assistant_workspace()
        self.assertEqual(ws.path, "/tmp/aw-a")

    def test_skill_workspace_is_source_dir(self):
        from runtime.skill.skill import Skill as SkillRt

        skill = _make_skill("aw-s", manifest_dir="/tmp/aw-s")
        ws = SkillRt(skill_model=skill).get_assistant_workspace()
        self.assertEqual(ws.path, "/tmp/aw-s")

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

    def test_global_system_rows(self):
        from runtime.agents.agents import Agents
        from runtime.cron.crons import Cronjobs
        from runtime.project.projects import Projects
        from runtime.skill.skills import Skills
        from runtime.workitems.workitems import Workitems
        from runtime.workspace.workspaces import Workspaces

        self.assertEqual(Agents().get_assistant_workspace().pk, Agents().get_assistant_workspace().pk)
        self.assertTrue(Skills().get_assistant_workspace().path.endswith("skills"))
        self.assertTrue(Cronjobs().get_assistant_workspace().path.endswith("cronjobs"))
        self.assertTrue(Workspaces().get_assistant_workspace() is not None)
        self.assertEqual(
            Projects().get_assistant_workspace().name, "AgentOne system"
        )
        self.assertEqual(
            Workitems().get_assistant_workspace().name, "AgentOne system"
        )

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
        self.assertEqual(first.model.name, "skills_assistant - global")
        self.assertEqual(first.model.group_key, "assistant:skills_assistant")
        self.assertIsNone(first.model.parent_project)

    def test_project_scope_binds_project(self):
        project = _make_project(name="as-proj", path="/tmp/as-proj")
        child = Skills(parent_project=project).get_assistant_session(caller=self.rt)
        self.assertIsNotNone(child)
        self.assertEqual(child.model.parent_project_id, project.pk)
        self.assertEqual(child.model.name, "skills_assistant - as-proj")

    def test_singular_name_override(self):
        _make_agent("skill_assistant")
        child = Skills().get_assistant_session(
            caller=self.rt, name="skill_assistant"
        )
        self.assertIsNotNone(child)
        self.assertEqual(child.model.name, "skill_assistant - global")

    def test_singular_item_label(self):
        _make_agent("agent_assistant")
        agent, _av = _make_agent("labelled-agent")
        from runtime.agents.agent import Agent

        child = Agent(agent).get_assistant_session(caller=self.rt)
        self.assertIsNotNone(child)
        self.assertEqual(child.model.name, "agent_assistant - labelled-agent")

    def test_owner_scoped_label(self):
        agent, _av = _make_agent("owner-agent")
        child = Skills(parent_agent=agent).get_assistant_session(caller=self.rt)
        self.assertIsNotNone(child)
        self.assertEqual(child.model.name, "skills_assistant - agent owner-agent")

    def test_callerless_creation(self):
        child = Skills().get_assistant_session()
        self.assertIsNotNone(child)
        self.assertEqual(child.model.name, "skills_assistant - global")
        self.assertEqual(child.model.group_key, "assistant:skills_assistant")

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
            "agents/internal/workspace_assistant/scripts/workspace.py", "sub_ws"
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
        ws = WorkspaceModel.objects.create(
            name="ext-ws", path="/tmp/ext-ws", parent_project=project
        )
        _make_ws_session(agent, av, ws, name="ext-bound", project=project)
        ok, wresult = ws_mod.list_workspaces(rt)
        self.assertTrue(ok, wresult)
        self.assertIn("scope", wresult)
        wrow = next(w for w in wresult["workspaces"] if w["name"] == "ext-ws")
        self.assertEqual(wrow["session_count"], 1)


class WorkspaceAssistantScopeTest(TestCase):
    """Workspace collection tools follow the session scope."""

    def _module(self):
        return _load_script(
            "agents/internal/workspaces_assistant/scripts/workspaces.py",
            "scope_workspaces",
        )

    def test_list_workspaces_project_scope(self):
        project = _make_project(path="")
        WorkspaceModel.objects.create(name="owned", path="/tmp/owned", parent_project=project)
        WorkspaceModel.objects.create(name="global", path="/tmp/global")
        agent, av = _make_agent("scope-list-host")
        rt = _make_session(agent, av, name="scope-list", project=project)

        ok, result = self._module().list_workspaces(rt)
        self.assertTrue(ok, result)
        self.assertEqual([w["name"] for w in result["workspaces"]], ["owned"])
        self.assertEqual(result["scope"], "project p")
        self.assertTrue(result["workspaces"][0]["top_level"])

    def test_list_workspaces_global_scope(self):
        project = _make_project(path="")
        WorkspaceModel.objects.create(name="owned", path="/tmp/owned", parent_project=project)
        WorkspaceModel.objects.create(name="global", path="/tmp/global")
        agent, av = _make_agent("scope-list-global-host")
        rt = _make_session(agent, av, name="scope-list-global")

        ok, result = self._module().list_workspaces(rt)
        self.assertTrue(ok, result)
        self.assertEqual(result["scope"], "global")
        self.assertEqual(
            sorted(w["name"] for w in result["workspaces"]), ["global", "owned"]
        )

    def test_create_workspace_stamps_project(self):
        project = _make_project(path="")
        agent, av = _make_agent("scope-create-host")
        rt = _make_session(agent, av, name="scope-create", project=project)
        tmp = tempfile.mkdtemp()

        ok, result = self._module().create_workspace(rt, "created", tmp)
        self.assertTrue(ok, result)
        self.assertTrue(result["created"])
        self.assertEqual(result["project_pk"], project.pk)
        self.assertEqual(
            WorkspaceModel.objects.get(name="created").parent_project_id, project.pk
        )

        global_rt = _make_session(agent, av, name="scope-create-global")
        other = tempfile.mkdtemp()
        ok, result = self._module().create_workspace(global_rt, "global-created", other)
        self.assertTrue(ok, result)
        self.assertIsNone(result["project_pk"])

    def test_create_workspace_adopts_unowned_row(self):
        project = _make_project(path="")
        tmp = tempfile.mkdtemp()
        ws = WorkspaceModel.objects.create(
            name="preexisting", path=os.path.realpath(tmp)
        )
        agent, av = _make_agent("scope-adopt-host")
        rt = _make_session(agent, av, name="scope-adopt", project=project)

        ok, result = self._module().create_workspace(rt, "preexisting", tmp)
        self.assertTrue(ok, result)
        self.assertFalse(result["created"])
        self.assertTrue(result["adopted"])
        ws.refresh_from_db()
        self.assertEqual(ws.parent_project_id, project.pk)

    def test_workspaces_stats_project_scope(self):
        project = _make_project(path="")
        root = tempfile.mkdtemp()
        child = str(Path(root) / "child")
        WorkspaceModel.objects.create(name="root", path=root, parent_project=project)
        WorkspaceModel.objects.create(name="child", path=child, parent_project=project)
        WorkspaceModel.objects.create(name="global", path="/tmp/global-stats")
        agent, av = _make_agent("scope-stats-host")
        rt = _make_session(agent, av, name="scope-stats", project=project)

        ok, result = self._module().workspaces_stats(rt)
        self.assertTrue(ok, result)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["top_level"], 1)
        self.assertEqual(result["nested"], 1)
        self.assertEqual(result["scope"], "project p")

    def test_create_subworkspace_inherits_project(self):
        project = _make_project(path="")
        root = tempfile.mkdtemp()
        managed = WorkspaceModel.objects.create(name="managed", path=root, parent_project=project)
        agent, av = _make_agent("scope-subws-host")
        rt = _make_ws_session(agent, av, managed, name="scope-subws")
        child = str(Path(root) / "child")

        mod = _load_script(
            "agents/internal/workspace_assistant/scripts/workspace.py",
            "scope_sub_workspaces",
        )
        ok, result = mod.create_subworkspace(rt, "child", child)
        self.assertTrue(ok, result)
        self.assertTrue(result["created"])
        self.assertEqual(result["project_pk"], project.pk)
        self.assertEqual(
            WorkspaceModel.objects.get(name="child").parent_project_id,
            project.pk,
        )

    def test_workspace_assistant_cronjobs_use_workspace_project(self):
        project = _make_project(path="")
        root = tempfile.mkdtemp()
        managed = WorkspaceModel.objects.create(name="managed", path=root, parent_project=project)
        agent, av = _make_agent("scope-cron-host")
        Cronjob.objects.create(
            name="project-job", schedule="* * * * *", agent=agent,
            parent_project=project,
        )
        Cronjob.objects.create(
            name="global-job", schedule="* * * * *", agent=agent,
        )
        rt = _make_ws_session(agent, av, managed, name="scope-cron")

        mod = _load_script(
            "agents/internal/workspace_assistant/scripts/workspace.py",
            "scope_cron_workspaces",
        )
        ok, result = mod.list_cronjobs(rt)
        self.assertTrue(ok, result)
        self.assertEqual([j["name"] for j in result["cronjobs"]], ["project-job"])
        ok, details = mod.workspace_details(rt)
        self.assertTrue(ok, details)
        self.assertEqual(details["cronjobs_count"], 1)

    def test_assistant_session_derives_project_from_workspace(self):
        project = _make_project()
        _make_agent("workspaces_assistant")
        workspace = WorkspaceModel.objects.create(
            name="derived-ws", path="/tmp/derived-ws", parent_project=project
        )

        runtime_session = Sessions().assistant_session(
            "workspaces_assistant", workspace=workspace, project=None
        )
        self.assertIsNotNone(runtime_session)
        self.assertEqual(runtime_session.model.parent_project_id, project.pk)
        self.assertEqual(
            runtime_session.model.name, "workspaces_assistant - p"
        )

    def test_call_assistant_binds_callers_workspace(self):
        project = _make_project(path="")
        root = tempfile.mkdtemp()
        _make_agent("workspaces_assistant")
        caller_ws = WorkspaceModel.objects.create(
            name="caller-ws", path=root, parent_project=project
        )
        agent, av = _make_agent("call-assistant-host")
        rt = _make_ws_session(
            agent, av, caller_ws, name="call-assistant-source", project=project
        )
        captured = {}

        def _fake_assistant_session(_self, name, **kwargs):
            captured.update({"name": name, **kwargs})
            return SimpleNamespace()

        mod = _load_script(
            "scripts/subagents/call_assistant.py", "scope_call_assistant"
        )
        with patch(
            "runtime.session.sessions.Sessions.assistant_session",
            _fake_assistant_session,
        ), patch.object(mod, "_send", lambda *args: {"ok": True}):
            result = mod.call_assistant(rt, "workspace_assistant", "do it")

        self.assertEqual(result, {"ok": True})
        self.assertEqual(captured["workspace"].pk, caller_ws.pk)
        self.assertEqual(captured["project"].pk, project.pk)


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
            "agents/internal/workspace_assistant/scripts/workspace.py", "det_ws"
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
