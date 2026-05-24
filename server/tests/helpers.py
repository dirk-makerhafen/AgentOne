import shutil
import tempfile
from pathlib import Path
from registry.install_repo import InstallRepo
from registry.loader.load_agent_manifest import load_agent_manifest
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.enums.task_enums import TaskType
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel

from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion


TESTPROJECT = Path(__file__).parent / "testproject" / ".agentone"


def create_global_task(name: str, group_name: str = "", task_type: str = TaskType.TOOL) -> TaskDefinition:
    """Create a global TaskDefinition + TaskDefinitionVersion pair.

    ``parent_agent`` / ``parent_project`` / ``parent_skill`` are all left
    NULL so the loader finds them as global fallback.
    """
    td = TaskDefinition.objects.create(name=name, group_name=group_name)
    tdv = TaskDefinitionVersion.objects.create(
        task_definition=td,
        description="test",
        function_schema={"type": "object", "properties": {}},
        task_type=task_type,
    )
    TaskDefinition.objects.filter(pk=td.pk).update(latest_task_version=tdv)
    return td


def create_global_taskdef_version(
    name: str, group_name: str = "", task_type: str = TaskType.TOOL
) -> TaskDefinitionVersion:
    """Create a global TDV and return it directly (not the TaskDefinition)."""
    td = create_global_task(name, group_name, task_type)
    return td.latest_task_version


class AgentMdTestMixin:
    """Mixin for test classes that load agents from ``testproject/``.

    Sets up a temp ``InstallRepo`` (isolated from ``~/.agentone/install/``),
    creates standard global ``TaskDefinition`` + ``TaskDefinitionVersion``
    fixtures, and provides ``_load_agent()`` to run the real loader pipeline.
    """

    _tmpdir: Path
    _install_repo: InstallRepo

    # ------------------------------------------------------------------
    # Class-level helpers  (call inside ``setUpTestData``)
    # ------------------------------------------------------------------

    @classmethod
    def setup_global_tasks(cls) -> None:
        """Create global tasks that the testproject agents reference.

        Tools: fs.read, fs.write, fs.delete, fs.tree, compiler.build
        Tasks: core.core_task
        Commands: ping
        """
        for name, group in [
            ("read", "fs"),
            ("write", "fs"),
            ("delete", "fs"),
            ("build", "compiler"),
            ("tree", "fs"),
        ]:
            create_global_task(name, group, TaskType.TOOL)
        create_global_task("core_task", "core", TaskType.TASK)
        for name in ["ping", "pong"]:
            create_global_task(name, "", TaskType.COMMAND)

    @classmethod
    def setup_install_repo(cls) -> None:
        """Create a temporary install repo and sync the testproject into it."""
        cls._tmpdir = Path(tempfile.mkdtemp())
        cls._install_repo = InstallRepo(repo_path=cls._tmpdir / "install")
        cls._install_repo.source_root = TESTPROJECT
        cls._install_repo.sync()

    @classmethod
    def load_agent(cls, name: str) -> tuple[AgentModel, AgentVersionModel]:
        """Load an agent from ``testproject/.agentone/agents/{name}/agent.md``.

        Runs the REAL ``load_agent_manifest`` against the temp install repo.
        Returns ``(AgentModel, AgentVersionModel)`` — the agent model is
        refreshed from DB so that ``latest_agent_version`` is current.
        """
        path = TESTPROJECT / "agents" / name / "agent.md"
        agent, av = load_agent_manifest(path, install_repo=cls._install_repo)
        agent.refresh_from_db()
        av.refresh_from_db()
        return agent, av

    @classmethod
    def teardown_install_repo(cls) -> None:
        """Clean up the temp install repo directory."""
        if hasattr(cls, "_tmpdir"):
            shutil.rmtree(cls._tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Session helpers  (used in per-test assertions)
    # ------------------------------------------------------------------

    @staticmethod
    def create_session(
        agent_model: AgentModel,
        agent_version: AgentVersionModel,
        session_settings: SettingsModel | None = None,
    ) -> SessionModel:
        """Create a real ``SessionModel`` + ``SessionVersionModel``.

        The session is wired to *agent_model* and the version's
        ``session_settings`` (if provided).  The runtime ``Session`` wrapper
        can be obtained via ``session.get_runtime()``.
        """
        session = SessionModel.objects.create(name="test_session")
        sv = SessionVersionModel.objects.create(
            session=session,
            agent=agent_model,
            pinned_agent_version=agent_version,
            version_number=1,
            session_settings=session_settings,
        )
        SessionModel.objects.filter(pk=session.pk).update(
            latest_session_version=sv
        )
        session.refresh_from_db()
        return session
