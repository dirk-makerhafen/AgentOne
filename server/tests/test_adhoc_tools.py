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
def run(text: str = ""):
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
        self.tools = {}

    def get_tool(self, name):
        return self.tools.get(name)


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

    def test_coerce_error_names_position(self):
        _, err = adhoc._coerce_dict_arg('{"a": 1}}', "params")
        self.assertIn("char", err)
        self.assertIn("native", err)


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
        self.assertEqual(res["result"]["length"], 2)
        self.assertEqual(res["result"]["upper"], "HI")

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
        big = "def run():\n    return {}\n" + "#" * adhoc.MAX_SOURCE_BYTES
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
        self.assertEqual(res["result"]["upper"], "HEY")

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
            self.stub, "boom", "def run():\n    raise ValueError('kaput')\n")
        self.assertTrue(ok)
        ok, res = adhoc.call_adhoc_tool(self.stub, "boom", {})
        self.assertFalse(ok)
        self.assertIn("kaput", res.get("stderr", ""))


class InferenceTest(SimpleTestCase):
    def test_typed_signature_inferred(self):
        schema = adhoc.infer_params_schema(
            "def run(text: str, limit: int = 10):\n    return text\n")
        self.assertEqual(schema, {
            "type": "object",
            "properties": {"text": {"type": "string"},
                           "limit": {"type": "integer"}},
            "required": ["text"],
        })

    def test_single_params_arg_is_a_normal_property(self):
        schema = adhoc.infer_params_schema(
            "def run(params):\n    return params\n")
        self.assertEqual(schema, {
            "type": "object",
            "properties": {"params": {"type": "string"}},
            "required": ["params"],
        })

    def test_zero_arg_gives_empty_schema(self):
        self.assertEqual(
            adhoc.infer_params_schema("def run():\n    return 1\n"),
            {"type": "object", "properties": {}, "required": []})

    def test_annotations_mapped(self):
        schema = adhoc.infer_params_schema(
            "from typing import Optional\n"
            "def run(name: str, tags: list, meta: dict, score: float,\n"
            "        flag: bool, nick: Optional[str] = None,\n"
            "        pipe: int | None = None, **extra):\n"
            "    return name\n")
        props = schema["properties"]
        self.assertEqual(props["name"], {"type": "string"})
        self.assertEqual(props["tags"], {"type": "array"})
        self.assertEqual(props["meta"], {"type": "object"})
        self.assertEqual(props["score"], {"type": "number"})
        self.assertEqual(props["flag"], {"type": "boolean"})
        self.assertEqual(props["nick"], {"type": "string"})
        self.assertEqual(props["pipe"], {"type": "integer"})
        self.assertEqual(schema["required"],
                         ["name", "tags", "meta", "score", "flag"])
        self.assertNotIn("nick", schema["required"])
        self.assertNotIn("pipe", schema["required"])
        self.assertTrue(schema["additionalProperties"])

    def test_unknown_annotation_falls_back_to_string(self):
        schema = adhoc.infer_params_schema(
            "def run(weird: SomeCustomType, bare):\n    return 1\n")
        self.assertEqual(schema["properties"]["weird"], {"type": "string"})
        self.assertEqual(schema["properties"]["bare"], {"type": "string"})
        self.assertEqual(schema["required"], ["weird", "bare"])

    def test_syntax_error_gives_none(self):
        self.assertIsNone(adhoc.infer_params_schema("def run(:\n"))


class InferredLifecycleTest(TestCase):
    def setUp(self):
        self.session = SessionModel.objects.create(name="adhoc-inf")
        self.stub = _Stub(self.session, tempfile.gettempdir())

    def test_create_without_schema_infers(self):
        ok, res = adhoc.create_adhoc_tool(
            self.stub, "shout",
            "def run(text: str, loud: bool = True):\n    return text.upper()\n",
            "shouts")
        self.assertTrue(ok, res)
        self.assertTrue(res.get("schema_inferred"))
        ok, res = adhoc.read_adhoc_tool(self.stub, "shout")
        self.assertEqual(res["meta"]["params_schema"], {
            "type": "object",
            "properties": {"text": {"type": "string"},
                           "loud": {"type": "boolean"}},
            "required": ["text"],
        })

    def test_inferred_schema_enforced_on_call(self):
        adhoc.create_adhoc_tool(
            self.stub, "shout",
            "def run(text: str):\n    return text.upper()\n")
        ok, res = adhoc.call_adhoc_tool(self.stub, "shout", {})
        self.assertFalse(ok)
        self.assertIn("required", res["message"])
        ok, res = adhoc.call_adhoc_tool(self.stub, "shout", {"text": "hi"})
        self.assertTrue(ok, res)
        self.assertEqual(res["result"], "HI")

    def test_unannotated_tool_infers_string_schema(self):
        ok, res = adhoc.create_adhoc_tool(self.stub, "leg", GOOD_SOURCE)
        self.assertTrue(ok, res)
        self.assertTrue(res.get("schema_inferred"))
        ok, res = adhoc.read_adhoc_tool(self.stub, "leg")
        self.assertEqual(res["meta"]["params_schema"], {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": [],
        })

    def test_non_dict_return_namespaced(self):
        adhoc.create_adhoc_tool(
            self.stub, "items",
            "def run(count: int):\n    return list(range(count))\n")
        ok, res = adhoc.call_adhoc_tool(self.stub, "items", {"count": 3})
        self.assertTrue(ok, res)
        self.assertEqual(res["result"], [0, 1, 2])

    def test_bool_tuple_return_unwrapped(self):
        adhoc.create_adhoc_tool(
            self.stub, "pair", "def run():\n    return (True, [1, 2])\n")
        ok, res = adhoc.call_adhoc_tool(self.stub, "pair", {})
        self.assertTrue(ok, res)
        self.assertEqual(res["result"], [1, 2])

    def test_false_tuple_reports_result(self):
        adhoc.create_adhoc_tool(
            self.stub, "neg",
            "def run():\n    return (False, {'reason': 'nope'})\n")
        ok, res = adhoc.call_adhoc_tool(self.stub, "neg", {})
        self.assertFalse(ok)
        self.assertEqual(res["result"], {"reason": "nope"})

    def test_zero_arg_run(self):
        adhoc.create_adhoc_tool(
            self.stub, "const", "def run():\n    return 42\n")
        ok, res = adhoc.call_adhoc_tool(self.stub, "const", {})
        self.assertTrue(ok, res)
        self.assertEqual(res["result"], 42)
        ok, res = adhoc.call_adhoc_tool(self.stub, "const", {"x": 1})
        self.assertFalse(ok)

    def test_update_source_refreshes_inferred_schema(self):
        adhoc.create_adhoc_tool(
            self.stub, "flex", "def run(text: str):\n    return text\n")
        ok, res = adhoc.update_adhoc_tool(
            self.stub, "flex",
            "def run(words: list):\n    return len(words)\n")
        self.assertTrue(ok, res)
        self.assertTrue(res.get("schema_inferred"))
        ok, res = adhoc.read_adhoc_tool(self.stub, "flex")
        self.assertEqual(
            res["meta"]["params_schema"]["properties"], {"words": {"type": "array"}})
        ok, res = adhoc.call_adhoc_tool(self.stub, "flex", {"words": ["a"]})
        self.assertTrue(ok, res)
        self.assertEqual(res["result"], 1)

    def test_explicit_schema_survives_source_update(self):
        adhoc.create_adhoc_tool(
            self.stub, "fixed", "def run(text: str):\n    return text\n",
            "fixed desc", SCHEMA)
        ok, res = adhoc.update_adhoc_tool(
            self.stub, "fixed", "def run(other: int):\n    return other\n")
        self.assertTrue(ok, res)
        self.assertNotIn("schema_inferred", res)
        ok, res = adhoc.read_adhoc_tool(self.stub, "fixed")
        self.assertEqual(res["meta"]["params_schema"], SCHEMA)


class _FakeFlowCall:
    def __init__(self, ok, payload):
        self._result = [ok, payload]
        self.status = "ENDED"

    def refresh_from_db(self):
        pass

    def get_result(self, timeout=0, recursive=True):
        return self._result


class _FakeFlowBound:
    def __init__(self, log, payload_fn):
        self._log = log
        self._payload_fn = payload_fn

    def delay(self, **kwargs):
        self._log.append(kwargs)
        ok, payload = self._payload_fn(kwargs)
        return _FakeFlowCall(ok, payload)


class FlowTest(TestCase):
    """call_tool_async inside run(): real subprocess + pipe pump."""

    def setUp(self):
        self.session = SessionModel.objects.create(name="adhoc-flow")
        self.stub = _Stub(self.session, tempfile.gettempdir())
        self.dispatched = []

    def _tool(self, name, source, sub_tools):
        self.stub.tools.update(sub_tools)
        ok, res = adhoc.create_adhoc_tool(self.stub, name, source)
        self.assertTrue(ok, res)

    def test_subcall_success_returns_payload(self):
        self._tool("flow", (
            "def run(text: str):\n"
            "    sub = call_tool_async('echo_tool', text=text)\n"
            "    return {'got': sub}\n"
        ), {"echo_tool": _FakeFlowBound(
            self.dispatched, lambda kw: (True, {"echoed": kw["text"]}))})
        ok, res = adhoc.call_adhoc_tool(self.stub, "flow", {"text": "hi"})
        self.assertTrue(ok, res)
        self.assertEqual(res["result"], {"got": {"echoed": "hi"}})
        self.assertEqual(self.dispatched, [{"text": "hi"}])

    def test_subcall_failure_raises_in_child(self):
        self._tool("flowfail", (
            "def run():\n"
            "    return call_tool_async('bad_tool')\n"
        ), {"bad_tool": _FakeFlowBound(
            self.dispatched,
            lambda kw: (False, {"status": "error", "message": "nope"}))})
        ok, res = adhoc.call_adhoc_tool(self.stub, "flowfail", {})
        self.assertFalse(ok)
        self.assertIn("bad_tool", res.get("stderr", ""))
        self.assertIn("nope", res.get("stderr", ""))

    def test_tool_error_catchable_in_child(self):
        self._tool("flowcatch", (
            "def run():\n"
            "    try:\n"
            "        call_tool_async('ghost')\n"
            "    except AdhocToolCallError as exc:\n"
            "        return {'caught': str(exc)}\n"
        ), {})
        ok, res = adhoc.call_adhoc_tool(self.stub, "flowcatch", {})
        self.assertTrue(ok, res)
        self.assertIn("ghost", res["result"]["caught"])
        self.assertIn("unknown or not allowed", res["result"]["caught"])

    def test_unknown_tool_is_clean_error(self):
        self._tool("flowunknown", (
            "def run():\n"
            "    return call_tool_async('ghost')\n"
        ), {})
        ok, res = adhoc.call_adhoc_tool(self.stub, "flowunknown", {})
        self.assertFalse(ok)
        self.assertIn("unknown or not allowed", res.get("stderr", ""))

    def test_nesting_depth_zero_outside_runs(self):
        self.assertEqual(adhoc._adhoc_nesting_depth(), 0)

    def test_nesting_walk_counts_frames(self):
        from runtime.context_manager import ContextTracker

        other_td = type("TD", (), {"name": "python"})()
        adhoc_td = type("TD", (), {"name": "adhoc_function_call"})()
        call_inner = type("C", (), {
            "task_definition": adhoc_td, "parent_taskrun": None})()
        run_inner = type("R", (), {"agent_task_call": call_inner})()
        call_mid = type("C", (), {
            "task_definition": other_td, "parent_taskrun": run_inner})()
        run_mid = type("R", (), {"agent_task_call": call_mid})()
        call_outer = type("C", (), {
            "task_definition": adhoc_td, "parent_taskrun": run_mid})()
        run_outer = type("R", (), {"agent_task_call": call_outer})()
        with ContextTracker(run_outer):
            self.assertEqual(adhoc._adhoc_nesting_depth(), 2)

    def test_await_observes_completion_via_refresh(self):
        """The waiter must re-read the row: a freshly dispatched call's
        in-memory status never changes, so get_result() alone polls stale
        state forever (this is what broke sub-calls initially)."""
        import time as _time

        class _FlippingCall:
            def __init__(self):
                self.status = "NEW"
                self.refreshes = 0

            def refresh_from_db(self):
                self.refreshes += 1
                if self.refreshes >= 3:
                    self.status = "ENDED"

            def get_result(self, timeout=0, recursive=True):
                return [True, {"done": True}]

        resolved = adhoc._await_call(
            _FlippingCall(), _time.time() + 30)
        self.assertEqual(resolved, [True, {"done": True}])

    def test_await_times_out_when_never_ending(self):
        import time as _time

        class _NeverCall:
            status = "NEW"

            def refresh_from_db(self):
                pass

            def get_result(self, timeout=0, recursive=True):
                raise AssertionError("must not resolve before ENDED")

        with self.assertRaises(TimeoutError):
            adhoc._await_call(_NeverCall(), _time.time() + 2)


class GuardrailTest(TestCase):
    def setUp(self):
        self.stub = _Stub(SessionModel.objects.create(name="adhoc-g"),
                           tempfile.gettempdir())

    def test_eval_blocked_at_create(self):
        ok, res = adhoc.create_adhoc_tool(
            self.stub, "evlx", "def run():\n    return eval('1')\n")
        self.assertFalse(ok)
        self.assertIn("guardrail", res["message"].lower())

    def test_shell_out_blocked_at_create(self):
        ok, res = adhoc.create_adhoc_tool(
            self.stub, "shlx", "import os\ndef run():\n    os.system('ls')\n    return {}\n")
        self.assertFalse(ok)
        self.assertIn("guardrail", res["message"].lower())

    def test_cross_session_reference_blocked(self):
        src = ("def run():\n"
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
        self.assertEqual(res["result"]["upper"], "HI")
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
