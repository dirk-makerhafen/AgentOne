"""Tests for the slash-command dispatch helpers (``slash_commands.py``)."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slash_commands  # noqa: E402
from slash_commands import process_slashcommand  # noqa: E402


class _FakeCall:
    """Stands in for AgentTaskCall so no DB is needed."""


def _session(bound_task):
    session = MagicMock()
    session.get_command.return_value = bound_task
    session.get_tool.return_value = None
    return session


class TestProcessSlashCommand(unittest.TestCase):
    def test_dispatch_call_is_linked_to_the_user_toolcall_part(self):
        bound_task = MagicMock()
        call = _FakeCall()
        bound_task.delay.return_value = call

        with (
            patch.object(slash_commands, "Message") as message_cls,
            patch.object(slash_commands, "MessagePart"),
            patch.object(slash_commands, "AgentTaskCall", _FakeCall),
        ):
            message = message_cls.objects.create.return_value
            result = process_slashcommand(_session(bound_task), "ping", value=1)

        kwargs = message.add_part.call_args.kwargs
        self.assertEqual(kwargs["type"], slash_commands.MessagePartType.TOOLCALL)
        self.assertIs(kwargs["tool_call"], call)
        # The chain auto-awaits the returned call, so the real result reaches
        # handle_slashcommand_response rather than the call promise itself.
        self.assertIs(result["tool_reponse"], call)

    def test_failed_dispatch_keeps_a_text_only_part(self):
        bound_task = MagicMock()
        bound_task.delay.side_effect = RuntimeError("dispatch failed")

        with (
            patch.object(slash_commands, "Message") as message_cls,
            patch.object(slash_commands, "MessagePart"),
            patch.object(slash_commands, "AgentTaskCall", _FakeCall),
        ):
            message = message_cls.objects.create.return_value
            result = process_slashcommand(_session(bound_task), "ping")

        self.assertIsNone(message.add_part.call_args.kwargs["tool_call"])
        self.assertIn("exception", result["tool_reponse"])
