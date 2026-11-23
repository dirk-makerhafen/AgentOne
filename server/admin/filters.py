"""Shared admin list filters that avoid full-table aggregates.

Django's built-in ``DateFieldListFilter`` runs aggregate queries over the whole
table to build its year/month drill-down.  On the multi-million-row task tables
that is unusable, so use indexed ``created_at >= now() - N days`` ranges instead.
"""
from datetime import timedelta

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils import timezone


class CreatedAtRangeFilter(admin.SimpleListFilter):
    """Date filter using indexed range lookups instead of aggregate scans."""

    title: str = "created"
    parameter_name: str = "created"

    def lookups(self, request: HttpRequest, model_admin: admin.ModelAdmin):
        return (
            ("1d", "Past 24 hours"),
            ("7d", "Past 7 days"),
            ("30d", "Past 30 days"),
            ("365d", "Past year"),
        )

    def queryset(self, request: HttpRequest, queryset: QuerySet) -> QuerySet:
        days = {"1d": 1, "7d": 7, "30d": 30, "365d": 365}.get(self.value() or "")
        if days is None:
            return queryset
        return queryset.filter(created_at__gte=timezone.now() - timedelta(days=days))
