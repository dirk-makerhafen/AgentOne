"""Fetch and cache the three upstream catalog sources.

The cache is re-syncable state, so it lives in the machine-wide var/cache
tree (``runtime.paths.cache_base()``), not in the checkout.  Every fetch is
written atomically and checked before a rebuild starts: a failed download
never leaves a half-updated source file behind.
"""

from __future__ import annotations

import base64
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from runtime.paths import cache_base

try:  # optional: only needed to verify the signed FreeLLMAPI feed
    from cryptography.hazmat.primitives import serialization
except ImportError:  # pragma: no cover - depends on the environment
    serialization = None

AWESOME_URL = (
    "https://raw.githubusercontent.com/mnfst/awesome-free-llm-apis/"
    "refs/heads/main/data.json"
)
FREELLMAPI_URL = "https://api.freellmapi.co/v1/latest"
OPENCODE_FIXTURE_URL = (
    "https://raw.githubusercontent.com/anomalyco/opencode/2.0/"
    "packages/opencode/test/tool/fixtures/models-api.json"
)
OPENCODE_LIVE_URL = "https://opencode.ai/zen/v1/models"

AWESOME_FILE = "awesome-free-llm-apis.json"
FREELLMAPI_FILE = "freellmapi-catalog.json"
OPENCODE_FILE = "opencode-models-api.json"
OPENCODE_LIVE_FILE = "opencode-live-models.json"
MANIFEST_FILE = "sources.json"
MODEL_LIST_DIR = "model-lists"
MODEL_LIST_MANIFEST_FILE = "manifest.json"
MODEL_LIST_TIMEOUT = 8

# Base URLs that do not follow the common ``{api_base}/models`` convention.
# Keys are canonical provider slugs; values are appended to api_base.
MODEL_LIST_PATH_OVERRIDES: dict[str, str] = {
    "google-gemini": "/v1beta/models",
    "ovhcloud-ai-endpoints": "/v1/models",
}

# Pinned public key from docs/en/architecture/05-catalog-sync.md in the
# freellmapi repository.  A mismatch means the response was tampered with or
# routed from the wrong feed, so we refuse to write it.
PINNED_CATALOG_PUBKEY = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAq9yv4+3EeyMHKsfVYBhkcz1lYgIXSUeHNnN6tNgYX3k=
-----END PUBLIC KEY-----"""


@dataclass
class SourceBundle:
    """Parsed payloads plus provenance for one rebuild."""

    awesome: dict[str, Any] = field(default_factory=dict)
    freellmapi: dict[str, Any] = field(default_factory=dict)
    opencode: dict[str, Any] = field(default_factory=dict)
    opencode_live: dict[str, Any] = field(default_factory=dict)
    provider_models: dict[str, Any] = field(default_factory=dict)
    manifest: dict[str, Any] = field(default_factory=dict)

    def available(self) -> list[str]:
        """Names of the sources that actually carry data."""
        return [
            name
            for name, payload in (
                ("awesome-free-llm-apis", self.awesome),
                ("freellmapi-catalog", self.freellmapi),
                ("opencode-models-api", self.opencode),
            )
            if payload
        ]


def cache_dir() -> Path:
    """Directory holding the raw upstream payloads."""
    return cache_base() / "provider-catalog"


def write_json(path: Path, data: Any) -> None:
    """Write UTF-8 JSON with a stable format, atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path, default: Any = None) -> Any:
    """Read a cached JSON file, returning *default* when absent/corrupt."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def verify_catalog_signature(body: bytes, signature: str | None) -> str:
    """Verify the FreeLLMAPI Ed25519 signature when cryptography is present."""
    if not signature:
        return "missing"
    if serialization is None:
        return "unverified (cryptography not installed)"

    try:
        public_key = serialization.load_pem_public_key(PINNED_CATALOG_PUBKEY.encode())
        public_key.verify(base64.b64decode(signature), body)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        raise RuntimeError(
            "FreeLLMAPI catalog signature verification FAILED; refusing to write raw data"
        ) from exc
    return "verified"


def _get_json(url: str, *, headers: dict[str, str] | None = None) -> tuple[Any, bytes, str | None]:
    response = requests.get(url, timeout=60, headers=headers or {"Accept": "application/json"})
    response.raise_for_status()
    return response.json(), response.content, response.headers.get("x-catalog-signature")


def fetch_sources(
    target_dir: Path | None = None,
    *,
    offline: bool = False,
) -> SourceBundle:
    # pylint: disable=too-many-locals
    """Download (or load from cache) all upstream sources.

    ``offline=True`` only reads the cache; it is used by tests and by rebuilds
    that must not touch the network.  A source whose download fails in an
    online run is left at its last cached payload and recorded in the manifest
    as ``stale`` so the rebuild can report it instead of silently using old
    data.
    """
    target_dir = Path(target_dir) if target_dir is not None else cache_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest = read_json(target_dir / MANIFEST_FILE, {}) or {}
    if not isinstance(manifest, dict):
        manifest = {}
    entries: dict[str, Any] = dict(manifest.get("sources") or {})
    errors: list[str] = []

    awesome_url = os.environ.get("AWESOME_FREE_LLMS_URL", AWESOME_URL)
    freellmapi_url = os.environ.get("FREELLMAPI_CATALOG_URL", FREELLMAPI_URL)
    opencode_url = os.environ.get("OPENCODE_MODELS_FIXTURE_URL", OPENCODE_FIXTURE_URL)
    live_url = os.environ.get("OPENCODE_MODELS_LIVE_URL", OPENCODE_LIVE_URL)

    tasks = (
        ("awesome-free-llm-apis", awesome_url, AWESOME_FILE, None),
        ("freellmapi-catalog", freellmapi_url, FREELLMAPI_FILE, "freellmapi"),
        ("opencode-models-api", opencode_url, OPENCODE_FILE, None),
        ("opencode-live-models", live_url, OPENCODE_LIVE_FILE, None),
    )

    for name, url, filename, verify in tasks:
        path = target_dir / filename
        if offline:
            entries.setdefault(name, {"url": url, "status": "cached"})
            continue
        try:
            payload, body, signature = _get_json(url)
            if verify == "freellmapi":
                status = verify_catalog_signature(body, signature)
                tier = payload.get("tier")
                if tier != "monthly" and os.environ.get("FREELLMAPI_ALLOW_LIVE_CATALOG") != "1":
                    raise RuntimeError(
                        f"Expected the public monthly catalog, got tier={tier!r}; "
                        "refusing to ingest a live/Premium feed"
                    )
            else:
                status = "ok"
            write_json(path, payload)
            entries[name] = {
                "url": url,
                "file": filename,
                "status": status,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:  # pylint: disable=broad-exception-caught
            message = f"{name}: {exc}"
            errors.append(message)
            entries[name] = {
                "url": url,
                "file": filename,
                "status": "stale" if path.exists() else "missing",
                "error": str(exc),
            }

    payload_manifest = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "offline": offline,
        "sources": entries,
        "errors": errors,
    }
    if not offline:
        write_json(target_dir / MANIFEST_FILE, payload_manifest)
    else:
        payload_manifest["fetched_at"] = manifest.get("fetched_at", "")
        payload_manifest["errors"] = manifest.get("errors", [])

    awesome = read_json(target_dir / AWESOME_FILE, {}) or {}
    catalog = read_json(target_dir / FREELLMAPI_FILE, {}) or {}
    opencode = read_json(target_dir / OPENCODE_FILE, {}) or {}
    live = read_json(target_dir / OPENCODE_LIVE_FILE, {}) or {}

    return SourceBundle(
        awesome=awesome if isinstance(awesome, dict) else {},
        freellmapi=catalog if isinstance(catalog, dict) else {},
        opencode=opencode if isinstance(opencode, dict) else {},
        opencode_live=live if isinstance(live, dict) else {},
        manifest=payload_manifest,
    )


def model_list_url(slug: str, api_base: Any) -> str:
    """Best-effort URL for a provider's OpenAI-style model-list endpoint.

    Returns an empty string when the base URL is account-specific (contains a
    placeholder) or not HTTP(S), because guessing there would be unsafe.
    """
    base = str(api_base or "").strip().rstrip("/")
    if not base.startswith(("http://", "https://")) or "{" in base or "}" in base:
        return ""
    hostname = (urlparse(base).hostname or "").lower()
    if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        return ""
    override = MODEL_LIST_PATH_OVERRIDES.get(slug)
    if override:
        return base + override
    if base.endswith(("/v1", "/v1beta", "/api/v1")):
        return base + "/models"
    return base + "/v1/models"


def _fetch_one_model_list(slug: str, url: str, target_dir: Path) -> dict[str, Any]:
    path = target_dir / slug
    try:
        response = requests.get(
            url,
            timeout=MODEL_LIST_TIMEOUT,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, (dict, list)):
            raise ValueError(f"expected a JSON object/list, got {type(payload).__name__}")
        cached = {
            "_meta": {
                "provider": slug,
                "url": url,
                "status": "ok",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            },
            "data": payload,
        }
        write_json(path.with_suffix(".json"), cached)
        return {"url": url, "status": "ok", "file": f"{slug}.json"}
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return {"url": url, "status": "unavailable", "error": str(exc)}


def fetch_provider_model_lists(
    providers: dict[str, dict],
    target_dir: Path | None = None,
    *,
    offline: bool = False,
    workers: int = 8,
) -> dict[str, dict[str, Any]]:
    # pylint: disable=too-many-locals
    """Fetch/cache each provider's ``/models`` payload.

    This is a best-effort discovery source, not a source of truth: failures are
    recorded in the manifest and never abort a rebuild.  In offline mode only
    cached payloads are returned, so extraction stays reproducible.
    """
    target = (Path(target_dir) if target_dir is not None else cache_dir()) / MODEL_LIST_DIR
    target.mkdir(parents=True, exist_ok=True)
    manifest_path = target / MODEL_LIST_MANIFEST_FILE
    previous = read_json(manifest_path, {}) or {}
    entries: dict[str, Any] = dict(previous.get("providers") or {}) if isinstance(previous, dict) else {}
    errors: list[str] = []

    if not offline:
        tasks: list[tuple[str, str]] = []
        for slug, provider in sorted(providers.items()):
            url = model_list_url(slug, provider.get("api_base"))
            if url:
                tasks.append((slug, url))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_fetch_one_model_list, slug, url, target): slug
                for slug, url in tasks
            }
            for future in as_completed(futures):
                slug = futures[future]
                result = future.result()
                entries[slug] = result
                if result["status"] != "ok":
                    errors.append(f"{slug}: {result.get('error', 'unavailable')}")

        manifest = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "offline": False,
            "providers": entries,
            "errors": errors,
        }
        write_json(manifest_path, manifest)
    else:
        errors = list(previous.get("errors") or []) if isinstance(previous, dict) else []

    result: dict[str, dict[str, Any]] = {}
    for slug in sorted(entries):
        payload = read_json(target / f"{slug}.json", {})
        if isinstance(payload, dict) and "data" in payload:
            result[slug] = payload
    return result
