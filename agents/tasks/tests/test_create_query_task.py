import pytest
from unittest.mock import patch, MagicMock
from agents.tasks.create_query import celery_create_query # Corrected import
from agents.models.agent_instance import AgentInstance # Explicit import
from agents.models.conversation_message import ConversationMessage # Explicit import
from agents.models.llm_query import LLMQuery # Explicit import
from agents.models.llm_response import LLMResponse # Explicit import
from providers.models.ai_model import AiModel
from providers.models.api_provider import ApiProvider # Explicit import
