"""Tests for session-private workflows (runtime/session_workflows.py).

Pure DSL checks run as SimpleTestCase (no DB); versioning/lifecycle tests
mirror server/tests/test_query_templates.py; chain-logic tests drive the
continuation functions with stub sessions (no Celery).
"""
import itertools

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase

from runtime.session_workflows import (
    WorkflowError,
    _raise_for_failure_envelope,
    advance_workflow,
    create_workflow,
    delete_workflow,
    evaluate_when,
    fanout_workflow,
    get_workflow,
    inherit_workflows,
    join_workflow,
    list_workflows,
    mapjoin_workflow,
    render_args,
    run_workflow,
    step_workflow,
    update_workflow,
    validate_when,
    validate_workflow,
    validate_workflow_name,
)
from server.models import SessionModel
from server.models.workflow import SessionWorkflow, WorkflowVersion


def _steps(*steps):
    return list(steps)


def _tool_step(step_id, tool="echo", args=None, when=None):
    step = {"id": step_id, "tool": tool, "args": args or {}}
    if when is not None:
        step["when"] = when
    return step


# ---------------------------------------------------------------------------
# Pure validation
# ---------------------------------------------------------------------------

class NameTest(SimpleTestCase):
    def test_valid(self):
        self.assertEqual(validate_workflow_name("triage_inbox"), "triage_inbox")

    def test_rejects(self):
        for bad in ["", "Abc", "ab", "has-hyphen", "has space", "1abc", None, 42]:
            with self.assertRaises(WorkflowError, msg=repr(bad)):
                validate_workflow_name(bad)


class ValidateDefinitionTest(SimpleTestCase):
    def test_minimal_tool_workflow(self):
        canonical = validate_workflow("wflow", [_tool_step("a")])
        self.assertEqual(canonical["name"], "wflow")
        self.assertEqual(canonical["steps"][0]["args"], {})
        self.assertEqual(canonical["inputs_schema"], {})

    def test_steps_accept_json_string(self):
        canonical = validate_workflow("wflow", '[{"id": "a", "tool": "t"}]')
        self.assertEqual([s["id"] for s in canonical["steps"]], ["a"])

    def test_rejects_empty_and_oversize(self):
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [])
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [_tool_step(f"s{i}") for i in range(33)])

    def test_rejects_duplicate_ids(self):
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [_tool_step("a"), _tool_step("a")])

    def test_rejects_bad_id(self):
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [{"id": "0bad", "tool": "t"}])

    def test_rejects_zero_or_two_actions(self):
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [{"id": "a"}])
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [{"id": "a", "tool": "t", "group": []}])

    def test_group_needs_two_branches(self):
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [{"id": "a", "group": [{"tool": "t"}]}])
        canonical = validate_workflow("wflow", [{
            "id": "a", "group": [{"tool": "t1"}, {"tool": "t2"}],
        }])
        self.assertEqual(len(canonical["steps"][0]["group"]), 2)

    def test_nested_group_ok_map_nesting_rejected(self):
        canonical = validate_workflow("wflow", [{
            "id": "a",
            "group": [{"tool": "t1"}, {"group": [{"tool": "t2"}, {"tool": "t3"}]}],
        }])
        self.assertIn("group", canonical["steps"][0]["group"][1])
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [{
                "id": "a",
                "map": {
                    "producer": {"tool": "p"},
                    "consumer": {"map": {
                        "producer": {"tool": "p2"},
                        "consumer": {"tool": "c"},
                    }},
                },
            }])

    def test_map_shapes(self):
        steps = [
            _tool_step("fetch"),
            {"id": "per_item", "map": {
                "producer": {"step": "fetch"},
                "consumer": {"tool": "summarize", "args": {"t": "{{ item }}"}},
            }},
        ]
        canonical = validate_workflow("wflow", steps)
        self.assertEqual(canonical["steps"][1]["map"]["max_parallel"], 8)
        # Unknown producer step rejected.
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [{
                "id": "m", "map": {
                    "producer": {"step": "nope"},
                    "consumer": {"tool": "c"},
                }}])
        # Forward reference rejected.
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [
                {"id": "m", "map": {
                    "producer": {"step": "later"},
                    "consumer": {"tool": "c"},
                }},
                _tool_step("later"),
            ])
        # max_parallel clamped, not rejected.
        canonical = validate_workflow("wflow", [
            _tool_step("fetch"),
            {"id": "m", "map": {
                "producer": {"step": "fetch"},
                "consumer": {"tool": "c"},
                "max_parallel": 99,
            }},
        ])
        self.assertEqual(canonical["steps"][1]["map"]["max_parallel"], 32)

    def test_template_refs_checked_statically(self):
        # Unknown step ref.
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [
                _tool_step("a", args={"q": "{{ steps.nope.output }}"}),
            ])
        # Forward ref.
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [
                _tool_step("a", args={"q": "{{ steps.b.output }}"}),
                _tool_step("b"),
            ])
        # Unknown top-level variable.
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [_tool_step("a", args={"q": "{{ frobnicate }}"})])
        # item/index outside a map consumer.
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [_tool_step("a", args={"q": "{{ item }}"})])
        # Backward refs and inputs are fine.
        canonical = validate_workflow("wflow", [
            _tool_step("a", args={"q": "{{ inputs.topic }}"}),
            _tool_step("b", args={"q": "{{ steps.a.output }}"}),
        ])
        self.assertEqual(len(canonical["steps"]), 2)

    def test_cross_session_literal_rejected(self):
        own, other = 7, 9
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [_tool_step("a", args={"p": "sessions/9/x"})],
                              session_pk=own)
        # Own pk allowed; no pk context rejects any.
        validate_workflow("wflow", [_tool_step("a", args={"p": "sessions/7/x"})],
                           session_pk=own)
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [_tool_step("a", args={"p": "sessions/7/x"})])

    def test_inputs_schema_enforced(self):
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [_tool_step("a")],
                              inputs_schema={"type": "array"})
        canonical = validate_workflow(
            "wflow", [_tool_step("a")],
            inputs_schema={"type": "object",
                           "properties": {"topic": {"type": "string"}},
                           "required": ["topic"]},
        )
        self.assertEqual(canonical["inputs_schema"]["required"], ["topic"])


class ValidateFunctionTest(SimpleTestCase):
    def test_minimal_function_step(self):
        canonical = validate_workflow("wflow", [
            {"id": "pick", "function": "return [1, 2]",
             "args": {"nums": "{{ inputs.numbers }}"}},
        ])
        step = canonical["steps"][0]
        self.assertEqual(step["function"], "return [1, 2]")
        self.assertEqual(step["args"], {"nums": "{{ inputs.numbers }}"})
        self.assertNotIn("tool", step)

    def test_rejects_empty_body(self):
        for bad in ["", "   ", None, 42]:
            with self.assertRaises(WorkflowError, msg=repr(bad)):
                validate_workflow("wflow", [{"id": "a", "function": bad}])

    def test_rejects_oversize_body(self):
        from runtime.session_workflows import MAX_FUNCTION_BYTES

        big = "return " + "x" * (MAX_FUNCTION_BYTES + 1)
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [{"id": "a", "function": big}])

    def test_rejects_bad_arg_keys(self):
        for key in ["my-key", "class", "0x", "has space"]:
            with self.assertRaises(WorkflowError, msg=key):
                validate_workflow("wflow", [
                    {"id": "a", "function": "return 1", "args": {key: 1}}])

    def test_rejects_syntax_error_at_save(self):
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [
                {"id": "a", "function": "def broken(:"}])

    def test_rejects_guardrail_body_at_save(self):
        with self.assertRaises(WorkflowError) as ctx:
            validate_workflow("wflow", [
                {"id": "a", "function": "return eval('1')"}])
        self.assertIn("guardrail", str(ctx.exception).lower())

    def test_rejects_cross_session_ref_in_body(self):
        with self.assertRaises(WorkflowError):
            validate_workflow(
                "wflow", [{"id": "a", "function": "return 'sessions/9/x'"}],
                session_pk=7)

    def test_two_actions_rejected(self):
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [
                {"id": "a", "tool": "t", "function": "return 1"}])

    def test_function_in_group_branches(self):
        canonical = validate_workflow("wflow", [{
            "id": "g",
            "group": [{"tool": "t1"},
                      {"function": "return 2", "args": {}}],
        }])
        self.assertIn("function", canonical["steps"][0]["group"][1])

    def test_function_as_map_consumer(self):
        canonical = validate_workflow("wflow", [
            _tool_step("fetch"),
            {"id": "m", "map": {
                "producer": {"step": "fetch", "path": "result.items"},
                "consumer": {"function": "return item * 2"},
            }},
        ])
        self.assertIn("function",
                      canonical["steps"][1]["map"]["consumer"])

    def test_function_as_map_producer(self):
        canonical = validate_workflow("wflow", [
            {"id": "m", "map": {
                "producer": {"function": "return [1, 2]"},
                "consumer": {"tool": "echo", "args": {"t": "{{ item }}"}},
            }},
        ])
        self.assertIn("function",
                      canonical["steps"][0]["map"]["producer"])

    def test_function_template_refs_checked(self):
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [
                {"id": "a", "function": "return x",
                 "args": {"x": "{{ steps.nope.output }}"}},
            ])
        with self.assertRaises(WorkflowError):
            validate_workflow("wflow", [
                {"id": "a", "function": "return x",
                 "args": {"x": "{{ item }}"}},
            ])


class WhenTest(SimpleTestCase):
    def test_grammar_accepted(self):
        for predicate in [
            'steps.check.output.status == "error"',
            "steps.per_item.count > 0 and steps.fetch succeeded",
            "steps.per_item.output contains high_priority",
            "steps.a.output is empty",
            "steps.a.output is not empty",
            "steps.a != steps.b",
        ]:
            validate_when(predicate, ["check", "per_item", "fetch", "a", "b"], "z")

    def test_rejects_unknown_and_forward_refs(self):
        with self.assertRaises(WorkflowError):
            validate_when("steps.nope succeeded", ["a"], "b")
        with self.assertRaises(WorkflowError):
            validate_when("steps.b succeeded", ["a"], "b")  # self-ref

    def test_rejects_garbage(self):
        for bad in ["", "frobnicate", "steps.a approx 3", "steps.a == ",
                    "(steps.a succeeded)", "x" * 201]:
            with self.assertRaises(WorkflowError, msg=repr(bad)):
                validate_when(bad, ["a", "x"], "z")

    def test_quoted_and_or_literal(self):
        # 'and' inside a quoted literal must not split the predicate.
        self.assertTrue(evaluate_when(
            'steps.a.output == "fish and chips"',
            {"a": {"output": "fish and chips", "succeeded": True}},
        ))

    def test_truth_table(self):
        records = {
            "check": {"output": {"status": "error", "n": 3,
                                 "tags": ["high_priority", "x"]},
                      "count": 1, "succeeded": True},
            "items": {"output": [1, 2], "count": 2, "succeeded": True},
            "skipped": {"output": None, "count": 0, "succeeded": False,
                        "skipped": True},
        }
        cases = [
            ('steps.check.output.status == "error"', True),
            ("steps.check.output.status != 'ok'", True),
            ("steps.check.output.n > 2", True),
            ("steps.check.output.n >= 3", True),
            ("steps.check.output.n < 3", False),
            ("steps.check.output.tags contains high_priority", True),
            ("steps.check.output.status contains err", True),
            ("steps.check.output.status not contains zz", True),
            ("steps.check.output.missing is empty", True),
            ("steps.check.output.status is not empty", True),
            ("steps.items.count == 2", True),
            ("steps.check succeeded", True),
            ("steps.check failed", False),
            ("steps.skipped succeeded", False),
            ('steps.check.output.status == "error" and steps.items.count == 2', True),
            ('steps.check.output.status == "nope" or steps.items.count == 2', True),
            ('steps.check.output.status == "nope" and steps.items.count == 2', False),
            ("steps.check.output.n > 99", False),  # mismatch-safe False
        ]
        for predicate, expected in cases:
            self.assertEqual(evaluate_when(predicate, records), expected,
                             predicate)


class FailureEnvelopeTest(SimpleTestCase):
    def test_success_envelope_passes_through(self):
        value = [True, {"stdout": "hi"}]
        self.assertIs(_raise_for_failure_envelope(value, "tool 'x'"), value)

    def test_plain_values_pass_through(self):
        for value in (None, 42, "text", [1, 2, 3], {"a": 1}, [True]):
            self.assertEqual(_raise_for_failure_envelope(value, "w"), value)

    def test_false_envelope_raises_with_message(self):
        with self.assertRaises(WorkflowError) as ctx:
            _raise_for_failure_envelope(
                [False, {"status": "error", "message": "boom"}],
                "Step tool 'python' (call 12)",
            )
        text = str(ctx.exception)
        self.assertIn("python", text)
        self.assertIn("boom", text)

    def test_false_envelope_prefers_stderr(self):
        with self.assertRaises(WorkflowError) as ctx:
            _raise_for_failure_envelope(
                [False, {"status": "success", "stdout": "",
                         "stderr": "NameError: name 'json' is not defined"}],
                "Map producer step 'gen'",
            )
        text = str(ctx.exception)
        self.assertIn("gen", text)
        self.assertIn("NameError", text)

    def test_false_envelope_non_dict_payload(self):
        with self.assertRaises(WorkflowError) as ctx:
            _raise_for_failure_envelope([False, "plain failure"], "w")
        self.assertIn("plain failure", str(ctx.exception))


class RenderTest(SimpleTestCase):
    def test_renders_inputs_and_steps(self):
        context = {
            "inputs": {"topic": "cats"},
            "steps": {"fetch": {"output": [1, 2], "count": 2,
                                "succeeded": True}},
        }
        out = render_args(
            {"q": "{{ inputs.topic }}", "n": "{{ steps.fetch.count }}",
             "limit": 20, "nested": {"x": ["{{ inputs.topic }}"]},
             "plain": "no template"},
            context,
        )
        self.assertEqual(out, {"q": "cats", "n": 2, "limit": 20,
                               "nested": {"x": ["cats"]}, "plain": "no template"})

    def test_single_expression_keeps_native_type(self):
        """A value that is exactly one {{ ... }} resolves to the object."""
        context = {
            "inputs": {},
            "steps": {"fetch": {"output": [1, 2], "count": 2,
                                "succeeded": True}},
        }
        out = render_args(
            {"items": "{{ steps.fetch.output }}",
             "label": "count: {{ steps.fetch.count }}"},
            context,
        )
        self.assertEqual(out["items"], [1, 2])  # native list, not repr
        self.assertEqual(out["label"], "count: 2")  # mixed text stays str

    def test_literal_looking_strings_are_never_parsed(self):
        """Bare {{ }} keeps strings as strings — no literal_eval guessing.

        Regression: Jinja NativeEnvironment used to parse literal-looking
        strings (a JSON stdout became a list, "42" an int), so type
        depended on string content and json.loads() in the next step blew
        up on already-parsed values (AGENTONE-AgentOne workflow_test).
        """
        context = {
            "inputs": {},
            "steps": {"produce": {
                "output": {"status": "success",
                           "stdout": '[{"id": 1, "score": 85}]',
                           "stderr": "", "return_code": 0},
                "count": 1, "succeeded": True}},
        }
        out = render_args(
            {"items_str": "{{ steps.produce.output.stdout }}",
             "whole": "{{ steps.produce.output }}"},
            context,
        )
        self.assertIsInstance(out["items_str"], str)
        self.assertEqual(out["items_str"], '[{"id": 1, "score": 85}]')
        self.assertIsInstance(out["whole"], dict)

    def test_numeric_and_bool_strings_stay_strings(self):
        out = render_args(
            {"n": "{{ inputs.n }}", "t": "{{ inputs.t }}",
             "none": "{{ inputs.z }}"},
            {"inputs": {"n": "42", "t": "True", "z": "None"}, "steps": {}},
        )
        self.assertEqual(out, {"n": "42", "t": "True", "none": "None"})
        self.assertIsInstance(out["n"], str)

    def test_native_int_stays_int(self):
        out = render_args({"n": "{{ steps.a.count }}"},
                          {"inputs": {},
                           "steps": {"a": {"output": 1, "count": 7,
                                           "succeeded": True}}})
        self.assertEqual(out, {"n": 7})
        self.assertIsInstance(out["n"], int)

    def test_strict_undefined(self):
        from runtime.session_workflows import WorkflowError as _WE

        with self.assertRaises(_WE):
            render_args({"q": "{{ inputs.missing }}"},
                        {"inputs": {}, "steps": {}})

    def test_item_index(self):
        out = render_args({"t": "{{ item.name }}-{{ index }}"},
                          {"inputs": {}, "steps": {},
                           "item": {"name": "x"}, "index": 3})
        self.assertEqual(out, {"t": "x-3"})


# ---------------------------------------------------------------------------
# DB lifecycle (mirrors test_query_templates.py)
# ---------------------------------------------------------------------------

class DatabaseTest(TestCase):
    def setUp(self):
        self.s1 = SessionModel.objects.create(name="wf-s1")
        self.s2 = SessionModel.objects.create(name="wf-s2")

    def _save(self, session=None, name="triage", **kwargs):
        kwargs.setdefault("steps", [_tool_step("fetch")])
        return create_workflow((session or self.s1).pk, name, **kwargs)

    def test_create_list_get_delete(self):
        created = self._save(description="d")
        self.assertEqual(created["name"], "triage")
        self.assertEqual(created["steps"], 1)

        listed = list_workflows(self.s1.pk)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["name"], "triage")
        self.assertNotIn("definition", listed[0])
        self.assertEqual(listed[0]["steps"], 1)

        fetched = get_workflow(self.s1.pk, "triage")
        self.assertEqual(fetched["definition"]["steps"][0]["id"], "fetch")

        delete_workflow(self.s1.pk, "triage")
        self.assertEqual(list_workflows(self.s1.pk), [])

    def test_list_empty_and_missing(self):
        self.assertEqual(list_workflows(self.s1.pk), [])
        with self.assertRaises(WorkflowError):
            get_workflow(self.s1.pk, "nope")
        with self.assertRaises(WorkflowError):
            delete_workflow(self.s1.pk, "nope")
        with self.assertRaises(WorkflowError):
            create_workflow(self.s1.pk, "Bad Name!", [_tool_step("a")])

    def test_create_fails_when_taken(self):
        self._save()
        with self.assertRaises(WorkflowError):
            self._save()

    def test_update_missing(self):
        with self.assertRaises(WorkflowError):
            update_workflow(self.s1.pk, "nope", steps=[_tool_step("a")])

    def test_identical_update_mints_no_new_version(self):
        self._save()
        before = WorkflowVersion.objects.count()
        result = update_workflow(self.s1.pk, "triage", steps=[_tool_step("fetch")])
        self.assertTrue(result.get("unchanged"))
        self.assertEqual(WorkflowVersion.objects.count(), before)

    def test_update_mints_version_and_moves_only_writer_link(self):
        self._save()
        v1 = SessionWorkflow.objects.get(
            session_id=self.s1.pk, name="triage").version
        inherit_workflows(self.s1.pk, self.s2.pk)
        update_workflow(self.s2.pk, "triage", steps=[_tool_step("changed")])
        link1 = SessionWorkflow.objects.get(session_id=self.s1.pk, name="triage")
        link2 = SessionWorkflow.objects.get(session_id=self.s2.pk, name="triage")
        self.assertEqual(link1.version_id, v1.pk)  # parent untouched
        self.assertNotEqual(link2.version_id, v1.pk)
        self.assertEqual(link2.version.created_by_session_id, self.s2.pk)

    def test_update_revalidates(self):
        self._save()
        with self.assertRaises(WorkflowError):
            update_workflow(self.s1.pk, "triage", steps=[{"id": "bad step!"}])

    def test_content_dedupes_across_sessions(self):
        self._save()
        create_workflow(self.s2.pk, "triage", [_tool_step("fetch")],
                        description="")
        v1 = SessionWorkflow.objects.get(session_id=self.s1.pk, name="triage").version
        v2 = SessionWorkflow.objects.get(session_id=self.s2.pk, name="triage").version
        self.assertNotEqual(v1.pk, v2.pk)
        self.assertEqual(v1.content_id, v2.content_id)

    def test_delete_keeps_versions_for_audit(self):
        self._save()
        update_workflow(self.s1.pk, "triage", steps=[_tool_step("v2")])
        self.assertEqual(WorkflowVersion.objects.filter(name="triage").count(), 2)
        delete_workflow(self.s1.pk, "triage")
        self.assertEqual(WorkflowVersion.objects.filter(name="triage").count(), 2)

    def test_version_rows_are_immutable(self):
        self._save()
        version = SessionWorkflow.objects.get(
            session_id=self.s1.pk, name="triage").version
        version.source = "rewritten"
        with self.assertRaises(ValidationError):
            version.save()

    def test_link_unique_per_session(self):
        self._save()
        version = SessionWorkflow.objects.get(
            session_id=self.s1.pk, name="triage").version
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SessionWorkflow.objects.create(
                    session=self.s1, name="triage", version=version)

    def test_cap_enforced(self):
        from runtime import session_workflows as _wf

        old_max = _wf.MAX_WORKFLOWS
        _wf.MAX_WORKFLOWS = 1
        try:
            self._save(name="one")
            with self.assertRaises(WorkflowError):
                self._save(name="two")
        finally:
            _wf.MAX_WORKFLOWS = old_max

    def test_archived_sessions_keep_full_access(self):
        archived = SessionModel.objects.create(name="wf-archived",
                                               is_archived=True)
        create_workflow(archived.pk, "qaw", [_tool_step("a")])
        self.assertEqual([w["name"] for w in list_workflows(archived.pk)], ["qaw"])
        update_workflow(archived.pk, "qaw", steps=[_tool_step("b")])
        delete_workflow(archived.pk, "qaw")
        self.assertEqual(list_workflows(archived.pk), [])


class InheritTest(TestCase):
    def setUp(self):
        self.parent = SessionModel.objects.create(name="wf-parent")
        self.child = SessionModel.objects.create(name="wf-child")

    def test_empty_parent_copies_nothing(self):
        self.assertEqual(inherit_workflows(self.parent.pk, self.child.pk), 0)

    def test_copies_links_without_new_versions(self):
        create_workflow(self.parent.pk, "wfa", [_tool_step("x")])
        create_workflow(self.parent.pk, "wfb", [_tool_step("y")])
        before = WorkflowVersion.objects.count()
        self.assertEqual(inherit_workflows(self.parent.pk, self.child.pk), 2)
        self.assertEqual(WorkflowVersion.objects.count(), before)
        self.assertEqual([w["name"] for w in list_workflows(self.child.pk)],
                         ["wfa", "wfb"])

    def test_never_clobbers_existing_child_links(self):
        create_workflow(self.parent.pk, "wfa", [_tool_step("p")])
        create_workflow(self.child.pk, "wfa", [_tool_step("c")])
        child_version = SessionWorkflow.objects.get(
            session_id=self.child.pk, name="wfa").version_id
        inherit_workflows(self.parent.pk, self.child.pk)
        self.assertEqual(
            SessionWorkflow.objects.get(
                session_id=self.child.pk, name="wfa").version_id,
            child_version)


class ForkHookTest(TestCase):
    """get_or_create_session copies workflow links for new forks only."""

    def setUp(self):
        from server.models.agents.agent import AgentModel
        from server.models.agents.agent_version import AgentVersionModel
        from server.models.sessions.session_version import SessionVersionModel

        self.agent = AgentModel.objects.create(name="wf_hook_agent")
        self.av = AgentVersionModel.objects.create(agent=self.agent,
                                                  version_number=1)
        self.parent_session = SessionModel.objects.create(name="wf-hook-parent")
        self.parent_sv = SessionVersionModel.objects.create(
            session=self.parent_session, agent=self.agent, version_number=1
        )
        create_workflow(self.parent_session.pk, "qaw", [_tool_step("a")])

    def test_new_fork_inherits_links(self):
        child_sv = self.av.get_or_create_session(
            name="wf-hook-child", parent_session_version=self.parent_sv)
        self.assertEqual(
            [w["name"] for w in list_workflows(child_sv.session.pk)], ["qaw"])

    def test_fork_edit_does_not_move_parent_link(self):
        child_sv = self.av.get_or_create_session(
            name="wf-hook-child2", parent_session_version=self.parent_sv)
        update_workflow(child_sv.session.pk, "qaw", steps=[_tool_step("b")])
        self.assertEqual(
            get_workflow(self.parent_session.pk, "qaw")["definition"]["steps"][0]["id"],
            "a")
        self.assertEqual(
            get_workflow(child_sv.session.pk, "qaw")["definition"]["steps"][0]["id"],
            "b")


# ---------------------------------------------------------------------------
# Chain logic with stub sessions (no Celery)
# ---------------------------------------------------------------------------

_call_pks = itertools.count(1000)


class _FakeCall:
    def __init__(self):
        self.pk = next(_call_pks)


class _FakeBound:
    def __init__(self, log, name):
        self._log = log
        self._name = name

    def delay(self, **kwargs):
        self._log.append((self._name, kwargs))
        return _FakeCall()


class _StubSession:
    def __init__(self, tools=(), tasks=(), pk=1):
        self.dispatched = []
        self.model = _ModelPk(pk)
        self._tools = {name: _FakeBound(self.dispatched, f"tool:{name}")
                       for name in tools}
        self._tasks = {name: _FakeBound(self.dispatched, f"task:{name}")
                       for name in tasks}

    def get_tool(self, name):
        return self._tools.get(name)

    def get_task(self, name):
        return self._tasks.get(name)


class _ModelPk:
    def __init__(self, pk):
        self.pk = pk


_ENGINE_TASKS = ("workflow_step", "workflow_advance", "workflow_join",
                 "workflow_fanout", "workflow_mapjoin", "workflow_inline")


def _run_ctx(session_pk, name, version, inputs=None, calls=None):
    return {"name": name, "version_pk": version, "inputs": inputs or {},
            "visited": [name], "calls": calls or {}, "producers": {}}


class ChainTest(TestCase):
    def setUp(self):
        self.session = SessionModel.objects.create(name="wf-chain")
        created = create_workflow(self.session.pk, "chain", [
            _tool_step("first", tool="echo",
                       args={"text": "hi {{ inputs.who }}"}),
            {"id": "second", "tool": "echo",
             "args": {"text": "{{ steps.first.output }}"},
             "when": "steps.first succeeded"},
        ])
        self.version = created["version"]

    def _stub(self, tools=("echo",)):
        return _StubSession(tools=tools, tasks=_ENGINE_TASKS,
                            pk=self.session.pk)

    def test_tool_step_dispatches_tool_then_advance(self):
        stub = self._stub()
        ctx = _run_ctx(self.session.pk, "chain", self.version,
                       inputs={"who": "you"})
        advance_call = step_workflow(stub, ctx, 0)
        kinds = [kind for kind, _ in stub.dispatched]
        self.assertEqual(kinds, ["tool:echo", "task:workflow_advance"])
        _tool_kind, tool_kwargs = stub.dispatched[0]
        self.assertEqual(tool_kwargs, {"text": "hi you"})
        _adv_kind, adv_kwargs = stub.dispatched[1]
        self.assertEqual(adv_kwargs["index"], 0)
        self.assertTrue(hasattr(adv_kwargs["prior"], "pk"))
        self.assertIsNotNone(advance_call)

    def test_run_workflow_pins_version_and_dispatches_step(self):
        stub = self._stub()
        call = run_workflow(stub, "chain", {"other": "ignored"})
        # 'who' has no schema so any inputs pass; version pinned in run_ctx.
        _name, kwargs = stub.dispatched[0]
        self.assertEqual(_name, "task:workflow_step")
        self.assertEqual(kwargs["run_ctx"]["version_pk"], self.version)
        self.assertEqual(kwargs["index"], 0)
        self.assertIsNotNone(call)

    def test_run_unknown_workflow_returns_error_tuple(self):
        stub = self._stub()
        ok, payload = run_workflow(stub, "nope")
        self.assertFalse(ok)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(stub.dispatched, [])

    def test_run_validates_inputs_against_schema(self):
        create_workflow(self.session.pk, "strict", [_tool_step("a")],
                        inputs_schema={"type": "object",
                                       "properties": {"t": {"type": "string"}},
                                       "required": ["t"]})
        stub = self._stub()
        ok, payload = run_workflow(stub, "strict", {})
        self.assertFalse(ok)
        self.assertIn("t", payload["message"])

    def test_unknown_tool_is_clean_error_not_traceback(self):
        create_workflow(self.session.pk, "badtool", [
            _tool_step("a", tool="no_such_tool_xyz")])
        stub = self._stub(tools=())
        version = get_workflow(self.session.pk, "badtool")["meta"]["version"]
        result = step_workflow(stub, _run_ctx(self.session.pk, "badtool",
                                              version), 0)
        self.assertEqual(result["status"], "error")
        self.assertIn("no_such_tool_xyz", result["message"])

    def test_advance_dispatches_next_step(self):
        stub = self._stub()
        ctx = _run_ctx(self.session.pk, "chain", self.version, calls={"first": [111]})
        nxt = advance_workflow(stub, ctx, 0, prior={"anything": 1})
        self.assertEqual(stub.dispatched[-1][0], "task:workflow_step")
        self.assertEqual(stub.dispatched[-1][1]["index"], 1)
        self.assertIsNotNone(nxt)

    def test_advance_past_last_step_finishes(self):
        from unittest.mock import patch

        stub = self._stub()
        ctx = _run_ctx(self.session.pk, "chain", self.version,
                       calls={"first": [111], "second": [222]})
        with patch("runtime.session_workflows._call_output",
                   side_effect=[{"v": 1}, {"v": 2}]):
            result = advance_workflow(stub, ctx, 1, prior={"v": 2})
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["outputs"], {"first": {"v": 1}, "second": {"v": 2}})
        self.assertEqual(result["skipped"], [])

    def test_when_false_skips_synchronously(self):
        from unittest.mock import patch

        create_workflow(self.session.pk, "cond", [
            _tool_step("first"),
            {"id": "nope", "tool": "echo", "when": "steps.first failed"},
            _tool_step("third"),
        ])
        version = get_workflow(self.session.pk, "cond")["meta"]["version"]
        stub = self._stub()
        ctx = _run_ctx(self.session.pk, "cond", version, calls={"first": [111]})
        with patch("runtime.session_workflows._call_output", return_value={"v": 1}):
            step_workflow(stub, ctx, 1)
        # Step 'nope' skipped without dispatch; step 'third' dispatched.
        tool_dispatches = [k for k, _ in stub.dispatched if k.startswith("tool:")]
        self.assertEqual(len(tool_dispatches), 1)
        adv_kwargs = stub.dispatched[-1][1]
        self.assertEqual(adv_kwargs["index"], 2)
        self.assertIsNone(adv_kwargs["run_ctx"]["calls"]["nope"])

    def test_group_dispatches_branches_then_join(self):
        create_workflow(self.session.pk, "grp", [{
            "id": "g",
            "group": [{"tool": "echo", "args": {"t": "1"}},
                      {"tool": "echo", "args": {"t": "2"}}],
        }])
        version = get_workflow(self.session.pk, "grp")["meta"]["version"]
        stub = self._stub()
        join_call = step_workflow(
            stub, _run_ctx(self.session.pk, "grp", version), 0)
        kinds = [kind for kind, _ in stub.dispatched]
        self.assertEqual(kinds, ["tool:echo", "tool:echo", "task:workflow_join"])
        _name, join_kwargs = stub.dispatched[-1]
        self.assertEqual(len(join_kwargs["branches"]), 2)
        self.assertIsNotNone(join_call)

    def test_join_continues_to_next_step(self):
        stub = self._stub()
        ctx = _run_ctx(self.session.pk, "chain", self.version, calls={"first": [111]})
        nxt = join_workflow(stub, ctx, 0, branches=[{"v": 1}])
        self.assertEqual(stub.dispatched[-1][0], "task:workflow_step")
        self.assertIsNotNone(nxt)

    def test_fanout_empty_list_finishes(self):
        from unittest.mock import patch

        create_workflow(self.session.pk, "empty", [
            _tool_step("fetch"),
            {"id": "m", "map": {
                "producer": {"step": "fetch"},
                "consumer": {"tool": "echo", "args": {"t": "{{ item }}"}},
            }},
        ])
        version = get_workflow(self.session.pk, "empty")["meta"]["version"]
        stub = self._stub()
        ctx = _run_ctx(self.session.pk, "empty", version, calls={"fetch": [111]})
        with patch("runtime.session_workflows._call_output", return_value=[]):
            result = fanout_workflow(stub, ctx, 1, producer=[[True, []]])
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["outputs"]["m"], [])
        self.assertEqual(stub.dispatched, [])

    def test_fanout_non_list_is_error(self):
        create_workflow(self.session.pk, "badmap", [
            _tool_step("fetch"),
            {"id": "m", "map": {
                "producer": {"step": "fetch"},
                "consumer": {"tool": "echo"},
            }},
        ])
        version = get_workflow(self.session.pk, "badmap")["meta"]["version"]
        stub = self._stub()
        ctx = _run_ctx(self.session.pk, "badmap", version, calls={"fetch": [111]})
        result = fanout_workflow(stub, ctx, 1, producer=[[True, {"not": "a list"}]])
        self.assertEqual(result["status"], "error")
        self.assertIn("must resolve to a list", result["message"])

    def test_fanout_waves_then_mapjoin_finishes(self):
        from unittest.mock import patch

        create_workflow(self.session.pk, "wavy", [
            _tool_step("fetch"),
            {"id": "m", "map": {
                "producer": {"step": "fetch"},
                "consumer": {"tool": "echo", "args": {"t": "{{ item }}-{{ index }}"}},
                "max_parallel": 2,
            }},
        ])
        version = get_workflow(self.session.pk, "wavy")["meta"]["version"]
        stub = self._stub()
        ctx = _run_ctx(self.session.pk, "wavy", version, calls={"fetch": [111]})
        with patch("runtime.session_workflows._call_output",
                   return_value=["a", "b", "c"]):
            mapjoin_call = fanout_workflow(
                stub, ctx, 1, producer=[[True, ["a", "b", "c"]]])
        tool_dispatches = [kw for kind, kw in stub.dispatched
                           if kind == "tool:echo"]
        self.assertEqual(len(tool_dispatches), 2)  # first wave only
        self.assertEqual(tool_dispatches[0], {"t": "a-0"})
        self.assertEqual(tool_dispatches[1], {"t": "b-1"})
        _name, mj_kwargs = stub.dispatched[-1]
        self.assertEqual(_name, "task:workflow_mapjoin")
        self.assertEqual(mj_kwargs["remaining"], ["c"])
        self.assertEqual(len(mj_kwargs["wave"]), 2)
        self.assertIsNotNone(mapjoin_call)

        # Second wave: remaining non-empty dispatches the rest.
        stub2 = self._stub()
        with patch("runtime.session_workflows._call_output",
                   return_value=["a", "b", "c"]):
            mapjoin_workflow(stub2, mj_kwargs["run_ctx"], 1,
                             collected=mj_kwargs["run_ctx"]["calls"]["m"],
                             wave=[{"r": 1}, {"r": 2}], remaining=["c"])
        tool_dispatches = [kw for kind, kw in stub2.dispatched
                           if kind == "tool:echo"]
        self.assertEqual(tool_dispatches, [{"t": "c-0"}])

    def test_fanout_inline_producer_takes_single_result(self):
        create_workflow(self.session.pk, "inlinemap", [{
            "id": "m", "map": {
                "producer": {"tool": "echo", "args": {"t": "x"}},
                "consumer": {"tool": "echo", "args": {"t": "{{ item }}"}},
            },
        }])
        version = get_workflow(self.session.pk, "inlinemap")["meta"]["version"]
        stub = self._stub()
        ctx = _run_ctx(self.session.pk, "inlinemap", version)
        mapjoin_call = fanout_workflow(
            stub, ctx, 0, producer=[True, ["a", "b"]])
        tool_dispatches = [kw for kind, kw in stub.dispatched
                           if kind == "tool:echo"]
        self.assertEqual(tool_dispatches, [{"t": "a"}, {"t": "b"}])
        self.assertIsNotNone(mapjoin_call)

    def test_fanout_failed_producer_reports_cause_not_path(self):
        """A producer tool returning (False, ...) fails with its stderr,
        not a downstream 'path not found' error (the AGENTONE-AgentOne loop)."""
        create_workflow(self.session.pk, "failmap", [
            _tool_step("gen"),
            {"id": "m", "map": {
                "producer": {"step": "gen", "path": "stdout"},
                "consumer": {"tool": "echo"},
            }},
        ])
        version = get_workflow(self.session.pk, "failmap")["meta"]["version"]
        stub = self._stub()
        ctx = _run_ctx(self.session.pk, "failmap", version, calls={"gen": [111]})
        result = fanout_workflow(
            stub, ctx, 1,
            producer=[[False, {"status": "success", "stdout": "",
                               "stderr": "NameError: name 'json' is not defined"}]])
        self.assertEqual(result["status"], "error")
        self.assertIn("gen", result["message"])
        self.assertIn("NameError", result["message"])
        self.assertNotIn("not found in producer output", result["message"])

    def test_fanout_json_string_producer_parses_to_list(self):
        """A producer resolving to a JSON-encoded list string (e.g. python
        stdout) maps over the parsed list."""
        from unittest.mock import patch

        create_workflow(self.session.pk, "jsonmap", [
            _tool_step("gen"),
            {"id": "m", "map": {
                "producer": {"step": "gen", "path": "stdout"},
                "consumer": {"tool": "echo", "args": {"t": "{{ item }}"}},
            }},
        ])
        version = get_workflow(self.session.pk, "jsonmap")["meta"]["version"]
        stub = self._stub()
        ctx = _run_ctx(self.session.pk, "jsonmap", version, calls={"gen": [111]})
        payload = {"stdout": '["a", "b"]', "stderr": ""}
        with patch("runtime.session_workflows._call_output", return_value=payload):
            mapjoin_call = fanout_workflow(stub, ctx, 1, producer=[[True, payload]])
        tool_dispatches = [kw for kind, kw in stub.dispatched
                           if kind == "tool:echo"]
        self.assertEqual(tool_dispatches, [{"t": "a"}, {"t": "b"}])
        self.assertIsNotNone(mapjoin_call)

    def test_fanout_plain_string_producer_errors_with_preview(self):
        create_workflow(self.session.pk, "strmap", [
            _tool_step("gen"),
            {"id": "m", "map": {
                "producer": {"step": "gen", "path": "stdout"},
                "consumer": {"tool": "echo"},
            }},
        ])
        version = get_workflow(self.session.pk, "strmap")["meta"]["version"]
        stub = self._stub()
        ctx = _run_ctx(self.session.pk, "strmap", version, calls={"gen": [111]})
        result = fanout_workflow(
            stub, ctx, 1, producer=[[True, {"stdout": "just text"}]])
        self.assertEqual(result["status"], "error")
        self.assertIn("must resolve to a list", result["message"])
        self.assertIn("just text", result["message"])

    def test_mapjoin_empty_remaining_advances(self):
        from unittest.mock import patch

        stub = self._stub()
        ctx = _run_ctx(self.session.pk, "chain", self.version,
                       calls={"first": [111], "second": [222]})
        with patch("runtime.session_workflows._call_output",
                   side_effect=[{"v": 1}, {"w": 1}, {"w": 2}]):
            nxt = mapjoin_workflow(stub, ctx, 1, collected=[222, 333],
                                   wave=[{"w": 1}, {"w": 2}], remaining=[])
        # Index 1 is the last step of 'chain' → finishes with regrouped map
        # output only if step 1 were a map; here step 1 is a tool step, so
        # collected pks resolve as extra leaves — assert it finishes cleanly.
        self.assertEqual(nxt["status"], "success")

    def test_delete_mid_run_is_safe(self):
        """Runs pin version pks, so deleting the link cannot break them."""
        stub = self._stub()
        ctx = _run_ctx(self.session.pk, "chain", self.version,
                       inputs={"who": "you"})
        step_workflow(stub, ctx, 0)
        delete_workflow(self.session.pk, "chain")
        # The recorded version still loads; the chain can continue.
        nxt = advance_workflow(stub, ctx, 0, prior={"ok": True})
        self.assertEqual(stub.dispatched[-1][0], "task:workflow_step")
        self.assertIsNotNone(nxt)


class FunctionChainTest(TestCase):
    def setUp(self):
        self.session = SessionModel.objects.create(name="wf-fnchain")

    def _stub(self, tools=("echo",)):
        return _StubSession(tools=tools, tasks=_ENGINE_TASKS,
                            pk=self.session.pk)

    def test_function_step_dispatches_inline_task(self):
        create_workflow(self.session.pk, "fnflow", [
            {"id": "pick", "function": "return [x * 2 for x in nums]",
             "args": {"nums": "{{ inputs.numbers }}"}},
        ])
        version = get_workflow(self.session.pk, "fnflow")["meta"]["version"]
        stub = self._stub(tools=())
        nxt = step_workflow(
            stub, _run_ctx(self.session.pk, "fnflow", version,
                           inputs={"numbers": [1, 2]}), 0)
        self.assertEqual([k for k, _ in stub.dispatched],
                         ["task:workflow_inline", "task:workflow_advance"])
        _name, inline_kwargs = stub.dispatched[0]
        self.assertEqual(inline_kwargs["source"], "return [x * 2 for x in nums]")
        self.assertEqual(inline_kwargs["params"], {"nums": [1, 2]})
        self.assertIsNotNone(nxt)

    def test_function_step_gets_native_prior_output(self):
        create_workflow(self.session.pk, "fntwo", [
            _tool_step("fetch"),
            {"id": "pick", "function": "return content + bar",
             "args": {"content": "{{ steps.fetch.output }}",
                      "bar": "bar"}},
        ])
        version = get_workflow(self.session.pk, "fntwo")["meta"]["version"]
        stub = self._stub()
        from unittest.mock import patch

        ctx = _run_ctx(self.session.pk, "fntwo", version, calls={"fetch": [111]})
        with patch("runtime.session_workflows._call_output",
                   return_value={"nested": [1]}):
            step_workflow(stub, ctx, 1)
        _name, inline_kwargs = stub.dispatched[0]
        self.assertEqual(_name, "task:workflow_inline")
        self.assertEqual(inline_kwargs["params"],
                         {"content": {"nested": [1]}, "bar": "bar"})

    def test_function_in_group_branch(self):
        create_workflow(self.session.pk, "fngrp", [{
            "id": "g",
            "group": [{"tool": "echo", "args": {"t": "1"}},
                      {"function": "return 2"}],
        }])
        version = get_workflow(self.session.pk, "fngrp")["meta"]["version"]
        stub = self._stub()
        step_workflow(stub, _run_ctx(self.session.pk, "fngrp", version), 0)
        kinds = [k for k, _ in stub.dispatched]
        self.assertEqual(kinds, ["tool:echo", "task:workflow_inline",
                                 "task:workflow_join"])

    def test_function_as_map_consumer(self):
        from unittest.mock import patch

        create_workflow(self.session.pk, "fnmap", [
            _tool_step("fetch"),
            {"id": "m", "map": {
                "producer": {"step": "fetch"},
                "consumer": {"function": "return item * 10"},
            }},
        ])
        version = get_workflow(self.session.pk, "fnmap")["meta"]["version"]
        stub = self._stub()
        ctx = _run_ctx(self.session.pk, "fnmap", version, calls={"fetch": [111]})
        with patch("runtime.session_workflows._call_output",
                   return_value=[3, 4]):
            fanout_workflow(stub, ctx, 1, producer=[[True, [3, 4]]])
        inline_dispatches = [kw for k, kw in stub.dispatched
                             if k == "task:workflow_inline"]
        self.assertEqual(len(inline_dispatches), 2)
        self.assertEqual(inline_dispatches[0]["params"], {"item": 3, "index": 0})

    def test_function_as_map_producer(self):
        create_workflow(self.session.pk, "fnprod", [{
            "id": "m", "map": {
                "producer": {"function": "return [7, 8]"},
                "consumer": {"tool": "echo", "args": {"t": "{{ item }}"}},
            },
        }])
        version = get_workflow(self.session.pk, "fnprod")["meta"]["version"]
        stub = self._stub()
        step_workflow(stub, _run_ctx(self.session.pk, "fnprod", version), 0)
        _name, inline_kwargs = stub.dispatched[0]
        self.assertEqual(_name, "task:workflow_inline")
        self.assertEqual(inline_kwargs["source"], "return [7, 8]")
        self.assertEqual(inline_kwargs["params"], {})

    def test_missing_inline_task_is_clean_error(self):
        create_workflow(self.session.pk, "fnoeng", [
            {"id": "a", "function": "return 1"},
        ])
        version = get_workflow(self.session.pk, "fnoeng")["meta"]["version"]
        stub = _StubSession(tools=(), tasks=("workflow_step",),
                            pk=self.session.pk)
        result = step_workflow(
            stub, _run_ctx(self.session.pk, "fnoeng", version), 0)
        self.assertEqual(result["status"], "error")
        self.assertIn("workflow_inline", result["message"])


class InlineExecutionTest(SimpleTestCase):
    def _stub(self):
        return _StubSession(pk=1)

    def test_native_list_flows_without_strings(self):
        from runtime.adhoc_tools import run_inline_function

        ok, res = run_inline_function(
            self._stub(), "foo = content + 'bar'\nreturn {'whatever': foo}",
            {"content": "x"})
        self.assertTrue(ok, res)
        self.assertEqual(res["result"], {"whatever": "xbar"})

    def test_no_args(self):
        from runtime.adhoc_tools import run_inline_function

        ok, res = run_inline_function(self._stub(), "return [1, 2]")
        self.assertTrue(ok, res)
        self.assertEqual(res["result"], [1, 2])

    def test_runtime_error_is_failure_envelope(self):
        from runtime.adhoc_tools import run_inline_function

        ok, res = run_inline_function(self._stub(), "return missing_name")
        self.assertFalse(ok)
        self.assertEqual(res["status"], "error")
        self.assertIn("missing_name", res["stderr"])

    def test_empty_body_rejected(self):
        from runtime.adhoc_tools import run_inline_function

        ok, res = run_inline_function(self._stub(), "   ")
        self.assertFalse(ok)
        self.assertIn("non-empty", res["message"])

    def test_print_breaks_envelope_like_adhoc(self):
        from runtime.adhoc_tools import run_inline_function

        ok, res = run_inline_function(
            self._stub(), "print('side quest')\nreturn 1")
        self.assertFalse(ok)
