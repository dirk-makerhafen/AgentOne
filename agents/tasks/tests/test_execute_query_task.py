import pytest
from unittest.mock import patch, MagicMock
from agents.tasks.execute_query import execute_query # Assuming execute_query is the correct function name
from agents.models.agent_instance import AgentInstance # Explicit import
from agents.models.llm_query import LLMQuery # Explicit import
from tools.calls.models.tool_call import ToolCall # Explicit import
from tools.calls.models.tool_response import ToolResponse # Explicit import
#TODO