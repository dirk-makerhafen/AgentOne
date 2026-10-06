"""Tests for database-backed query templates (runtime/query_templates.py)."""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase

from runtime.query_templates import (
    TemplateError,
    build_context,
    coerce_value,
    delete_template,
    get_template,
    inherit_templates,
    list_templates,
    parse_template_text,
    render_template,
    render_template_by_name,
    save_template,
    slugify_name,
)
from server.models import SessionModel
from server.models.queries.query_template import (
    QueryTemplateVersion,
    SessionQueryTemplate,
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

    def test_optional_unused_renders(self):
        optional = parse_template_text(
            "---\nname: s2\nvariables:\n  - name: a\n    required: false\n---\nstatic\n"
        )
        self.assertEqual(render_template(optional, {}), "static")
        required = parse_template_text("---\nname: s\nvariables: [a]\n---\nstatic\n")
        with self.assertRaises(TemplateError):
            render_template(required, {})


class StringInputTest(SimpleTestCase):
    """String ``variables`` must never split into characters."""

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


class DatabaseTest(TestCase):
    def setUp(self):
        self.s1 = SessionModel.objects.create(name="tpl-s1")
        self.s2 = SessionModel.objects.create(name="tpl-s2")

    def _save(self, session=None, **kwargs):
        kwargs.setdefault("body", "Points: {{ max_points }}: {{ text }}")
        kwargs.setdefault("variables", [
            {"name": "text", "type": "string", "required": True},
            {"name": "max_points", "type": "integer", "default": 5},
        ])
        return save_template((session or self.s1).pk, "summarize", **kwargs)

    def test_save_list_get_render_delete(self):
        saved = self._save(description="d")
        self.assertEqual(saved.name, "summarize")

        listed = list_templates(self.s1.pk)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["name"], "summarize")
        self.assertNotIn("body", listed[0])

        fetched = get_template(self.s1.pk, "summarize")
        self.assertIn("max_points", fetched.body)

        _, rendered = render_template_by_name(self.s1.pk, "summarize", {"text": "hi"})
        self.assertIn("5", rendered)

        delete_template(self.s1.pk, "summarize")
        self.assertEqual(list_templates(self.s1.pk), [])

    def test_list_empty_for_new_session(self):
        self.assertEqual(list_templates(self.s1.pk), [])

    def test_get_missing(self):
        with self.assertRaises(TemplateError):
            get_template(self.s1.pk, "nope")

    def test_delete_missing(self):
        with self.assertRaises(TemplateError):
            delete_template(self.s1.pk, "nope")

    def test_bare_name_rejected_with_hint(self):
        with self.assertRaises(TemplateError) as ctx:
            save_template(self.s1.pk, "t", "Q: {{ question }}", variables="question")
        self.assertIn("[{'name': 'question'}]", str(ctx.exception))

    def test_json_and_yaml_string_specs_accepted(self):
        t = save_template(
            self.s1.pk, "t", "Q: {{ question }}",
            variables='[{"name": "question"}]',
        )
        self.assertEqual([v.name for v in t.variables], ["question"])
        t2 = save_template(
            self.s1.pk, "t2", "Q: {{ question }}",
            variables="- name: question\n  type: string\n",
        )
        self.assertEqual([v.name for v in t2.variables], ["question"])

    def test_identical_save_mints_no_new_version(self):
        self._save()
        before = QueryTemplateVersion.objects.count()
        self._save()
        self.assertEqual(QueryTemplateVersion.objects.count(), before)

    def test_update_mints_version_and_moves_only_writer_link(self):
        self._save()
        v1 = SessionQueryTemplate.objects.get(
            session_id=self.s1.pk, name="summarize"
        ).version
        # Sibling shares V1 via inherit.
        inherit_templates(self.s1.pk, self.s2.pk)
        self._save(body="CHANGED: {{ text }}", variables=["text"])
        link1 = SessionQueryTemplate.objects.get(session_id=self.s1.pk, name="summarize")
        link2 = SessionQueryTemplate.objects.get(session_id=self.s2.pk, name="summarize")
        self.assertNotEqual(link1.version_id, v1.pk)
        self.assertEqual(link2.version_id, v1.pk)  # sibling untouched
        self.assertEqual(link1.version.name, "summarize")
        self.assertEqual(link1.version.source, "api")

    def test_content_dedupes_across_sessions(self):
        self._save()
        save_template(
            self.s2.pk, "summarize", "Points: {{ max_points }}: {{ text }}",
            variables=[
                {"name": "text", "type": "string", "required": True},
                {"name": "max_points", "type": "integer", "default": 5},
            ],
        )
        v1 = SessionQueryTemplate.objects.get(session_id=self.s1.pk, name="summarize").version
        v2 = SessionQueryTemplate.objects.get(session_id=self.s2.pk, name="summarize").version
        self.assertNotEqual(v1.pk, v2.pk)
        self.assertEqual(v1.content_id, v2.content_id)

    def test_delete_keeps_versions_for_audit(self):
        self._save()
        self._save(body="v2 {{ text }}", variables=["text"])
        self.assertEqual(
            QueryTemplateVersion.objects.filter(name="summarize").count(), 2
        )
        delete_template(self.s1.pk, "summarize")
        self.assertEqual(list_templates(self.s1.pk), [])
        # Versions stay — the audit trail for later discovery.
        self.assertEqual(
            QueryTemplateVersion.objects.filter(name="summarize").count(), 2
        )

    def test_archived_sessions_keep_full_template_access(self):
        """Archive is a visibility state, not a freeze: nothing else in the
        runtime refuses writes on archived sessions (messages, turns, files
        all keep working), so templates must not either.  There is no
        ``_refuse_if_archived`` for templates — the only such helper lives
        in the unrelated adhoc-tools feature."""
        archived = SessionModel.objects.create(name="tpl-archived", is_archived=True)
        save_template(archived.pk, "qa", "Q: {{ q }}", variables=["q"])
        self.assertEqual([t["name"] for t in list_templates(archived.pk)], ["qa"])
        self.assertIn("q", get_template(archived.pk, "qa").body)
        delete_template(archived.pk, "qa")
        self.assertEqual(list_templates(archived.pk), [])

    def test_source_recorded(self):
        save_template(
            self.s1.pk, "t", "hi {{ x }}", variables=["x"], source="tool"
        )
        version = SessionQueryTemplate.objects.get(
            session_id=self.s1.pk, name="t"
        ).version
        self.assertEqual(version.source, "tool")
        self.assertEqual(version.created_by_session_id, self.s1.pk)
        self.assertEqual(version.name, "t")

    def test_version_rows_are_immutable(self):
        self._save()
        version = SessionQueryTemplate.objects.get(
            session_id=self.s1.pk, name="summarize"
        ).version
        version.source = "rewritten"
        with self.assertRaises(ValidationError):
            version.save()

    def test_link_unique_per_session(self):
        self._save()
        version = SessionQueryTemplate.objects.get(
            session_id=self.s1.pk, name="summarize"
        ).version
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SessionQueryTemplate.objects.create(
                    session=self.s1, name="summarize", version=version
                )

    def test_fork_edit_delete_lineage_is_reconstructable(self):
        """The plan's scenario: S saves, F inherits, F edits, F deletes."""
        save_template(self.s1.pk, "qa", "Q: {{ question }}",
                      variables=["question"], source="tool")
        v1 = SessionQueryTemplate.objects.get(session_id=self.s1.pk, name="qa").version
        inherit_templates(self.s1.pk, self.s2.pk)
        save_template(self.s2.pk, "qa", "CHANGED: {{ question }}",
                      variables=["question"], source="tool")
        delete_template(self.s2.pk, "qa")
        # Edit lineage, ordered: V1 by S, V2 by F.
        lineage = list(
            QueryTemplateVersion.objects.filter(
                name="qa", created_by_session__in=[self.s1, self.s2]
            ).order_by("pk")
        )
        self.assertEqual(len(lineage), 2)
        self.assertEqual(lineage[0].pk, v1.pk)
        self.assertEqual(lineage[0].created_by_session_id, self.s1.pk)
        self.assertEqual(lineage[1].created_by_session_id, self.s2.pk)
        self.assertNotEqual(lineage[1].pk, v1.pk)
        # Deleted in F (no link), alive in S.
        self.assertFalse(
            SessionQueryTemplate.objects.filter(
                session_id=self.s2.pk, name="qa"
            ).exists()
        )
        self.assertEqual(get_template(self.s1.pk, "qa").body, "Q: {{ question }}")


class InheritTest(TestCase):
    def setUp(self):
        self.parent = SessionModel.objects.create(name="tpl-parent")
        self.child = SessionModel.objects.create(name="tpl-child")

    def test_empty_parent_copies_nothing(self):
        self.assertEqual(inherit_templates(self.parent.pk, self.child.pk), 0)
        self.assertEqual(list_templates(self.child.pk), [])

    def test_copies_links_without_new_versions(self):
        save_template(self.parent.pk, "a", "hi {{ x }}", variables=["x"])
        save_template(self.parent.pk, "b", "yo {{ y }}", variables=["y"])
        versions_before = QueryTemplateVersion.objects.count()
        self.assertEqual(inherit_templates(self.parent.pk, self.child.pk), 2)
        self.assertEqual(QueryTemplateVersion.objects.count(), versions_before)
        self.assertEqual(
            [t["name"] for t in list_templates(self.child.pk)], ["a", "b"]
        )

    def test_never_clobbers_existing_child_links(self):
        save_template(self.parent.pk, "a", "parent {{ x }}", variables=["x"])
        save_template(self.child.pk, "a", "child {{ x }}", variables=["x"])
        child_version = SessionQueryTemplate.objects.get(
            session_id=self.child.pk, name="a"
        ).version_id
        inherit_templates(self.parent.pk, self.child.pk)
        self.assertEqual(
            SessionQueryTemplate.objects.get(
                session_id=self.child.pk, name="a"
            ).version_id,
            child_version,
        )


class ForkHookTest(TestCase):
    """get_or_create_session copies template links for new forks only."""

    def setUp(self):
        from server.models.agents.agent import AgentModel
        from server.models.agents.agent_version import AgentVersionModel
        from server.models.sessions.session_version import SessionVersionModel

        self.agent = AgentModel.objects.create(name="tpl_hook_agent")
        self.av = AgentVersionModel.objects.create(agent=self.agent, version_number=1)
        self.parent_session = SessionModel.objects.create(name="tpl-hook-parent")
        self.parent_sv = SessionVersionModel.objects.create(
            session=self.parent_session, agent=self.agent, version_number=1
        )
        save_template(self.parent_session.pk, "qa", "Q: {{ q }}", variables=["q"])

    def test_new_fork_inherits_links(self):
        child_sv = self.av.get_or_create_session(
            name="tpl-hook-child", parent_session_version=self.parent_sv
        )
        self.assertEqual(
            [t["name"] for t in list_templates(child_sv.session.pk)], ["qa"]
        )

    def test_fork_edit_does_not_move_parent_link(self):
        child_sv = self.av.get_or_create_session(
            name="tpl-hook-child2", parent_session_version=self.parent_sv
        )
        save_template(child_sv.session.pk, "qa", "CHANGED {{ q }}", variables=["q"])
        self.assertEqual(
            get_template(self.parent_session.pk, "qa").body, "Q: {{ q }}"
        )
        self.assertEqual(
            get_template(child_sv.session.pk, "qa").body, "CHANGED {{ q }}"
        )

    def test_existing_session_keeps_own_links(self):
        child_sv = self.av.get_or_create_session(
            name="tpl-hook-child3", parent_session_version=self.parent_sv
        )
        save_template(child_sv.session.pk, "qa", "CHANGED {{ q }}", variables=["q"])
        # Resolving the same session again must not clobber the child's edit.
        same_sv = self.av.get_or_create_session(
            name="tpl-hook-child3", parent_session_version=self.parent_sv
        )
        self.assertEqual(
            get_template(same_sv.session.pk, "qa").body, "CHANGED {{ q }}"
        )
