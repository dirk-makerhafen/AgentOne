"""

Source: https://github.com/tashfeenahmed/freellmapi
Feed:   https://api.freellmapi.co/v1/latest (public, signed, monthly tier, ~30-day lag)

Usage:
    python3 scripts/generate_from_freellmapi_catalog.py

Creates "raw/freellmapi-catalog/":
  - source.json           feed metadata (version, tier, signature status)
  - catalog.json          verbatim signed payload
  - platforms/<id>.json   one file per platform: metadata + chat models + quirks
  - non_chat.json         embeddings / transcription / search / decision leads
  - candidates.json       structured diff against providers/ and models/
  - candidates.md         human-readable lead report

The catalog is a DISCOVERY source only. Never promote a row into providers/ or
models/ without the normal official-doc verification described in AGENT.md.
Per-model limits belong in a model card's providers[].limits, not in the
provider frontmatter. monthlyTokenBudget, ranks and capability flags are hints.
"""

import base64
import fnmatch
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CATALOG_URL = os.environ.get(
    "FREELLMAPI_CATALOG_URL", "https://api.freellmapi.co/v1/latest"
)
TARGET_DIR = BASE / "raw" / "freellmapi-catalog"
PLATFORMS_DIR = TARGET_DIR / "platforms"
PROVIDERS_DIR = BASE / "providers"
MODELS_DIR = BASE / "models"

# Pinned public key from docs/en/architecture/05-catalog-sync.md in the
# freellmapi repository. Only used to detect a tampered/misrouted response.
PINNED_CATALOG_PUBKEY = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAq9yv4+3EeyMHKsfVYBhkcz1lYgIXSUeHNnN6tNgYX3k=
-----END PUBLIC KEY-----"""

# Catalog platform IDs whose canonical research file uses a different slug.
# Unknown IDs fall back to the catalog ID and are reported as new leads.
PLATFORM_ALIASES = {
    "agnes": "agnes-ai",
    "aion": "aion-labs",
    "cloudflare": "cloudflare-workers-ai",
    "google": "google-gemini",
    "kilo": "kilo-code",
    "nvidia": "nvidia-nim",
    "ovh": "ovhcloud-ai-endpoints",
    "zhipu": "z-ai",
}


def write_json(path: Path, data) -> None:
    """Write UTF-8 JSON with a stable, readable format."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def verify_signature(body: bytes, signature_header: str | None) -> str:
    """Verify the Ed25519 catalog signature when cryptography is available."""
    if not signature_header:
        return "missing"

    try:
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        return "unverified (cryptography not installed)"

    try:
        public_key = serialization.load_pem_public_key(PINNED_CATALOG_PUBKEY.encode())
        public_key.verify(base64.b64decode(signature_header), body)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        raise RuntimeError(
            "FreeLLMAPI catalog signature verification FAILED; refusing to write raw data"
        ) from exc
    return "verified"


def fetch_catalog() -> tuple[dict, dict]:
    """Fetch the public monthly catalog and return payload + source metadata."""
    response = requests.get(
        CATALOG_URL,
        timeout=30,
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()

    signature_status = verify_signature(
        response.content, response.headers.get("x-catalog-signature")
    )
    payload = response.json()

    tier = payload.get("tier")
    if tier != "monthly" and os.environ.get("FREELLMAPI_ALLOW_LIVE_CATALOG") != "1":
        raise RuntimeError(
            f"Expected the public monthly catalog, got tier={tier!r}. "
            "Refusing to ingest a live/Premium feed. "
            "Set FREELLMAPI_ALLOW_LIVE_CATALOG=1 only if you have explicit permission."
        )

    metadata = {
        "source": "FreeLLMAPI public monthly catalog",
        "url": CATALOG_URL,
        "repository": "https://github.com/tashfeenahmed/freellmapi",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "version": payload.get("version"),
        "generated_at": payload.get("generatedAt"),
        "tier": tier,
        "signature_status": signature_status,
        "counts": payload.get("counts", {}),
        "usage_note": (
            "Discovery source only. Verify every provider/model claim against official "
            "provider documentation before adding or updating research cards."
        ),
    }
    return payload, metadata


def platform_names(payload: dict) -> dict[str, str]:
    """Map platform ID -> display name."""
    return {
        item.get("id"): item.get("name") or item.get("id")
        for item in payload.get("platforms", [])
        if item.get("id")
    }


def quirks_for_platform(payload: dict, platform_id: str, models: list[dict]) -> list[dict]:
    """Return catalog quirks targeting this platform (and matching model globs)."""
    result = []
    for quirk in payload.get("quirks", []):
        for target in quirk.get("targets", []):
            if target.get("platform") != platform_id:
                continue

            model_glob = target.get("modelGlob")
            if model_glob and not any(
                fnmatch.fnmatch(model.get("modelId", ""), model_glob) for model in models
            ):
                continue

            result.append(quirk)
            break
    return result


def write_platform_files(payload: dict) -> None:
    """Write one raw discovery file per catalog platform."""
    names = platform_names(payload)
    chat_models = payload.get("models", [])

    for platform in payload.get("platforms", []):
        platform_id = platform.get("id")
        if not platform_id:
            continue

        models = [m for m in chat_models if m.get("platform") == platform_id]
        data = {
            "id": platform_id,
            "name": names.get(platform_id, platform_id),
            "catalog_version": payload.get("version"),
            "chat_model_count": len(models),
            "models": models,
            "quirks": quirks_for_platform(payload, platform_id, models),
            "sections": {
                "embeddings": sum(
                    1
                    for item in payload.get("embeddings", [])
                    if item.get("platform") == platform_id
                ),
                "transcription": sum(
                    1
                    for item in payload.get("transcriptionModels", [])
                    if item.get("platform") == platform_id
                ),
            },
        }
        write_json(PLATFORMS_DIR / f"{platform_id}.json", data)


def write_non_chat(payload: dict) -> None:
    """Keep non-chat discovery sections in one separate raw file."""
    keys = (
        "embeddings",
        "transcriptionModels",
        "videoModels",
        "searchEngines",
        "decisionModels",
        "specialistTextModels",
    )
    write_json(
        TARGET_DIR / "non_chat.json",
        {key: payload.get(key, []) for key in keys},
    )


def build_candidates(payload: dict) -> dict:
    """Diff catalog leads against existing research cards."""
    provider_slugs = {path.stem for path in PROVIDERS_DIR.glob("*.md")}
    model_text = "\n".join(
        path.read_text(encoding="utf-8").lower() for path in MODELS_DIR.glob("*.md")
    )
    names = platform_names(payload)
    chat_models = [
        model for model in payload.get("models", []) if model.get("enabled", True)
    ]

    models_by_platform: dict[str, list[dict]] = {}
    for model in chat_models:
        models_by_platform.setdefault(model.get("platform", ""), []).append(model)

    rows = []
    unique_new_model_ids: set[str] = set()

    for platform_id, models in models_by_platform.items():
        suggested_slug = PLATFORM_ALIASES.get(platform_id, platform_id)
        has_provider_card = suggested_slug in provider_slugs

        new_models = [
            model
            for model in models
            if model.get("modelId", "").lower() not in model_text
        ]
        unique_new_model_ids.update(
            model["modelId"] for model in new_models if model.get("modelId")
        )

        rows.append(
            {
                "platform": platform_id,
                "name": names.get(platform_id, platform_id),
                "suggested_provider_slug": suggested_slug,
                "provider_card_exists": has_provider_card,
                "chat_models": len(models),
                "new_model_ids": len(new_models),
                "new_model_examples": [
                    model.get("modelId") for model in new_models[:5]
                ],
                "quirks": len(quirks_for_platform(payload, platform_id, models)),
            }
        )

    rows.sort(key=lambda row: (-row["chat_models"], row["platform"]))
    return {
        "catalog_version": payload.get("version"),
        "generated_at": payload.get("generatedAt"),
        "chat_platform_count": len(rows),
        "existing_provider_count": sum(1 for row in rows if row["provider_card_exists"]),
        "new_platform_count": sum(1 for row in rows if not row["provider_card_exists"]),
        "unique_new_model_id_count": len(unique_new_model_ids),
        "note": (
            "Discovery leads only. 'new' means no matching research card was found by "
            "slug/model-id text search; verify before creating cards."
        ),
        "platforms": rows,
    }


def render_candidates_markdown(candidates: dict) -> str:
    """Render the human-readable lead report."""
    lines = [
        f"# FreeLLMAPI catalog leads — v{candidates['catalog_version']}",
        "",
        f"Generated from the public monthly feed at {CATALOG_URL}.",
        "Discovery only: verify every row against official provider docs before "
        "creating or updating `providers/` or `models/` cards.",
        "",
        "## Summary",
        "",
        f"- Chat platforms: {candidates['chat_platform_count']}",
        f"- Already mapped to a provider card: {candidates['existing_provider_count']}",
        f"- New provider leads: {candidates['new_platform_count']}",
        f"- Unique model IDs not found in existing cards: {candidates['unique_new_model_id_count']}",
        "",
        "## Platform leads",
        "",
        "| Platform | Catalog ID | Chat models | New model IDs | Provider card | Quirks |",
        "|---|---|---:|---:|---|---:|",
    ]

    for row in candidates["platforms"]:
        status = "existing" if row["provider_card_exists"] else "NEW"
        lines.append(
            "| {name} | `{platform}` | {chat_models} | {new_model_ids} | "
            "{status} (`{slug}`) | {quirks} |".format(
                name=row["name"],
                platform=row["platform"],
                chat_models=row["chat_models"],
                new_model_ids=row["new_model_ids"],
                status=status,
                slug=row["suggested_provider_slug"],
                quirks=row["quirks"],
            )
        )

    lines.extend(
        [
            "",
            "## Interpretation notes",
            "",
            "- Catalog `limits` are per platform+model; put them in model-card "
            "`providers[].limits`, not provider frontmatter.",
            "- `monthlyTokenBudget` is a display label, not a numeric quota.",
            "- `intelligenceRank` / `speedRank` are FreeLLMAPI's ranks, not our leaderboard ranks.",
            "- Capability flags and quirks are leads; confirm from official docs.",
            "- Some platforms may fail our free-tier rules (payment method, one-time credits).",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    """Fetch, verify, store and summarize the FreeLLMAPI monthly catalog."""
    payload, metadata = fetch_catalog()
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    write_json(TARGET_DIR / "source.json", metadata)
    write_json(TARGET_DIR / "catalog.json", payload)
    write_platform_files(payload)
    write_non_chat(payload)

    candidates = build_candidates(payload)
    write_json(TARGET_DIR / "candidates.json", candidates)
    (TARGET_DIR / "candidates.md").write_text(
        render_candidates_markdown(candidates), encoding="utf-8"
    )

    print(
        f"FreeLLMAPI monthly catalog v{metadata['version']} "
        f"(signature: {metadata['signature_status']})"
    )
    print(f"  platforms: {len(payload.get('platforms', []))}")
    print(f"  chat models: {len(payload.get('models', []))}")
    print(f"  new provider leads: {candidates['new_platform_count']}")
    print(f"  model IDs not seen in cards: {candidates['unique_new_model_id_count']}")
    print(f"  raw data: {TARGET_DIR}")


if __name__ == "__main__":
    main()
