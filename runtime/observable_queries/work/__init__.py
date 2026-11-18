"""Work observable queries."""
from __future__ import annotations

from runtime.observable_queries.work.cronjob import CronjobObservables
from runtime.observable_queries.work.collection import CollectionObservables
from runtime.observable_queries.work.collection_item import CollectionItemObservables
from runtime.observable_queries.work.work_item import WorkItemObservables

__all__ = [
    "CronjobObservables",
    "CollectionObservables",
    "CollectionItemObservables",
    "WorkItemObservables",
]