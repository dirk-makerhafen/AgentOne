"""Tests for the call_llm_direct task and tool wrapper."""
from __future__ import annotations

import importlib.util
import sys
from unittest.mock import MagicMock, patch

from django.test import TestCase


def _load_module():
    """Load the module from .agentone/scripts/core/call_llm_direct.py."""
    spec = importlib.util.spec_from_file_location(
        "call_llm_direct",
        ".agentone/scripts/core/call_llm_direct.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["call_llm_direct"] = module
    spec.loader.exec_module(module)
    return module


class NormalizeInputTest(TestCase):
    """Test input normalization in the tool wrapper."""

    def setUp(self):
        self.tool = _load_module()
        self.normalize = self.tool._normalize_input

    def test_string_input(self):
        """Single string becomes a user message."""
        result = self.normalize("hello")
        self.assertEqual(result, [{"role": "user", "content": "hello"}])

    def test_list_of_strings(self):
        """List of strings becomes multiple user messages."""
        result = self.normalize(["a", "b", "c"])
        self.assertEqual(result, [
            {"role": "user", "content": "a"},
            {"role": "user", "content": "b"},
            {"role": "user", "content": "c"},
        ])

    def test_list_of_dicts(self):
        """OpenAI format dicts pass through unchanged."""
        msgs = [
            {"role": "system", "content": "be nice"},
            {"role": "user", "content": "hello"},
        ]
        result = self.normalize(msgs)
        self.assertEqual(result, msgs)

    def test_empty_list_raises(self):
        """Empty list raises ValueError."""
        with self.assertRaises(ValueError):
            self.normalize([])

    def test_dict_missing_role_raises(self):
        """Dict without 'role' key raises ValueError."""
        with self.assertRaises(ValueError):
            self.normalize([{"content": "hello"}])

    def test_dict_missing_content_raises(self):
        """Dict without 'content' key raises ValueError."""
        with self.assertRaises(ValueError):
            self.normalize([{"role": "user"}])


class CallLlmDirectToolTest(TestCase):
    """Test the tool wrapper function."""

    def setUp(self):
        self.tool = _load_module()

    def test_none_messages_returns_error(self):
        """None messages returns error."""
        mock_session = MagicMock()
        ok, payload = self.tool.call_llm_direct_tool(_session=mock_session, messages=None)
        self.assertFalse(ok)
        self.assertIn("error", payload)
        self.assertIn("No messages", payload["error"])

    def test_dispatches_bound_task(self):
        """Tool dispatches bound task via _session.call_llm_direct.delay()."""
        mock_result = MagicMock()
        mock_result.id = "task-123"

        mock_task = MagicMock()
        mock_task.delay.return_value = mock_result

        mock_session = MagicMock()
        mock_session.call_llm_direct = mock_task

        ok, payload = self.tool.call_llm_direct_tool(_session=mock_session, messages="hello")
        self.assertTrue(ok)
        self.assertEqual(payload["status"], "dispatched")
        self.assertEqual(payload["task_id"], "task-123")

        mock_task.delay.assert_called_once_with(
            messages=[{"role": "user", "content": "hello"}],
            model_name=None,
        )

    def test_dispatches_with_model_name(self):
        """Tool passes model_name to bound task."""
        mock_result = MagicMock()
        mock_result.id = "task-456"

        mock_task = MagicMock()
        mock_task.delay.return_value = mock_result

        mock_session = MagicMock()
        mock_session.call_llm_direct = mock_task

        ok, payload = self.tool.call_llm_direct_tool(
            _session=mock_session,
            messages="classify: hello",
            model="gpt-4o",
        )
        self.assertTrue(ok)
        mock_task.delay.assert_called_once_with(
            messages=[{"role": "user", "content": "classify: hello"}],
            model_name="gpt-4o",
        )

    def test_dispatches_list_of_dicts(self):
        """Tool handles OpenAI format input."""
        mock_result = MagicMock()
        mock_result.id = "task-789"

        msgs = [
            {"role": "system", "content": "you are a classifier"},
            {"role": "user", "content": "hello"},
        ]

        mock_task = MagicMock()
        mock_task.delay.return_value = mock_result

        mock_session = MagicMock()
        mock_session.call_llm_direct = mock_task

        ok, payload = self.tool.call_llm_direct_tool(_session=mock_session, messages=msgs)
        self.assertTrue(ok)
        mock_task.delay.assert_called_once_with(messages=msgs, model_name=None)


class ResolveAimodelTest(TestCase):
    """Test model resolution in the task."""

    def test_explicit_model_name(self):
        """Explicit model name is used."""
        mod = _load_module()

        with patch("runtime.session.aimodel_picker.pick_aimodel") as mock_pick:
            mock_model = MagicMock()
            mock_model.name = "gpt-4o"
            mock_pick.return_value = mock_model

            result = mod._resolve_aimodel("gpt-4o")
            self.assertEqual(result, mock_model)
            mock_pick.assert_called_once_with("gpt-4o")

    def test_none_uses_default_model(self):
        """None model_name falls back to Default Model setting."""
        mod = _load_module()

        with patch("runtime.settings.settings.get_default_model_name") as mock_get_default:
            with patch("runtime.session.aimodel_picker.pick_aimodel") as mock_pick:
                mock_get_default.return_value = "gpt-3.5-turbo"
                mock_model = MagicMock()
                mock_pick.return_value = mock_model

                result = mod._resolve_aimodel(None)
                self.assertEqual(result, mock_model)
                mock_get_default.assert_called_once()
                mock_pick.assert_called_once_with("gpt-3.5-turbo")

    def test_no_model_returns_none(self):
        """No model available returns None."""
        mod = _load_module()

        with patch("runtime.settings.settings.get_default_model_name") as mock_get_default:
            mock_get_default.return_value = ""

            result = mod._resolve_aimodel(None)
            self.assertIsNone(result)

    def test_pick_fails_returns_none(self):
        """If pick_aimodel raises, returns None."""
        mod = _load_module()

        with patch("runtime.session.aimodel_picker.pick_aimodel") as mock_pick:
            mock_pick.side_effect = Exception("model not found")

            result = mod._resolve_aimodel("nonexistent-model")
            self.assertIsNone(result)


class EphemeralSessionTest(TestCase):
    """Test ephemeral session creation."""

    def _create_aimodel(self, name="gpt-4o"):
        """Helper to create an AiModel with a real ApiProvider."""
        from server.models.providers.api_provider import ApiProvider
        from server.models.providers.ai_model import AiModel

        provider = ApiProvider.objects.create(name=f"test-provider-{name}")
        return AiModel.objects.create(
            name=name,
            provider_model_id=name,
            api_provider=provider,
        )

    def test_creates_session_model(self):
        """SessionModel is created with correct fields."""
        mod = _load_module()

        mock_aimodel = self._create_aimodel()
        session_model, session_version, settings = mod._build_ephemeral_session(mock_aimodel)

        self.assertIsNotNone(session_model.pk)
        self.assertTrue(session_model.name.startswith("LLM Direct Call"))
        self.assertFalse(session_model.is_active)
        self.assertEqual(session_model.session_type, "llm_direct")

    def test_creates_settings_with_aimodel(self):
        """SettingsModel has the correct aimodel and tool_call_syntax."""
        mod = _load_module()
        from server.models.settings import AgentToolCallSyntax

        mock_aimodel = self._create_aimodel()
        session_model, session_version, settings = mod._build_ephemeral_session(mock_aimodel)

        self.assertEqual(settings.aimodel, mock_aimodel)
        self.assertEqual(settings.tool_call_syntax, AgentToolCallSyntax.CUSTOM)

    def test_creates_session_version(self):
        """SessionVersionModel is created and linked to ephemeral agent."""
        mod = _load_module()

        mock_aimodel = self._create_aimodel()
        session_model, session_version, settings = mod._build_ephemeral_session(mock_aimodel)

        self.assertEqual(session_version.session, session_model)
        self.assertEqual(session_version.session_settings, settings)
        self.assertIsNotNone(session_version.agent)

    def test_ephemeral_agent_created(self):
        """An ephemeral AgentModel is created for the SessionVersionModel FK."""
        from server.models.agents.agent import AgentModel
        mod = _load_module()

        mock_aimodel = self._create_aimodel()
        session_model, session_version, settings = mod._build_ephemeral_session(mock_aimodel)

        # Verify the agent was created and linked
        self.assertIsNotNone(session_version.agent)
        self.assertTrue(session_version.agent.name.startswith("LLM Direct Call Agent"))


class CallLlmDirectTaskTest(TestCase):
    """Test the task integration."""

    def test_task_is_plain_function(self):
        """Task is a plain Python function (not @shared_task)."""
        mod = _load_module()

        self.assertTrue(callable(mod.call_llm_direct))
        # Should not have Celery attributes like .delay or .apply
        self.assertFalse(hasattr(mod.call_llm_direct, "delay"))
        self.assertFalse(hasattr(mod.call_llm_direct, "apply"))

    def test_no_model_returns_error(self):
        """Task returns error dict when no model is available."""
        mod = _load_module()

        with patch.object(mod, "_resolve_aimodel") as mock_resolve:
            mock_resolve.return_value = None
            mock_session = MagicMock()

            result = mod.call_llm_direct(mock_session, messages=[{"role": "user", "content": "test"}])

            self.assertEqual(result["status"], "FAILURE")
            self.assertIn("No AI model", result["error"])

    def test_build_failure_returns_error(self):
        """Task returns error dict when session creation fails."""
        mod = _load_module()

        with patch.object(mod, "_resolve_aimodel") as mock_resolve:
            with patch.object(mod, "_build_ephemeral_session") as mock_build:
                mock_resolve.return_value = MagicMock()
                mock_build.side_effect = Exception("DB error")
                mock_session = MagicMock()

                result = mod.call_llm_direct(mock_session, messages=[{"role": "user", "content": "test"}])

                self.assertEqual(result["status"], "FAILURE")
                self.assertIn("Failed to create ephemeral session", result["error"])

    def test_query_build_failure_returns_error(self):
        """Task returns error dict when query creation fails."""
        mod = _load_module()

        with patch.object(mod, "_resolve_aimodel") as mock_resolve:
            with patch.object(mod, "_build_ephemeral_session") as mock_build:
                mock_resolve.return_value = MagicMock()
                mock_session_model, mock_session_version, mock_settings = MagicMock(), MagicMock(), MagicMock()
                mock_build.return_value = (mock_session_model, mock_session_version, mock_settings)

                with patch("server.models.queries.query.Query.objects.create") as mock_query_create:
                    mock_query_create.side_effect = Exception("Query error")
                    mock_session = MagicMock()

                    result = mod.call_llm_direct(mock_session, messages=[{"role": "user", "content": "test"}])

                    self.assertEqual(result["status"], "FAILURE")
                    self.assertIn("Failed to build query", result["error"])

    def test_successful_call_returns_response(self):
        """Task returns response data on successful LLM call."""
        from server.models.queries.response import ResponseStatus
        mod = _load_module()

        # Setup mocks
        mock_aimodel = MagicMock()
        mock_aimodel.name = "gpt-4o"

        mock_session_model = MagicMock(pk=1)
        mock_session_version = MagicMock()
        mock_settings = MagicMock()
        mock_build_result = (mock_session_model, mock_session_version, mock_settings)

        mock_query = MagicMock(pk=2)

        mock_session = MagicMock()

        mock_response = MagicMock()
        mock_response.content = "Hello, world!"
        mock_response.model_name = "gpt-4o"
        mock_response.prompt_tokens = 10
        mock_response.completion_tokens = 20
        mock_response.cached_tokens = 5
        mock_response.reasoning_tokens = 0
        mock_response.total_time = 1.5
        mock_response.status = ResponseStatus.SUCCESS
        mock_response.pk = 3

        mock_call_llm_result = MagicMock()
        mock_call_llm_result.call_llm.return_value = mock_response

        mock_session_obj = MagicMock()

        with patch.object(mod, "_resolve_aimodel") as mock_resolve:
            with patch.object(mod, "_build_ephemeral_session") as mock_build:
                with patch("server.models.queries.query.Query.objects.create") as mock_query_create:
                    with patch("runtime.session.session.Session") as mock_session_class:
                        with patch("runtime.call_llm.call_llm") as mock_call_llm_func:
                            mock_call_llm_func.return_value = mock_response
                            mock_resolve.return_value = mock_aimodel
                            mock_build.return_value = mock_build_result
                            mock_query_create.return_value = mock_query
                            mock_session_class.return_value = mock_session

                            # Call task
                            result = mod.call_llm_direct(
                                mock_session_obj,
                                messages=[{"role": "system", "content": "be nice"}, {"role": "user", "content": "hello"}]
                            )

                            # Verify result
                            self.assertEqual(result["status"], "SUCCESS")
                            self.assertEqual(result["content"], "Hello, world!")
                            self.assertEqual(result["model"], "gpt-4o")
                            self.assertEqual(result["prompt_tokens"], 10)
                            self.assertEqual(result["completion_tokens"], 20)
                            self.assertEqual(result["cached_tokens"], 5)
                            self.assertEqual(result["reasoning_tokens"], 0)
                            self.assertEqual(result["total_time"], 1.5)
                            self.assertEqual(result["session_pk"], 1)
                            self.assertEqual(result["query_pk"], 2)
                            self.assertEqual(result["response_pk"], 3)

                            # Verify call_llm was called with correct session and query
                            mock_call_llm_func.assert_called_once_with(mock_session, mock_query)

    def test_call_failure_returns_error(self):
        """Task returns error dict when LLM call raises exception."""
        mod = _load_module()

        mock_aimodel = MagicMock()

        mock_session_model = MagicMock(pk=1)
        mock_session_version = MagicMock()
        mock_settings = MagicMock()
        mock_build_result = (mock_session_model, mock_session_version, mock_settings)

        mock_query = MagicMock(pk=2)

        mock_session = MagicMock()

        mock_call_llm = MagicMock(side_effect=Exception("API error"))

        mock_session_obj = MagicMock()

        with patch.object(mod, "_resolve_aimodel") as mock_resolve:
            with patch.object(mod, "_build_ephemeral_session") as mock_build:
                with patch("server.models.queries.query.Query.objects.create") as mock_query_create:
                    with patch("runtime.session.session.Session") as mock_session_class:
                        with patch("runtime.call_llm.call_llm", side_effect=Exception("API error")):
                            mock_resolve.return_value = mock_aimodel
                            mock_build.return_value = mock_build_result
                            mock_query_create.return_value = mock_query
                            mock_session_class.return_value = mock_session

                            # Call task
                            result = mod.call_llm_direct(mock_session_obj, messages=[{"role": "user", "content": "test"}])

                            # Verify result
                            self.assertEqual(result["status"], "FAILURE")
                            self.assertIn("API error", result["error"])
                            self.assertEqual(result["session_pk"], 1)