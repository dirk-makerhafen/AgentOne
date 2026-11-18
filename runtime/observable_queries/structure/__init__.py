"""Structure observable queries."""
from __future__ import annotations

from runtime.observable_queries.structure.project import ProjectObservables
from runtime.observable_queries.structure.workspace import WorkspaceObservables
from runtime.observable_queries.structure.provider import ProviderObservables
from runtime.observable_queries.structure.ai_model import AiModelObservables
from runtime.observable_queries.structure.terminal import TerminalObservables

__all__ = [
    "ProjectObservables",
    "WorkspaceObservables",
    "ProviderObservables",
    "AiModelObservables",
    "TerminalObservables",
]