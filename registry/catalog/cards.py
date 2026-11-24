"""Local provider research cards and documented API-base overrides.

The curated ``.agentone/providers/*.md`` cards are user-owned research, so this
module only reads them.  A small deterministic override table covers providers
that appear in the upstream free catalogs but have no card; each entry keeps
the documenting URL as provenance for the later verification pass.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import frontmatter
import yaml

from registry.catalog.normalize import resolve_provider_slug, slugify

SOURCE = "curated-provider-cards"
DOC_SOURCE = "provider-docs"


# Static, non-account-specific bases found in each provider's own docs.  The
# values are deliberately conservative: account-scoped gateways (Cloudflare AI
# Gateway, GitLab Duo, Bedrock, Vertex, ...) are omitted because no reusable
# base URL exists.
DOCUMENTED_API_BASES: dict[str, tuple[str, str]] = {
    "aclide": ("https://aclide.com/v1", "https://aclide.com/en"),
    "blaze": ("https://blazeai.boxu.dev/api", "https://api.tsukiai.org/"),
    "dreamprompting": (
        "https://dreamprompting.com/api/v1",
        "https://dreamprompting.com/api-docs?lang=en",
    ),
    "electronhub": (
        "https://api.electronhub.ai/v1",
        "https://docs.electronhub.ai/guides/openai-sdks",
    ),
    "iteracompute": (
        "https://api.iteracompute.com/v1",
        "https://iteracompute.com/docs.html",
    ),
    "router9": ("https://api.router9.com/v1", "https://www.router9.com/docs/quickstart"),
    "speechify": ("https://api.speechify.ai/v1", "https://speechify.ai"),
}


def _source_ref(provider: str, raw_id: str, source: str = SOURCE) -> dict[str, str]:
    return {"source": source, "provider": provider, "raw_id": raw_id}


def load_api_bases(root: Path) -> dict[str, dict[str, Any]]:
    """Return known API bases keyed by canonical provider slug."""
    result: dict[str, dict[str, Any]] = {}
    providers_dir = Path(root) / "providers"

    for path in sorted(providers_dir.glob("*.md")):
        try:
            metadata = frontmatter.load(path).metadata
        except (OSError, ValueError, yaml.YAMLError):  # malformed card: skip it
            continue
        api_base = str(metadata.get("api_base") or "").strip().rstrip("/")
        if not api_base.startswith(("http://", "https://")):
            continue
        aliases = [path.stem, metadata.get("name")]
        for alias in aliases:
            slug = resolve_provider_slug(alias, alias)
            result.setdefault(
                slug,
                {
                    "api_base": api_base,
                    "source": SOURCE,
                    "ref": _source_ref(slug, path.name),
                    "card": path.name,
                },
            )

    for slug, (api_base, url) in sorted(DOCUMENTED_API_BASES.items()):
        result.setdefault(
            resolve_provider_slug(slug, slug),
            {
                "api_base": api_base,
                "source": DOC_SOURCE,
                "ref": _source_ref(slug, url, DOC_SOURCE),
                "card": url,
            },
        )

    return {slug: result[slug] for slug in sorted(result) if slugify(slug) == slug}
