"""Generic content model with deduplication by SHA-256 hash and expiry support."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any

from django.db import models
from django_enum import EnumField


class ContentType(models.TextChoices):
    """Supported content types for :class:`GenericContent`."""

    IMAGE = "IMAGE"
    TEXT = "TEXT"
    JSON = "JSON"


class GenericContent(models.Model):
    """Content-addressed storage deduplicated by SHA-256 hash.

    Each piece of content is stored once and referenced by its hash, with an
    optional expiry for automatic cleanup.
    """

    sha256: str = models.CharField(max_length=64, primary_key=True)
    content: str = models.TextField()
    content_type: ContentType = EnumField(ContentType, default=ContentType.TEXT)
    expires_at: datetime | None = models.DateTimeField(null=True, default=None, blank=True)

    def get(self) -> Any:
        """Return the deserialised content.

        JSON content is parsed via ``json.loads``; all other types return the
        raw string.
        """
        if self.content_type == ContentType.JSON:
            return json.loads(self.content)
        return self.content

    @classmethod
    def from_text(cls, text: str, max_age: int | None = None) -> GenericContent:
        """Create or retrieve a :class:`GenericContent` from a text string.

        Parameters
        ----------
        text:
            The text content to store.
        max_age:
            Optional maximum age in days before the content expires.
        """
        h = sha256(text.encode()).hexdigest()
        item = cls.objects.get_or_create(
            sha256=h,
            defaults={"content": text, "content_type": ContentType.TEXT},
        )[0]
        item.extend_expired_at(max_age=max_age)
        return item

    @classmethod
    def from_image(cls, image_data: str, max_age: int | None = None) -> GenericContent:
        """Create or retrieve a :class:`GenericContent` from image data.

        Parameters
        ----------
        image_data:
            The raw image data string.
        max_age:
            Optional maximum age in days before the content expires.
        """
        h = sha256(image_data.encode()).hexdigest()
        item = cls.objects.get_or_create(
            sha256=h,
            defaults={"content": image_data, "content_type": ContentType.IMAGE},
        )[0]
        item.extend_expired_at(max_age=max_age)
        return item

    @classmethod
    def from_data(
        cls, data: dict[str, Any] | list[Any], max_age: int | None = None
    ) -> GenericContent:
        """Create or retrieve a :class:`GenericContent` from a JSON-serialisable
        Python object.

        Parameters
        ----------
        data:
            The data to serialise (dict or list).
        max_age:
            Optional maximum age in days before the content expires.
        """
        data_str = json.dumps(data)
        h = sha256(data_str.encode()).hexdigest()
        item = cls.objects.get_or_create(
            sha256=h,
            defaults={"content": data_str, "content_type": ContentType.JSON},
        )[0]
        item.extend_expired_at(max_age=max_age)
        return item

    @classmethod
    def from_file(cls, path: str, max_age: int | None = None) -> GenericContent:
        """Read a file and store its content deduplicated.

        The content type is guessed from the file extension.

        Parameters
        ----------
        path:
            Filesystem path to the file.
        max_age:
            Optional maximum age in days before expiry.
        """
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
        content_type = ContentType.TEXT
        if path[-3:] in (".py", ".js") or path[-4:] in (".txt", ".css") or path[-5:] in (".html",):
            content_type = ContentType.TEXT
        elif path[-4:] in (".jpg", "png") or path[-5:] in (".jpeg", "tiff"):
            content_type = ContentType.IMAGE
        h = sha256(content.encode()).hexdigest()
        item = cls.objects.get_or_create(
            sha256=h,
            defaults={"content": content, "content_type": content_type},
        )[0]
        item.extend_expired_at(max_age=max_age)
        return item

    def extend_expired_at(self, max_age: int | None) -> None:
        """Extend the expiry timestamp if ``max_age`` is provided and the
        current expiry is earlier than the proposed new expiry."""
        if not max_age:
            return
        new_expiry = datetime.now() + timedelta(days=max_age)
        GenericContent.objects.filter(pk=self.pk, expires_at__lt=new_expiry).update(
            expires_at=new_expiry
        )
