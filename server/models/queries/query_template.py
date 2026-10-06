"""Database-backed reusable query (prompt) templates.

Replaces the former per-session ``templates/*.md`` files.  Each template
version is an immutable row pointing at content-addressed
:class:`GenericContent` (no session FK — identical bodies dedupe across
sessions); a session's *current* template is a link row
(:class:`SessionQueryTemplate`, unique per session + name).

- Save → mint a new version row, move only the writer's link.  Siblings
  and forks keep pointing at their own versions.
- Fork → copy the parent's link rows (see ``inherit_templates`` in
  ``runtime/query_templates.py``, called from
  ``AgentVersionModel.get_or_create_session``).
- Delete → remove the link row only.  Version rows stay as the audit
  trail (author, timestamp, source) for later knowledge discovery; they
  are never garbage-collected in v1.
"""
from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import models

from server.models.base_model import BaseModel, Observables


class QueryTemplateVersion(BaseModel):
    """One immutable snapshot of a query template's full ``.md`` text."""

    class QueryTemplateVersionObservables(Observables):
        """Explicit observable keys for a QueryTemplateVersion (IDE autocomplete)."""
        pass

    content = models.ForeignKey(
        "server.GenericContent",
        on_delete=models.PROTECT,
        related_name="query_template_versions",
        help_text="Full template text (frontmatter + Jinja body), content-addressed.",
    )
    name = models.CharField(
        max_length=255,
        help_text="Denormalized template slug (mirrors the frontmatter name) "
        "so lineage queries never have to parse content blobs.",
    )
    created_by_session = models.ForeignKey(
        "server.SessionModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name="created_template_versions",
        help_text="Session that minted this version (audit); NULL when unknown. "
        "SET_NULL so session deletion never erases authorship.",
    )
    source = models.CharField(
        max_length=30,
        default="",
        blank=True,
        help_text="How the version was created: panel, tool, restore, ...",
    )

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Prevent updates to existing version rows (append-only history)."""
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"<QueryTemplateVersion[{self.pk}] {self.name}>"


class SessionQueryTemplate(BaseModel):
    """A session's current pointer to one template version (the link row)."""

    class SessionQueryTemplateObservables(Observables):
        """Explicit observable keys for a SessionQueryTemplate (IDE autocomplete)."""
        @property
        def session_templates(self):
            return f"SessionQueryTemplate.session:{self.model.pk}"

    session = models.ForeignKey(
        "server.SessionModel",
        on_delete=models.CASCADE,
        related_name="query_template_links",
    )
    name = models.CharField(
        max_length=255,
        help_text="Canonical template slug (lowercase, file-stable).",
    )
    version = models.ForeignKey(
        "server.QueryTemplateVersion",
        on_delete=models.PROTECT,
        related_name="session_links",
        help_text="Current version. PROTECT: a linked version must never vanish.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "name"],
                name="uniq_session_template_name",
            ),
        ]

    def __str__(self) -> str:
        return f"<SessionQueryTemplate[{self.pk}] session={self.session_id} name={self.name}>"
