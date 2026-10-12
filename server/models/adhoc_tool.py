"""Database-backed session-private ad-hoc tools.

Replaces the former per-session ``adhoc_tools/*.py`` files.  Each tool
version is an immutable row pointing at content-addressed
:class:`GenericContent` (no session FK — identical code dedupes across
sessions); a session's *current* tool is a link row
(:class:`SessionAdhocTool`, unique per session + name).

- Save → mint a new version row, move only the writer's link.  Siblings
  and forks keep pointing at their own versions.  Saving identical
  content+metadata is a no-op (no new version).
- Fork → copy the parent's link rows (see ``inherit_adhoc_tools`` in
  ``runtime/adhoc_tools.py``, called from
  ``AgentVersionModel.get_or_create_session``).
- Delete → remove the link row only.  Version rows stay as the audit
  trail (author, timestamp, source); they are never garbage-collected
  in v1 — same convention as query templates
  (``server/models/queries/query_template.py``).

The tool source is scanned once at write time (same Python guardrails as
the ``execution.python`` tool); reads never re-scan because version rows
are immutable.
"""
from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import models

from server.models.base_model import BaseModel, Observables


class AdhocToolVersion(BaseModel):
    """One immutable snapshot of an ad-hoc tool (code + metadata)."""

    class AdhocToolVersionObservables(Observables):
        """Explicit observable keys for an AdhocToolVersion (IDE autocomplete)."""
        @property
        def links(self):
            return f"SessionAdhocTool.version:{self.model.pk}"

    content = models.ForeignKey(
        "server.GenericContent",
        on_delete=models.PROTECT,
        related_name="adhoc_tool_versions",
        help_text="Python source defining run(...), content-addressed.",
    )
    name = models.CharField(
        max_length=255,
        help_text="Denormalized tool name so lineage queries never have "
        "to join content blobs.",
    )
    description = models.TextField(
        default="",
        blank=True,
        help_text="One-line description shown by adhoc_list.",
    )
    params_schema = models.JSONField(
        null=True,
        default=None,
        blank=True,
        help_text="Optional JSON-schema-subset dict calls are validated against.",
    )
    schema_inferred = models.BooleanField(
        default=False,
        help_text="True when params_schema was inferred from run's signature "
        "(vs explicitly set). Lets source-only updates refresh inferred "
        "schemas without ever clobbering explicit ones.",
    )
    created_by_session = models.ForeignKey(
        "server.SessionModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name="created_adhoc_tool_versions",
        help_text="Session that minted this version (audit); NULL when unknown. "
        "SET_NULL so session deletion never erases authorship.",
    )
    source = models.CharField(
        max_length=30,
        default="",
        blank=True,
        help_text="How the version was created: tool, migrate, ...",
    )

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Prevent updates to existing version rows (append-only history)."""
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"<AdhocToolVersion[{self.pk}] {self.name}>"


class SessionAdhocTool(BaseModel):
    """A session's current pointer to one ad-hoc tool version (the link row)."""

    class SessionAdhocToolObservables(Observables):
        """Explicit observable keys for a SessionAdhocTool (IDE autocomplete)."""
        @property
        def session_adhoc_tools(self):  # type: ignore[no-untyped-def]
            return f"SessionAdhocTool.session:{self.model.session_id}"

    session = models.ForeignKey(
        "server.SessionModel",
        on_delete=models.CASCADE,
        related_name="adhoc_tool_links",
    )
    name = models.CharField(
        max_length=255,
        help_text="Tool name (lowercase letter first, then lowercase/digits/_).",
    )
    version = models.ForeignKey(
        "server.AdhocToolVersion",
        on_delete=models.PROTECT,
        related_name="session_links",
        help_text="Current version. PROTECT: a linked version must never vanish.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "name"],
                name="uniq_session_adhoc_tool_name",
            ),
        ]

    def __str__(self) -> str:
        return f"<SessionAdhocTool[{self.pk}] session={self.session_id} name={self.name}>"
