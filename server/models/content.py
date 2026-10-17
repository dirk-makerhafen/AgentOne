"""Generic content model with deduplication by SHA-256 hash and expiry support."""
from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any

from django.db import models
from django_enum import EnumField

from server.models.base_model import ObservableMixin, Observables


# Context-budget estimate for a single image part.  Providers bill per image
# (OpenAI: base 85 tokens + 170 per 512px tile at ``high`` detail), NOT per
# base64 character — so counting the raw data-URI string like text would
# massively over-estimate (a 2048px JPEG would look like ~700k tokens).
# 1500 approximates a 2048px long-edge image at ``auto``/``high`` detail.
IMAGE_TOKEN_ESTIMATE = 1500


# Strings at or above this length are stored content-addressed (one
# GenericContent row, referenced as {"_type": "GenericContent", "pk": ...})
# instead of inline in AgentTaskCall/AgentTaskRun JSON columns.  Keeps
# result_json / carguments_json / arguments_json small when LLM outputs or
# tool payloads carry KBs/MBs of text.  Below the threshold the inline form
# is cheaper than an extra row + fetch.
GENERIC_CONTENT_DEDUP_THRESHOLD = 512


class ContentType(models.TextChoices):
    """Supported content types for :class:`GenericContent`."""

    IMAGE = "IMAGE"
    TEXT = "TEXT"
    JSON = "JSON"


class GenericContent(ObservableMixin, models.Model):
    """Content-addressed storage deduplicated by SHA-256 hash.

    Each piece of content is stored once and referenced by its hash, with an
    optional expiry for automatic cleanup.
    """

    class GenericContentObservables(Observables):
        """Explicit observable keys for a GenericContent (IDE autocomplete)."""

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
        data_str = json.dumps(data, sort_keys=True)
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

        Image files are read as binary and stored as base64 data URIs so they
        can flow straight into ``image_url`` content blocks; everything else
        is read as text.

        Parameters
        ----------
        path:
            Filesystem path to the file.
        max_age:
            Optional maximum age in days before expiry.
        """
        path = str(path)
        low = path.lower()
        image_exts = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".tif")
        if low.endswith(image_exts):
            with open(path, "rb") as fh:
                raw = fh.read()
            mime = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".gif": "image/gif",
                ".bmp": "image/bmp",
                ".tiff": "image/tiff",
                ".tif": "image/tiff",
            }[low[low.rfind("."):]]
            content = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
            content_type = ContentType.IMAGE
        else:
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
            content_type = ContentType.TEXT
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


def pack_large_string(text: str) -> Any:
    """Return *text* inline or as a GenericContent ref dict.

    Fail-open: if the DB write fails (migrations, no DB), the raw string
    is returned so serialization never breaks.
    """
    if len(text) < GENERIC_CONTENT_DEDUP_THRESHOLD:
        return text
    try:
        item = GenericContent.from_text(text)
        return {"_type": "GenericContent", "pk": item.pk}
    except Exception:
        return text


def unpack_generic_content(instance: Any) -> Any:
    """Return the plain value for a GenericContent instance, else passthrough."""
    if isinstance(instance, GenericContent):
        try:
            return instance.get()
        except Exception:
            return None
    return instance


def resolve_generic_content_refs(obj: Any) -> Any:
    """Recursively unwrap ``{"_type": "GenericContent", "pk": ...}`` refs.

    Used when rendering stored JSON (e.g. ``AgentTaskCall.carguments_json``)
    back to plain values for the LLM.  Fail-open: on any DB error the
    original ref dict is returned so rendering never breaks.
    """
    if isinstance(obj, dict):
        if set(obj.keys()) == {"_type", "pk"} and obj.get("_type") == "GenericContent":
            try:
                return GenericContent.objects.get(pk=obj["pk"]).get()
            except Exception:
                return obj
        return {k: resolve_generic_content_refs(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        resolved = [resolve_generic_content_refs(v) for v in obj]
        return type(obj)(resolved) if isinstance(obj, tuple) else resolved
    return obj
