"""Tests for session-private storage (runtime/session_folder.py + guardrail carve-out)."""
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings

from runtime.session_folder import (
    cleanup_orphaned_session_folders,
    ensure_session_dir,
    get_sessions_base,
    parse_session_pk,
    session_dir,
)
from runtime.workspace_access import evaluate, resolve_policy
from server.models.sessions.session import SessionModel


class _Agent:
    def __init__(self, access=None):
        self._access = access

    def get_agent_setting(self, name):
        if name == "access" and self._access is not None:
            return self._access
        return None


class _Model:
    def __init__(self, pk):
        self.pk = pk


class _Session:
    def __init__(self, root, pk, access=None, agent_access=None):
        self.workspace = type(
            "WS", (), {"path": root.as_posix(), "access": access or {}}
        )()
        self.agent = _Agent(agent_access)
        self.model = _Model(pk)


class SessionFolderHelperTest(SimpleTestCase):
    def test_session_dir_is_pk_keyed(self):
        with tempfile.TemporaryDirectory() as td:
            with override_settings(AGENTONE_SESSIONS_DIR=td):
                self.assertEqual(session_dir(123), Path(td) / "agent" / "123")
                self.assertEqual(session_dir("456"), Path(td) / "agent" / "456")

    def test_ensure_creates_with_restricted_mode(self):
        with tempfile.TemporaryDirectory() as td:
            with override_settings(AGENTONE_SESSIONS_DIR=td):
                folder = ensure_session_dir(42)
                self.assertTrue(folder.is_dir())
                self.assertEqual(folder, Path(td) / "agent" / "42")
                # Second call is idempotent.
                self.assertEqual(ensure_session_dir(42), folder)

    def test_ensure_is_idempotent_when_exists(self):
        with tempfile.TemporaryDirectory() as td:
            with override_settings(AGENTONE_SESSIONS_DIR=td):
                (Path(td) / "agent" / "7").mkdir(parents=True)
                (Path(td) / "agent" / "7" / "note.md").write_text("hi")
                folder = ensure_session_dir(7)
                self.assertEqual((folder / "note.md").read_text(), "hi")

    def test_parse_session_pk(self):
        with tempfile.TemporaryDirectory() as td:
            with override_settings(AGENTONE_SESSIONS_DIR=td):
                self.assertEqual(parse_session_pk(str(Path(td) / "9" / "a.md")), "9")
                self.assertIsNone(parse_session_pk("/etc/hosts"))

    def test_get_sessions_base_default(self):
        base = get_sessions_base()
        self.assertTrue(str(base).endswith("sessions"))


class SessionFolderGuardrailTest(SimpleTestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.root = Path(self.td)
        self._override = override_settings(AGENTONE_SESSIONS_DIR=str(self.root / "sessions"))
        self._override.enable()
        self.addCleanup(self._override.disable)

    def _session(self, pk, access=None):
        return _Session(self.root, pk, access=access)

    def test_own_folder_allowed_despite_external_deny(self):
        policy = resolve_policy(self._session(11))
        own = str(Path(self.root / "sessions" / "agent" / "11" / "scratch.md"))
        self.assertEqual(evaluate(policy, own, "read").action, "allow")
        self.assertEqual(evaluate(policy, own, "write").action, "allow")

    def test_own_folder_allowed_despite_workspace_deny(self):
        policy = resolve_policy(
            self._session(11, access={"write": {"default": "deny"}, "read": {"default": "deny"}})
        )
        own = str(Path(self.root / "sessions" / "agent" / "11" / "a.md"))
        self.assertEqual(evaluate(policy, own, "write").action, "allow")
        self.assertEqual(evaluate(policy, own, "read").action, "allow")

    def test_other_session_denied(self):
        policy = resolve_policy(self._session(11))
        other = str(Path(self.root / "sessions" / "agent" / "22" / "a.md"))
        self.assertEqual(evaluate(policy, other, "read").action, "deny")
        self.assertEqual(evaluate(policy, other, "write").action, "deny")

    def test_base_dir_not_listable(self):
        policy = resolve_policy(self._session(11))
        base = str(Path(self.root / "sessions"))
        self.assertEqual(evaluate(policy, base, "read").action, "deny")

    def test_explicit_global_deny_still_wins_over_own(self):
        base = get_sessions_base().as_posix()
        policy = resolve_policy(
            self._session(11, access={"read": {"default": "allow", "deny": [f"{base}/**"]}})
        )
        own = str(Path(base) / "agent" / "11" / "a.md")
        self.assertEqual(evaluate(policy, own, "read").action, "deny")

    def test_no_workspace_still_isolates_other_sessions(self):
        class NoWS:
            workspace = None
            agent = _Agent()
            model = _Model(11)

        policy = resolve_policy(NoWS())
        self.assertEqual(
            evaluate(policy, str(Path(self.root / "sessions" / "agent" / "11" / "a.md")), "write").action,
            "allow",
        )
        self.assertEqual(
            evaluate(policy, str(Path(self.root / "sessions" / "agent" / "99" / "a.md")), "read").action,
            "deny",
        )
        # Unrelated paths keep the legacy allow-all behaviour.
        self.assertEqual(evaluate(policy, "/etc/hosts", "read").action, "allow")

    def test_unknown_pk_no_carveout(self):
        policy = resolve_policy(self._session(None))
        other = str(Path(self.root / "sessions" / "agent" / "22" / "a.md"))
        # No carve-out without a known pk — falls through to the normal
        # inside-workspace default (allow here, since the temp sessions base
        # sits inside the temp workspace root).
        self.assertEqual(evaluate(policy, other, "read").action, "allow")


class SessionFolderCleanupTest(TestCase):
    def test_cleanup_removes_only_orphans(self):
        with tempfile.TemporaryDirectory() as td:
            with override_settings(AGENTONE_SESSIONS_DIR=td):
                session = SessionModel.objects.create(name="privtest")
                keep = ensure_session_dir(session.pk)
                (keep / "note.md").write_text("keep")
                orphan = Path(td) / "999999999"
                orphan.mkdir()
                (orphan / "x.md").write_text("orphan")
                ignoreme = Path(td) / "not-a-pk"
                ignoreme.mkdir()
                removed = cleanup_orphaned_session_folders()
                self.assertEqual(removed, 1)
                self.assertTrue(keep.is_dir())
                self.assertFalse(orphan.exists())
                self.assertTrue(ignoreme.is_dir())

    def test_cleanup_keeps_archived_sessions(self):
        with tempfile.TemporaryDirectory() as td:
            with override_settings(AGENTONE_SESSIONS_DIR=td):
                session = SessionModel.objects.create(name="archived", is_archived=True)
                folder = ensure_session_dir(session.pk)
                self.assertEqual(cleanup_orphaned_session_folders(), 0)
                self.assertTrue(folder.is_dir())


class RuntimeSessionPrivateDirTest(TestCase):
    def test_private_dir_matches_session_folder(self):
        with tempfile.TemporaryDirectory() as td:
            with override_settings(AGENTONE_SESSIONS_DIR=td):
                session = SessionModel.objects.create(name="privdir")
                runtime = session.get_runtime()
                self.assertEqual(runtime.private_dir, session_dir(session))
                folder = runtime.ensure_private_dir()
                self.assertTrue(folder.is_dir())
