"""``ingest_assistant_message`` must be idempotent on ``response``.

A retried ``process_turn`` (e.g. after an awaited tool call failed) re-runs
ingest with the same Response.  The first attempt already persisted the
Message and dispatched every tool call; replaying it must reuse that Message
and dispatch nothing again, otherwise one turn spawns duplicate sub-sessions
(the cron ``update_entities`` storm).
"""
import importlib.util
from pathlib import Path

import pytest

from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.enums.task_enums import TaskType
from server.models.message import Message
from server.models.queries.response import Response
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion

_ROOT = Path(__file__).resolve().parents[2]


def _load_script(relpath: str):
    """Load a manifest script module the same way registry/loader does."""
    spec = importlib.util.spec_from_file_location(
        relpath.replace("/", "_").replace(".", "_"),
        _ROOT / relpath,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _make_tool(name: str, task_type: TaskType = TaskType.TOOL):
    td = TaskDefinition.objects.create(name=name)
    tdv = TaskDefinitionVersion.objects.create(
        task_definition=td, task_type=task_type,
        description=name, function_schema={},
        priority=0, max_retries=0, retry_delay=0,
    )
    return td, tdv


def _make_setup():
    agent = AgentModel.objects.create(name="idem-agent")
    settings = SettingsModel.objects.create(priority=0)
    av = AgentVersionModel.objects.create(agent=agent, agent_settings=settings)
    _, read_tdv = _make_tool("read")
    av.task_versions.add(read_tdv)
    AgentModel.objects.filter(pk=agent.pk).update(latest_agent_version=av)
    agent.refresh_from_db()

    session = SessionModel.objects.create(name="idem-session")
    sv = SessionVersionModel.objects.create(session=session, agent=agent)
    session.latest_session_version = sv
    session.save()

    response = Response.objects.create(session=session, session_version=sv)
    return session, sv, response


def _parts():
    return [{
        "type": "TOOLCALL",
        "content_type": "JSON",
        "content": {"name": "read", "arguments": {"path": "x"}},
    }]


@pytest.mark.django_db
class TestIngestIsIdempotent:
    def test_replay_reuses_message_and_dispatches_once(self):
        session, _sv, response = _make_setup()
        module = _load_script(".agentone/scripts/core/ingest_assistant_message.py")

        first = module.ingest_assistant_message(session.get_runtime(), response, _parts())
        second = module.ingest_assistant_message(session.get_runtime(), response, _parts())

        assert first["message"].pk == second["message"].pk
        assert Message.objects.filter(response=response).count() == 1
        # The tool call was dispatched exactly once.
        assert AgentTaskCall.objects.filter(task_definition__name="read").count() == 1
        # Replayed turn shape still advertises the tool call.
        assert second["has_tool_calls"] is True

    def test_replay_preserves_final_result_shape(self):
        session, _sv, response = _make_setup()
        # ``parse_llm_response`` stores the validated name flat on the call.
        response.tool_calls = [
            {"name": "final_result", "arguments": {"content": "done"}}
        ]
        response.save()
        module = _load_script(".agentone/scripts/core/ingest_assistant_message.py")

        parts = [{
            "type": "TOOLCALL",
            "content_type": "JSON",
            "content": {
                "name": "final_result",
                "arguments": {"content": "done"},
            },
        }]
        module.ingest_assistant_message(session.get_runtime(), response, parts)
        replayed = module.ingest_assistant_message(
            session.get_runtime(), response, _final_result_parts()
        )

        assert replayed["has_final_result"] is True
        assert replayed["has_message"] is True
        assert replayed["has_tool_calls"] is False
        assert Message.objects.filter(response=response).count() == 1


def _final_result_parts():
    return [{
        "type": "TOOLCALL",
        "content_type": "JSON",
        "content": {"name": "final_result", "arguments": {"content": "done"}},
    }]
