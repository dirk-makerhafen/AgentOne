"""Upstream manifest sources — git repos that supply agents, scripts, and skills."""

from registry.sources.types import SourceConfig, SourceResult
from registry.sources.manager import sync_upstream_sources

__all__ = ["SourceConfig", "SourceResult", "sync_upstream_sources"]
