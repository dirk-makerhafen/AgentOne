from django.test import SimpleTestCase

from runtime.session.messages import default_type_for_role, normalize_messages


class NormalizeMessagesTest(SimpleTestCase):
    """Tests for the pure message-spec normalizer."""

    def test_string_single_part(self):
        self.assertEqual(
            normalize_messages("hello"),
            [{"role": "user", "message_type": None, "parts": [
                {"part_type": "message", "content_type": "text", "content": "hello"},
            ]}],
        )

    def test_list_of_strings_one_message_many_parts(self):
        result = normalize_messages(["a", "b"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(
            [p["content"] for p in result[0]["parts"]], ["a", "b"],
        )

    def test_part_dicts_one_message(self):
        result = normalize_messages([
            {"type": "message", "content_type": "text", "content": "a"},
            "b",
        ])
        self.assertEqual(len(result), 1)
        self.assertEqual([p["content"] for p in result[0]["parts"]], ["a", "b"])

    def test_single_part_dict(self):
        result = normalize_messages({"content": "hi"})
        self.assertEqual(result, [{"role": "user", "message_type": None, "parts": [
            {"part_type": "message", "content_type": "text", "content": "hi"},
        ]}])

    def test_message_dict_with_role(self):
        result = normalize_messages({"role": "assistant", "message": "hi"})
        self.assertEqual(result, [{"role": "assistant", "message_type": None, "parts": [
            {"part_type": "message", "content_type": "text", "content": "hi"},
        ]}])

    def test_parts_alias_for_body(self):
        result = normalize_messages({"role": "assistant", "parts": ["hi", "there"]})
        self.assertEqual(result[0]["role"], "assistant")
        self.assertEqual([p["content"] for p in result[0]["parts"]], ["hi", "there"])

    def test_message_list_with_trailing_user_shorthand(self):
        result = normalize_messages([
            {"role": "assistant", "message": "summary"},
            "now continue",
        ])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["role"], "assistant")
        self.assertEqual(result[1]["role"], "user")
        self.assertEqual(result[1]["parts"][0]["content"], "now continue")

    def test_mixing_message_and_part_dicts_raises(self):
        with self.assertRaises(ValueError):
            normalize_messages([
                {"role": "user", "message": "hi"},
                {"content": "part"},
            ])

    def test_template_data_infers_content_type(self):
        result = normalize_messages([{"content": "{{x}}", "template_data": {"x": 1}}])
        part = result[0]["parts"][0]
        self.assertEqual(part["content_type"], "template")
        self.assertEqual(part["template_data"], {"x": 1})

    def test_dict_content_infers_json(self):
        result = normalize_messages([{"content": {"a": 1}}])
        self.assertEqual(result[0]["parts"][0]["content_type"], "json")

    def test_explicit_content_type_wins(self):
        result = normalize_messages([{"content": {"a": 1}, "content_type": "image"}])
        self.assertEqual(result[0]["parts"][0]["content_type"], "image")

    def test_part_type_alias(self):
        result = normalize_messages([{"type": "reasoning", "content": "think"}])
        self.assertEqual(result[0]["parts"][0]["part_type"], "reasoning")

    def test_tool_call_preserved(self):
        result = normalize_messages([{"type": "toolcall", "content": "x", "tool_call": 5}])
        self.assertEqual(result[0]["parts"][0]["tool_call"], 5)

    def test_empty_specs_raise(self):
        for spec in (None, "", []):
            with self.assertRaises(ValueError):
                normalize_messages(spec)

    def test_unsupported_type_raises(self):
        with self.assertRaises(ValueError):
            normalize_messages(42)

    def test_nested_message_list_raises(self):
        with self.assertRaises(ValueError):
            normalize_messages([{"role": "user", "message": [{"role": "assistant"}]}])

    def test_none_body_yields_no_parts(self):
        result = normalize_messages([{"role": "info"}])
        self.assertEqual(result[0], {"role": "info", "message_type": None, "parts": []})

    def test_message_dict_message_type_preserved(self):
        result = normalize_messages(
            {"role": "user", "message_type": "system_notice", "message": "hi"}
        )
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[0]["message_type"], "system_notice")


class DefaultTypeForRoleTest(SimpleTestCase):
    """The role→type fallback must mirror the 0151 backfill mapping."""

    def test_role_map(self):
        self.assertEqual(default_type_for_role("assistant"), "assistant_message")
        self.assertEqual(default_type_for_role("tool"), "tool_response")
        self.assertEqual(default_type_for_role("info"), "info")
        self.assertEqual(default_type_for_role("system"), "system_notice")

    def test_unknown_roles_fall_back_to_user_chat(self):
        for role in ("user", "developer", None, ""):
            self.assertEqual(default_type_for_role(role), "user_chat")
