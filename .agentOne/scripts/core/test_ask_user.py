import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", ".."))

from runtime.user_questions import (
    all_answered,
    format_answers_for_llm,
    normalize_questions,
    validate_answers,
    validate_questions,
)

QUESTIONS = [
    {
        "question": "How should I format the output?",
        "header": "Format",
        "options": [
            {"label": "Summary", "description": "Brief overview"},
            {"label": "Detailed", "description": "Full explanation"},
        ],
        "multiSelect": False,
    },
    {
        "question": "Which sections?",
        "header": "Sections",
        "options": [
            {"label": "Intro", "description": "Opening"},
            {"label": "Outro", "description": "Closing"},
        ],
        "multiSelect": True,
    },
]


class TestValidateQuestions(unittest.TestCase):
    def test_valid(self):
        ok, reason = validate_questions(QUESTIONS)
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_empty(self):
        self.assertFalse(validate_questions([])[0])
        self.assertFalse(validate_questions(None)[0])
        self.assertFalse(validate_questions("nope")[0])

    def test_too_many_questions(self):
        self.assertFalse(validate_questions(QUESTIONS * 3)[0])

    def test_missing_text(self):
        bad = [dict(QUESTIONS[0], question="  ")]
        ok, reason = validate_questions(bad)
        self.assertFalse(ok)
        self.assertIn("non-empty question", reason)

    def test_too_few_options(self):
        bad = [dict(QUESTIONS[0], options=[{"label": "Only"}])]
        self.assertFalse(validate_questions(bad)[0])

    def test_too_many_options(self):
        bad = [dict(QUESTIONS[0],
                    options=[{"label": f"O{i}"} for i in range(5)])]
        self.assertFalse(validate_questions(bad)[0])

    def test_empty_label(self):
        bad = [dict(QUESTIONS[0], options=[{"label": "A"}, {"label": " "}])]
        ok, reason = validate_questions(bad)
        self.assertFalse(ok)
        self.assertIn("label", reason)


class TestValidateAnswers(unittest.TestCase):
    def test_single_and_multi(self):
        qs = normalize_questions(QUESTIONS)
        ok, _, norm = validate_answers(qs, {
            "How should I format the output?": "Summary",
            "Which sections?": ["Intro", "Outro"],
        })
        self.assertTrue(ok)
        self.assertEqual(norm, {
            "How should I format the output?": "Summary",
            "Which sections?": ["Intro", "Outro"],
        })

    def test_free_text_accepted(self):
        qs = normalize_questions(QUESTIONS)
        ok, _, norm = validate_answers(
            qs, {"How should I format the output?": "A haiku"})
        self.assertTrue(ok)
        self.assertEqual(norm["How should I format the output?"], "A haiku")

    def test_unknown_question_rejected(self):
        qs = normalize_questions(QUESTIONS)
        self.assertFalse(validate_answers(qs, {"Nope?": "x"})[0])

    def test_empty_value_rejected(self):
        qs = normalize_questions(QUESTIONS)
        self.assertFalse(
            validate_answers(qs, {"How should I format the output?": " "})[0])

    def test_all_answered(self):
        qs = normalize_questions(QUESTIONS)
        self.assertFalse(all_answered(qs, None))
        self.assertFalse(all_answered(
            qs, {"How should I format the output?": "Summary"}))
        self.assertTrue(all_answered(qs, {
            "How should I format the output?": "Summary",
            "Which sections?": ["Intro"],
        }))

    def test_format_for_llm(self):
        text = format_answers_for_llm({"Q?": "A", "R?": ["x", "y"]})
        self.assertIn('"Q?"="A"', text)
        self.assertIn('"R?"="x, y"', text)


if __name__ == "__main__":
    unittest.main()
