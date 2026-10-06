"""Tests for database-backed ad-hoc tools (runtime/adhoc_tools.py).

Mirrors the structure of server/tests/test_query_templates.py: pure
validation in SimpleTestCase, DB behavior in TestCase with real
SessionModel rows.
"""
import json
import tempfile

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase, override_settings

from runtime import adhoc_tools as adhoc
from runtime.adhoc_tools import (
    inherit_adhoc_tools,
    validate_params_against_schema,
    validate_params_schema,
    validate_tool_name,
)
from server.models import SessionModel
from server.models.adhoc_tool import AdhocToolVersion, SessionAdhocTool


GOOD_SOURCE = """\
def run(params):
    text = params.get("text", "")
    return {"length": len(text), "upper": text.upper()}
"""

SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
}


class _Agent:
    def get_agent_setting(self, name):
        return None


class _Stub:
    """Duck-typed session wrapper around a real SessionModel row."""

    def __init__(self, model, root):
        self.model = model
        self.workspace = type("WS", (), {"path": root, "access": {}})()
        self.agent = _Agent()


class NameValidationTest(SimpleTestCase):
    def test_bad_names_rejected(self):
        for bad in ["AB", "has space", "HasUpper", "1abc", "a" * 50, "", None]:
            self.assertIsNotNone(validate_tool_name(bad), bad)

    def test_good_names_accepted(self):
        for good in ["abc", "wordstats", "headline_parser", "tool_01"]:
            self.assertIsNone(validate_tool_name(good), good)


class SchemaValidationTest(SimpleTestCase):
    def test_valid_schemas(self):
        self.assertIsNone(validate_params_schema(None))
        self.assertIsNone(validate_params_schema(SCHEMA))

    def test_bad_schemas(self):
        self.assertIsNotNone(validate_params_schema("nope"))
        self.assertIsNotNone(validate_params_schema({"type": "array"}))
        self.assertIsNotNone(
            validate_params_schema(
                {"type": "object", "properties": {"x": {"type": "weird"}}}
            )
        )

    def test_enforcement(self):
        self.assertIsNone(validate_params_against_schema({"text": "hi"}, SCHEMA))
        self.assertIn("required", validate_params_against_schema({}, SCHEMA))
        self.assertIn("must be string",
                      validate_params_against_schema({"text": 1}, SCHEMA))


class LifecycleTest(TestCase):
    def setUp(self):
        self.session = SessionModel.objects.create(name="adhoc-s1")
        self.stub = _Stub(self.session, tempfile.gettempdir())

    def test_create_list_read_call_update_delete(self):
        ok, res = adhoc.create_adhoc_tool(
            self.stub, "wordstats", GOOD_SOURCE, "counts words", SCHEMA)
        self.assertTrue(ok, res)
        v1 = res["version"]
        self.assertIsInstance(v1, int)

        ok, res = adhoc.list_adhoc_tools(self.stub)
        self.assertTrue(ok)
        self.assertEqual(len(res["tools"]), 1)
        entry = res["tools"][0]
        self.assertEqual(entry["name"], "wordstats")
        self.assertEqual(entry["version"], v1)
        self.assertNotIn("source", entry)

        ok, res = adhoc.read_adhoc_tool(self.stub, "wordstats")
        self.assertTrue(ok)
        self.assertIn("def run", res["source"])
        self.assertEqual(res["meta"]["params_schema"], SCHEMA)

        ok, res = adhoc.call_adhoc_tool(self.stub, "wordstats", {"text": "hi"})
        self.assertTrue(ok, res)
        self.assertEqual(res["length"], 2)
        self.assertEqual(res["upper"], "HI")

        ok, res = adhoc.update_adhoc_tool(
            self.stub, "wordstats", description="new desc")
        self.assertTrue(ok, res)
        self.assertNotEqual(res["version"], v1)  # meta-only change still mints

        ok, res = adhoc.delete_adhoc_tool(self.stub, "wordstats")
        self.assertTrue(ok)
        ok, res = adhoc.list_adhoc_tools(self.stub)
        self.assertEqual(res["tools"], [])

    def test_duplicate_create_rejected(self):
        ok, _ = adhoc.create_adhoc_tool(self.stub, "dup", GOOD_SOURCE)
        self.assertTrue(ok)
        ok, res = adhoc.create_adhoc_tool(self.stub, "dup", GOOD_SOURCE)
        self.assertFalse(ok)
        self.assertIn("already exists", res["message"])

    def test_update_missing_rejected(self):
        ok, res = adhoc.update_adhoc_tool(self.stub, "ghost", GOOD_SOURCE)
        self.assertFalse(ok)
        self.assertIn("adhoc_create", res["message"])

    def test_call_missing(self):
        ok, res = adhoc.call_adhoc_tool(self.stub, "nope", {})
        self.assertFalse(ok)
        self.assertIn("No ad-hoc tool", res["message"])

    def test_missing_run_rejected(self):
        ok, res = adhoc.create_adhoc_tool(self.stub, "norun", "x = 1\n")
        self.assertFalse(ok)
        self.assertIn("def run", res["message"])

    def test_identical_update_is_noop(self):
        ok, res = adhoc.create_adhoc_tool(self.stub, "same", GOOD_SOURCE)
        v1 = res["version"]
        before = AdhocToolVersion.objects.count()
        ok, res = adhoc.update_adhoc_tool(self.stub, "same", GOOD_SOURCE)
        self.assertTrue(ok)
        self.assertEqual(res["version"], v1)
        self.assertTrue(res.get("unchanged"))
        self.assertEqual(AdhocToolVersion.objects.count(), before)

    def test_content_dedupes_across_sessions(self):
        other = SessionModel.objects.create(name="adhoc-s2")
        adhoc.create_adhoc_tool(self.stub, "shared", GOOD_SOURCE)
        adhoc.create_adhoc_tool(_Stub(other, tempfile.gettempdir()),
                                "shared", GOOD_SOURCE)
        from server.models.content import GenericContent
        self.assertEqual(GenericContent.objects.count(), 1)

    def test_tool_limit(self):
        for i in range(adhoc.MAX_ADHOC_TOOLS):
            ok, res = adhoc.create_adhoc_tool(self.stub, f"tool_{i:02d}", GOOD_SOURCE)
            self.assertTrue(ok, res)
        ok, res = adhoc.create_adhoc_tool(self.stub, "one_more", GOOD_SOURCE)
        self.assertFalse(ok)
        self.assertIn("limit", res["message"].lower())

    def test_source_size_cap(self):
        big = "def run(params):\n    return {}\n" + "#" * adhoc.MAX_SOURCE_BYTES
        ok, res = adhoc.create_adhoc_tool(self.stub, "big", big)
        self.assertFalse(ok)
        self.assertIn("exceeds", res["message"])

    def test_stringified_args_accepted(self):
        adhoc.create_adhoc_tool(self.stub, "strschema", GOOD_SOURCE,
                                params_schema=json.dumps(SCHEMA))
        ok, res = adhoc.read_adhoc_tool(self.stub, "strschema")
        self.assertTrue(ok)
        self.assertEqual(res["meta"]["params_schema"], SCHEMA)
        ok, res = adhoc.call_adhoc_tool(self.stub, "strschema",
                                        json.dumps({"text": "hey"}))
        self.assertTrue(ok, res)
        self.assertEqual(res["upper"], "HEY")

    def test_delete_keeps_versions_for_audit(self):
        ok, res = adhoc.create_adhoc_tool(self.stub, "audit", GOOD_SOURCE)
        v1 = res["version"]
        adhoc.delete_adhoc_tool(self.stub, "audit")
        self.assertTrue(AdhocToolVersion.objects.filter(pk=v1).exists())
        lineage = AdhocToolVersion.objects.filter(name="audit")
        self.assertEqual(lineage.count(), 1)
        self.assertEqual(lineage.first().created_by_session_id, self.session.pk)

    def test_version_rows_immutable(self):
        ok, res = adhoc.create_adhoc_tool(self.stub, "frozen", GOOD_SOURCE)
        version = AdhocToolVersion.objects.get(pk=res["version"])
        version.description = "mutate"
        with self.assertRaises(ValidationError):
            version.save()

    def test_linked_version_protected(self):
        ok, res = adhoc.create_adhoc_tool(self.stub, "prot", GOOD_SOURCE)
        version = AdhocToolVersion.objects.get(pk=res["version"])
        with self.assertRaises(ProtectedError):
            version.delete()

    def test_call_exception_reported(self):
        ok, _ = adhoc.create_adhoc_tool(
            self.stub, "boom", "def run(params):\n    raise ValueError('kaput')\n")
        self.assertTrue(ok)
        ok, res = adhoc.call_adhoc_tool(self.stub, "boom", {})
        self.assertFalse(ok)
        self.assertIn("kaput", res.get("stderr", ""))


class GuardrailTest(TestCase):
    def setUp(self):
        self.stub = _Stub(SessionModel.objects.create(name="adhoc-g"),
                           tempfile.gettempdir())

    def test_eval_blocked_at_create(self):
        ok, res = adhoc.create_adhoc_tool(
            self.stub, "evlx", "def run(params):\n    return eval('1')\n")
        self.assertFalse(ok)
        self.assertIn("guardrail", res["message"].lower())

    def test_shell_out_blocked_at_create(self):
        ok, res = adhoc.create_adhoc_tool(
            self.stub, "shlx", "import os\ndef run(params):\n    os.system('ls')\n    return {}\n")
        self.assertFalse(ok)
        self.assertIn("guardrail", res["message"].lower())

    def test_cross_session_reference_blocked(self):
        src = ("def run(params):\n"
               "    p = '/x/.agentone/sessions/999/adhoc_tools/a.py'\n"
               "    return {'p': p}\n")
        ok, res = adhoc.create_adhoc_tool(self.stub, "xray", src)
        self.assertFalse(ok)
        self.assertIn("another session", res["message"].lower())


class ArchiveTest(TestCase):
    def test_archived_sessions_keep_full_access(self):
        """Archive is a visibility state, not a freeze: nothing else in the
        runtime refuses writes on archived sessions (messages, turns, files,
        templates all keep working), so ad-hoc tools must not either."""
        archived = SessionModel.objects.create(name="adhoc-archived",
                                               is_archived=True)
        stub = _Stub(archived, tempfile.gettempdir())
        ok, res = adhoc.create_adhoc_tool(stub, "keep", GOOD_SOURCE)
        self.assertTrue(ok, res)
        ok, res = adhoc.call_adhoc_tool(stub, "keep", {"text": "hi"})
        self.assertTrue(ok, res)
        self.assertEqual(res["upper"], "HI")
        ok, res = adhoc.update_adhoc_tool(stub, "keep", description="edit")
        self.assertTrue(ok, res)
        ok, res = adhoc.delete_adhoc_tool(stub, "keep")
        self.assertTrue(ok, res)
        self.assertEqual(adhoc.list_adhoc_tools(stub)[1]["tools"], [])


class ForkTest(TestCase):
    """Forks inherit links; later saves diverge (copy-on-write)."""

    def setUp(self):
        self.parent = SessionModel.objects.create(name="adhoc-parent")
        self.child = SessionModel.objects.create(name="adhoc-child")
        adhoc.create_adhoc_tool(_Stub(self.parent, tempfile.gettempdir()),
                                "helper", GOOD_SOURCE)

    def test_inherit_copies_links_without_minting(self):
        before = AdhocToolVersion.objects.count()
        self.assertEqual(inherit_adhoc_tools(self.parent.pk, self.child.pk), 1)
        self.assertEqual(AdhocToolVersion.objects.count(), before)
        child_links = SessionAdhocTool.objects.filter(session_id=self.child.pk)
        self.assertEqual([l.name for l in child_links], ["helper"])
        self.assertEqual(
            child_links[0].version_id,
            SessionAdhocTool.objects.get(
                session_id=self.parent.pk, name="helper").version_id,
        )

    def test_fork_edit_does_not_move_parent_link(self):
        inherit_adhoc_tools(self.parent.pk, self.child.pk)
        child_stub = _Stub(self.child, tempfile.gettempdir())
        ok, res = adhoc.update_adhoc_tool(
            child_stub, "helper", GOOD_SOURCE.replace("len(text)", "len(text) + 1"))
        self.assertTrue(ok)
        parent_src = adhoc.read_adhoc_tool(
            _Stub(self.parent, tempfile.gettempdir()), "helper")[1]["source"]
        self.assertIn("len(text),", parent_src)
        self.assertEqual(
            AdhocToolVersion.objects.filter(name="helper").count(), 2)

    def test_inherit_empty_parent_returns_zero(self):
        orphan = SessionModel.objects.create(name="adhoc-orphan")
        self.assertEqual(inherit_adhoc_tools(orphan.pk, self.child.pk), 0)


class ForkHookTest(TestCase):
    """get_or_create_session copies adhoc links for new forks only."""

    def setUp(self):
        from server.models.agents.agent import AgentModel
        from server.models.agents.agent_version import AgentVersionModel
        from server.models.sessions.session_version import SessionVersionModel

        self.agent = AgentModel.objects.create(name="adhoc_hook_agent")
        self.av = AgentVersionModel.objects.create(agent=self.agent, version_number=1)
        self.parent_session = SessionModel.objects.create(name="adhoc-hook-parent")
        self.parent_sv = SessionVersionModel.objects.create(
            session=self.parent_session, agent=self.agent, version_number=1
        )
        adhoc.create_adhoc_tool(
            _Stub(self.parent_session, tempfile.gettempdir()),
            "hooked", GOOD_SOURCE)

    def test_new_fork_inherits_links(self):
        child_sv = self.av.get_or_create_session(
            name="adhoc-hook-child", parent_session_version=self.parent_sv
        )
        ok, res = adhoc.list_adhoc_tools(
            _Stub(child_sv.session, tempfile.gettempdir()))
        self.assertTrue(ok)
        self.assertEqual([t["name"] for t in res["tools"]], ["hooked"])

    def test_fork_edit_does_not_move_parent_link(self):
        child_sv = self.av.get_or_create_session(
            name="adhoc-hook-child2", parent_session_version=self.parent_sv
        )
        child_stub = _Stub(child_sv.session, tempfile.gettempdir())
        adhoc.update_adhoc_tool(child_stub, "hooked", description="child edit")
        parent_names = [
            t["description"] for t in
            adhoc.list_adhoc_tools(
                _Stub(self.parent_session, tempfile.gettempdir()))[1]["tools"]
        ]
        self.assertEqual(parent_names, [""])

    def test_existing_session_keeps_own_links(self):
        child_sv = self.av.get_or_create_session(
            name="adhoc-hook-child3", parent_session_version=self.parent_sv
        )
        child_stub = _Stub(child_sv.session, tempfile.gettempdir())
        adhoc.delete_adhoc_tool(child_stub, "hooked")
        same_sv = self.av.get_or_create_session(
            name="adhoc-hook-child3", parent_session_version=self.parent_sv
        )
        ok, res = adhoc.list_adhoc_tools(
            _Stub(same_sv.session, tempfile.gettempdir()))
        self.assertTrue(ok)
        self.assertEqual(res["tools"], [])


class UniqueBindingTest(TestCase):
    def test_duplicate_binding_rejected_at_db_level(self):
        s = SessionModel.objects.create(name="adhoc-uq")
        stub = _Stub(s, tempfile.gettempdir())
        ok, res = adhoc.create_adhoc_tool(stub, "uni", GOOD_SOURCE)
        self.assertTrue(ok)
        version = AdhocToolVersion.objects.get(pk=res["version"])
        with self.assertRaises(IntegrityError):
            SessionAdhocTool.objects.create(
                session_id=s.pk, name="uni", version=version)
