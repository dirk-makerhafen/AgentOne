"""Tests for session-private query templates (runtime/query_templates.py)."""
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from runtime.query_templates import (
    TemplateError,
    build_context,
    coerce_value,
    delete_template,
    get_template,
    list_templates,
    parse_template_text,
    render_template,
    render_template_by_name,
    save_template,
    slugify_name,
)


VALID_TEXT = """---
name: summarize
description: Summarize text
variables:
  - name: text
    type: string
    required: true
  - name: max_points
    type: integer
    required: false
    default: 5
---
Summarize in {{ max_points }} points:

{{ text }}
"""


class SlugTest(SimpleTestCase):
    def test_valid(self):
        self.assertEqual(slugify_name("summarize"), "summarize")
        self.assertEqual(slugify_name("My Template!"), "my-template")

    def test_traversal_sanitized_safe(self):
        # Lenient slugify: dangerous input is sanitized to a safe slug that
        # always stays inside the templates dir (never raises, never escapes).
        self.assertEqual(slugify_name("../evil"), "evil")

    def test_empty_rejected(self):
        with self.assertRaises(TemplateError):
            slugify_name("")


class ParseTest(SimpleTestCase):
    def test_valid(self):
        t = parse_template_text(VALID_TEXT)
        self.assertEqual(t.name, "summarize")
        self.assertEqual(len(t.variables), 2)
        self.assertEqual(t.variables[1].default, 5)

    def test_missing_frontmatter(self):
        with self.assertRaises(TemplateError):
            parse_template_text("Just a body, no frontmatter.")

    def test_missing_name(self):
        with self.assertRaises(TemplateError):
            parse_template_text("---\ndescription: x\n---\nbody\n")

    def test_duplicate_vars(self):
        with self.assertRaises(TemplateError):
            parse_template_text(
                "---\nname: dup\nvariables:\n  - name: a\n  - name: a\n---\n{{ a }}\n"
            )

    def test_unknown_type(self):
        with self.assertRaises(TemplateError):
            parse_template_text(
                "---\nname: bad\nvariables:\n  - name: a\n    type: dict\n---\n{{ a }}\n"
            )

    def test_plain_string_var_means_required_string(self):
        t = parse_template_text("---\nname: s\nvariables: [text]\n---\n{{ text }}\n")
        self.assertTrue(t.variables[0].required)
        self.assertEqual(t.variables[0].type, "string")

    def test_required_false_string_means_optional(self):
        t = parse_template_text(
            "---\nname: s\nvariables:\n  - name: a\n    required: \"false\"\n---\n"
            "Hi {{ a }}\n"
        )
        self.assertFalse(t.variables[0].required)
        # Omitted optional renders fine when unused...
        t2 = parse_template_text(
            "---\nname: s2\nvariables:\n  - name: a\n    required: \"false\"\n---\n"
            "static\n"
        )
        self.assertEqual(render_template(t2, {}), "static")
        # ...but referencing it without a value fails loudly (StrictUndefined).
        with self.assertRaises(TemplateError):
            render_template(t, {})
        self.assertEqual(render_template(t, {"a": "x"}), "Hi x")

    def test_required_garbage_rejected(self):
        with self.assertRaises(TemplateError):
            parse_template_text(
                "---\nname: s\nvariables:\n  - name: a\n    required: maybe\n---\n{{ a }}\n"
            )

    def test_empty_body_rejected(self):
        with self.assertRaises(TemplateError):
            parse_template_text("---\nname: empty\n---\n")


class CoerceTest(SimpleTestCase):
    def test_integer_from_string(self):
        self.assertEqual(coerce_value("integer", "5", var_name="n"), 5)

    def test_integer_rejects_float_string(self):
        with self.assertRaises(TemplateError):
            coerce_value("integer", "5.5", var_name="n")

    def test_number_from_string(self):
        self.assertEqual(coerce_value("number", "5", var_name="n"), 5)
        self.assertEqual(coerce_value("number", "5.5", var_name="n"), 5.5)

    def test_number_rejects_garbage(self):
        with self.assertRaises(TemplateError):
            coerce_value("number", "abc", var_name="n")

    def test_boolean_strings(self):
        self.assertIs(coerce_value("boolean", "true", var_name="b"), True)
        self.assertIs(coerce_value("boolean", "No", var_name="b"), False)

    def test_boolean_rejects_int_2(self):
        with self.assertRaises(TemplateError):
            coerce_value("boolean", 2, var_name="b")

    def test_integer_rejects_bool(self):
        with self.assertRaises(TemplateError):
            coerce_value("integer", True, var_name="n")


class RenderTest(SimpleTestCase):
    def test_defaults_applied(self):
        t = parse_template_text(VALID_TEXT)
        out = render_template(t, {"text": "hello"})
        self.assertIn("5 points", out)
        self.assertIn("hello", out)

    def test_missing_required(self):
        t = parse_template_text(VALID_TEXT)
        with self.assertRaises(TemplateError):
            render_template(t, {})

    def test_typo_fails_loudly(self):
        t = parse_template_text("---\nname: t\nvariables: [txt]\n---\n{{ txt_typo }}\n")
        with self.assertRaises(TemplateError):
            render_template(t, {"txt": "hi"})

    def test_build_context_ignores_extras(self):
        t = parse_template_text(VALID_TEXT)
        ctx = build_context(t, {"text": "hi", "unknown_key": 1})
        self.assertNotIn("unknown_key", ctx)


class StringInputTest(SimpleTestCase):
    """Regression: string ``variables`` must never split into characters.

    An agent once passed ``"question"`` where a spec list was expected and
    got 8 one-character variables (q, u, e, s, t, i, o, n).
    """

    def test_bare_name_rejected_with_hint(self):
        with tempfile.TemporaryDirectory() as td:
            with override_settings(AGENTONE_SESSIONS_DIR=td):
                with self.assertRaises(TemplateError) as ctx:
                    save_template(1, "t", "Q: {{ question }}", variables="question")
                self.assertIn("[{'name': 'question'}]", str(ctx.exception))

    def test_json_string_list_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            with override_settings(AGENTONE_SESSIONS_DIR=td):
                t = save_template(
                    1, "t", "Q: {{ question }}",
                    variables='[{"name": "question"}]',
                )
                self.assertEqual([v.name for v in t.variables], ["question"])

    def test_yaml_string_list_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            with override_settings(AGENTONE_SESSIONS_DIR=td):
                t = save_template(
                    1, "t", "Q: {{ question }}",
                    variables="- name: question\n  type: string\n",
                )
                self.assertEqual([v.name for v in t.variables], ["question"])

    def test_single_mapping_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            with override_settings(AGENTONE_SESSIONS_DIR=td):
                t = save_template(
                    1, "t", "Q: {{ question }}",
                    variables={"name": "question"},
                )
                self.assertEqual([v.name for v in t.variables], ["question"])

    def test_json_string_values_render(self):
        t = parse_template_text(VALID_TEXT)
        out = render_template(t, '{"text": "hi", "max_points": "3"}')
        self.assertIn("3 points", out)
        self.assertIn("hi", out)

    def test_bare_string_values_rejected(self):
        t = parse_template_text(VALID_TEXT)
        with self.assertRaises(TemplateError) as ctx:
            render_template(t, "question")
        self.assertIn("mapping", str(ctx.exception))


class FilesystemTest(SimpleTestCase):
    def test_save_list_get_render_delete(self):
        with tempfile.TemporaryDirectory() as td:
            with override_settings(AGENTONE_SESSIONS_DIR=td):
                saved = save_template(
                    11, "summarize", "Points: {{ max_points }}: {{ text }}",
                    description="d",
                    variables=[
                        {"name": "text", "type": "string", "required": True},
                        {"name": "max_points", "type": "integer", "default": 5},
                    ],
                )
                self.assertEqual(saved.name, "summarize")
                self.assertTrue((Path(td) / "11" / "templates" / "summarize.md").is_file())

                listed = list_templates(11)
                self.assertEqual(len(listed), 1)
                self.assertEqual(listed[0]["name"], "summarize")
                self.assertNotIn("body", listed[0])

                fetched = get_template(11, "summarize")
                self.assertIn("max_points", fetched.body)

                _, rendered = render_template_by_name(11, "summarize", {"text": "hi"})
                self.assertIn("5", rendered)

                delete_template(11, "summarize")
                self.assertEqual(list_templates(11), [])

    def test_list_empty_when_no_dir(self):
        with tempfile.TemporaryDirectory() as td:
            with override_settings(AGENTONE_SESSIONS_DIR=td):
                self.assertEqual(list_templates(999), [])

    def test_get_missing(self):
        with tempfile.TemporaryDirectory() as td:
            with override_settings(AGENTONE_SESSIONS_DIR=td):
                with self.assertRaises(TemplateError):
                    get_template(1, "nope")

    def test_invalid_file_skipped_in_list(self):
        with tempfile.TemporaryDirectory() as td:
            with override_settings(AGENTONE_SESSIONS_DIR=td):
                save_template(2, "good", "hi {{ x }}", variables=["x"])
                folder = Path(td) / "2" / "templates"
                (folder / "broken.md").write_text("no frontmatter here")
                listed = list_templates(2)
                self.assertEqual([t["name"] for t in listed], ["good"])
                with self.assertRaises(TemplateError):
                    get_template(2, "broken")

    def test_name_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with override_settings(AGENTONE_SESSIONS_DIR=td):
                save_template(3, "alpha", "hi {{ x }}", variables=["x"])
                folder = Path(td) / "3" / "templates"
                (folder / "alpha.md").write_text(
                    "---\nname: beta\nvariables: []\n---\nbody\n"
                )
                with self.assertRaises(TemplateError):
                    get_template(3, "alpha")
