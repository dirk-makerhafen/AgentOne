from unittest.mock import patch

from django.test import TestCase
from jinja2 import BaseLoader, Environment

from runtime.session.session import Session
from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
from server.models.message import Message
from server.tests.helpers import AgentMdTestMixin


class _FakeTask:
    def __init__(self, name):
        self.name = name
        self.calls = []

    def delay(self, **kwargs):
        self.calls.append(kwargs)
        return {"name": self.name, **kwargs}


class IngestSubagentResultTest(AgentMdTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.setup_global_tasks()
        cls.setup_install_repo()
        cls.agent, cls.av = cls.load_agent("base")

    @classmethod
    def tearDownClass(cls):
        cls.teardown_install_repo()
        super().tearDownClass()

    def _result_message(self, session, text):
        msg = Message.objects.create(
            role=MessageRole.ASSISTANT,
            session=session,
            session_version=session.latest_session_version,
        )
        msg.add_part(
            type=MessagePartType.MESSAGE,
            content_type=MessageContentType.TEXT,
            content=text,
        )
        return msg

    def test_template_data_is_json_safe_and_renders(self):
        parent_model = self.create_session(self.agent, self.av)
        child_model = self.create_session(self.agent, self.av)
        result = self._result_message(child_model, "the answer is 42")

        parent = Session(session_model=parent_model)
        fake = _FakeTask("ingest_user_message")
        with patch.object(Session, "get_task", return_value=fake):
            from importlib.util import module_from_spec, spec_from_file_location
            from pathlib import Path

            repo = Path(__file__).resolve().parent.parent.parent
            spec = spec_from_file_location(
                "ingest_subagent_result",
                repo / ".agentone/scripts/subagents/ingest_subagent_result.py",
            )
            module = module_from_spec(spec)
            spec.loader.exec_module(module)
            module.ingest_subagent_result(
                parent, child_model.pk, "did the thing", result
            )

        self.assertEqual(len(fake.calls), 1)
        kwargs = fake.calls[0]
        self.assertEqual(
            kwargs["execute_turn"], parent.subagentResultDelivery == "immediate"
        )
        part = kwargs["messages"][0]["parts"][0]
        self.assertEqual(part["content_type"], MessageContentType.TEMPLATE)

        # JSON-safe: no objects, only primitives.
        template_data = part["template_data"]
        self.assertEqual(template_data["child_agent"], {"name": self.agent.name})
        self.assertEqual(template_data["child_session_pk"], child_model.pk)
        self.assertEqual(template_data["task_summary"], "did the thing")
        self.assertEqual(template_data["result"], "the answer is 42")
        import json

        json.dumps(template_data)  # must not raise

        rendered = Environment(loader=BaseLoader()).from_string(
            part["content"]
        ).render(**template_data)
        self.assertIn(self.agent.name, rendered)
        self.assertIn("did the thing", rendered)
        self.assertIn("Result: the answer is 42", rendered)
