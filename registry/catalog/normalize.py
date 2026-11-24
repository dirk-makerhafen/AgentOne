"""Deterministic normalization and merge helpers for the catalog builder.

All functions here are pure: the same raw source files must always produce
the same canonical dataset.  When sources disagree, a fixed priority order
(``SOURCE_PRIORITY``) decides which value wins; the losing values are still
recorded per-record under ``sources`` / ``aliases`` so nothing is lost.
"""

from __future__ import annotations

import fnmatch
import re
from typing import Any, Iterable

SOURCE_PRIORITY: tuple[str, ...] = (
    "opencode-models-api",
    "freellmapi-catalog",
    "awesome-free-llm-apis",
)

GENERATED_BY = "registry.catalog"
# Marker for model/provider records synthesized from free-candidate evidence.
# They are generated files, but the main catalog pass must not prune them.
FREE_MODEL_SOURCE = "free-candidates"

# opencode's provider entries omit ``api`` when the npm runtime has a fixed
# public endpoint baked in (the AI SDK default).  These defaults are pinned
# here so a provider like Anthropic is not mistaken for "no API".  Packages
# that require account/project-specific URLs (Azure, Bedrock, Vertex, SAP, ...)
# are deliberately absent: they cannot yield one static base URL.
SDK_DEFAULT_API_BASES: dict[str, str] = {
    "@ai-sdk/anthropic": "https://api.anthropic.com/v1",
    "@ai-sdk/cerebras": "https://api.cerebras.ai/v1",
    "@ai-sdk/deepinfra": "https://api.deepinfra.com/v1",
    "@ai-sdk/gateway": "https://ai-gateway.vercel.sh/v4/ai",
    "@ai-sdk/mistral": "https://api.mistral.ai/v1",
    "@ai-sdk/openai": "https://api.openai.com/v1",
    "@ai-sdk/perplexity": "https://api.perplexity.ai",
    "@ai-sdk/togetherai": "https://api.together.xyz/v1",
    "@ai-sdk/vercel": "https://api.v0.dev/v1",
    "@ai-sdk/xai": "https://api.x.ai/v1",
    "venice-ai-sdk-provider": "https://api.venice.ai/api/v1",
}

# Access/edition suffixes that are provider-specific noise for identity
# purposes.  They are kept in the record's aliases, just not in the slug.
_MODEL_NOISE_SUFFIXES = ("free", "preview", "beta", "latest", "experimental")

# Some upstream feeds join the org to the model with a dash instead of a slash
# (``zai-org-glm-4.6``). Slash namespaces are dropped generically below, so
# strip these known spellings too or the same model gets two canonical slugs.
_HYPHENATED_ORG_PREFIX = re.compile(r"^(?:zai-org|z-ai|zai|moonshot)-")
# The same org namespace is sometimes written with a dot (``aion-labs.aion-2-0``)
# instead of a slash.  Require a hyphenated, letter-only prefix so dotted model
# names (``dots.ocr``, ``flux.1-dev``) and version dots (``claude-3.5``,
# ``gpt-5.2``) are never mistaken for a namespace; single-word vendors are
# already covered by the list below.
_DOTTED_ORG_PREFIX = re.compile(r"^[a-z][a-z-]*-[a-z][a-z-]*\.")
_REGION_PREFIX = re.compile(r"^(?:us-gov|us|eu|apac|global)\.", re.I)
# Bedrock-style IDs can carry both a region and a vendor namespace
# (``us.anthropic.claude-...``); drop the vendor segment too.
_DOTTED_VENDOR_NAMESPACES = {
    "anthropic", "cohere", "deepseek", "google", "meta", "mistral",
    "openai", "qwen", "xai",
}
_VERSION_DOT = re.compile(r"\.(\d+)")
_SIZE = re.compile(r"^\s*([\d][\d.,]*)\s*([kmb]?)\s*$", re.I)
# Human quota labels use many spellings: "20 RPM", "200 req/hr", "1M
# tokens/month", "2/min per IP", "1 concurrent request".  One regex with
# optional scale/qualifier groups covers all of them; raw labels are preserved
# alongside the parsed numbers so the verification pass can review the result.
_RATE = re.compile(
    r"(?<![\w/$€£.])(?:[~≈<>=]\s*)?"
    r"(?P<number>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<scale>[KMB])?\s*"
    r"(?P<extra>(?:weighted|free-model|shared)\s+)?"
    r"(?P<kind>tokens?|toks?|requests?|reqs?|calls?|concurrent\s+requests?)?\s*"
    r"(?P<unit>/?\s*(?:RPS|RPD|RPM|RPH|TPS|TPD|TPM|TPH|"
    r"mins?|minutes?|hours?|hrs?|hr|days?|24h|weeks?|months?|mo))?"
    r"(?:\s*(?:/|per)\s*(?P<scope>model|ip|account))?",
    re.I,
)
_BARE_BUDGET = re.compile(r"^\s*[~≈]?\s*(\d[\d,]*(?:\.\d+)?)\s*([KMB])\s*$", re.I)
_SCALES = {"": 1, "k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
_COMPACT_UNITS = {
    "rps": "rps", "rpm": "rpm", "rph": "rph", "rpd": "rpd",
    "tps": "tps", "tpm": "tpm", "tph": "tph", "tpd": "tpd",
}
_PERIODS = {
    "min": "min", "minute": "min", "minutes": "min",
    "hr": "hr", "hrs": "hr", "hour": "hr", "hours": "hr",
    "day": "day", "days": "day", "24h": "day",
    "week": "week", "weeks": "week",
    "mo": "month", "month": "month", "months": "month",
}
_KEYS_BY_PERIOD = {
    "request": {"min": "rpm", "hr": "rph", "day": "rpd", "week": "requests_per_week", "month": "requests_per_month"},
    "token": {"min": "tpm", "hr": "tph", "day": "tpd", "week": "tokens_per_week", "month": "tokens_per_month"},
}
_SCOPE_SUFFIXES = {"model": "_model", "ip": "_ip", "account": "_account"}

# Source identifiers that refer to the same provider as a canonical slug.
# Keep this table small and explicit: silent fuzzy matching creates duplicates.
PROVIDER_ALIASES: dict[str, str] = {
    # opencode / freellmapi id -> canonical research slug
    "agnes": "agnes-ai",
    "aion": "aion-labs",
    "aihorde": "ai-horde",
    "airforce": "api-airforce",
    "api-airforce": "api-airforce",
    "cloudflare": "cloudflare-workers-ai",
    "deepseek": "deepseek-platform",
    "empiriolabs-ai": "empiriolabs",
    "freeai": "free-ai",
    "google": "google-gemini",
    "google-gemini": "google-gemini",
    "hugging-face": "huggingface",
    "kilo": "kilo-code",
    "kilo-gateway": "kilo-code",
    "llm-gateway": "llmgateway",
    "llm7-io": "llm7",
    "nvidia": "nvidia-nim",
    "opencode": "opencode-zen",
    "ovh": "ovhcloud-ai-endpoints",
    "ovhcloud": "ovhcloud-ai-endpoints",
    "radeon": "amd-radeon",
    "sealion": "sea-lion",
    "septor": "septor-labs",
    "vercel": "vercel-ai-gateway",
    "zai": "z-ai",
    "zhipu": "z-ai",
    "zhipuai": "z-ai",
    "z-ai-zhipu-ai": "z-ai",
}

# Known model developer prefixes.  Only used to fill ``developer`` when no
# source states it explicitly; never overrides an explicit value.
DEVELOPER_HINTS: dict[str, str] = {
    "openai": "OpenAI",
    "google": "Google",
    "gemini": "Google",
    "anthropic": "Anthropic",
    "claude": "Anthropic",
    "meta": "Meta",
    "llama": "Meta",
    "mistral": "Mistral AI",
    "deepseek": "DeepSeek",
    "qwen": "Alibaba Qwen",
    "glm": "Zhipu AI",
    "grok": "xAI",
    "kimi": "Moonshot AI",
    "gemma": "Google",
    "command": "Cohere",
    "nemotron": "NVIDIA",
    "phi": "Microsoft",
    "jamba": "AI21 Labs",
}


def slugify(value: Any) -> str:
    """Stable filename-style slug (same rule as the research cards)."""
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return slug or "unknown"


def canonical_model_slug(raw_id: Any) -> str:
    """Return the canonical slug for a provider-specific model ID.

    Handles the messy real-world variants found in the three upstream feeds:

    * namespaces (``openai/gpt-oss-120b``, ``@cf/meta/llama-3.2-1b``)
    * access suffixes (``:free``, ``-free``, ``-preview``)
    * separator/case differences (``GLM-5.3`` vs ``glm_5_3`` vs ``glm-5-3``)
    * cloud region prefixes (``us.anthropic.claude-...``)
    * known hyphenated org prefixes (``zai-org-glm-4.6`` → ``glm-4-6``)
    * dotted org prefixes (``aion-labs.aion-2-0`` → ``aion-2-0``)
    """
    text = str(raw_id or "").strip().lower()
    if not text:
        return "unknown"

    if text.startswith("accounts/") and "/models/" in text:
        text = text.split("/models/", 1)[1]
    text = text.split("/", -1)[-1]
    text = text.split(":", 1)[0]
    text = _HYPHENATED_ORG_PREFIX.sub("", text, count=1)
    text = _REGION_PREFIX.sub("", text)
    if _DOTTED_ORG_PREFIX.match(text):
        text = text.partition(".")[2]
    namespace, dot, remainder = text.partition(".")
    if dot and namespace in _DOTTED_VENDOR_NAMESPACES:
        text = remainder
    text = re.sub(r"[@_\s]+", "-", text)
    text = _VERSION_DOT.sub(r"-\1", text)
    text = re.sub(r"[^a-z0-9._-]+", "-", text)
    text = re.sub(r"[-_.]+", "-", text).strip("-")

    # Iterate: suffixes can stack, e.g. ``model-free-preview``.
    changed = True
    while changed:
        changed = False
        for suffix in _MODEL_NOISE_SUFFIXES:
            if text.endswith("-" + suffix):
                text = text[: -(len(suffix) + 1)]
                changed = True
    return text.strip("-") or "unknown"


def resolve_provider_slug(raw_id: Any, name: Any = "") -> str:
    """Resolve an upstream provider id/name onto a canonical directory slug.

    The upstream id wins over the display name: catalog names such as
    "LLM Gateway" would otherwise create a second ``llm-gateway`` directory
    next to the existing ``llmgateway`` one.
    """
    candidates = [slugify(raw_id), slugify(name)]
    for candidate in candidates:
        if candidate in PROVIDER_ALIASES:
            return PROVIDER_ALIASES[candidate]
    for candidate in candidates:
        if candidate not in ("unknown", ""):
            return candidate
    return "unknown"


def parse_size(value: Any) -> int | None:
    """Parse a human size label (``131K``, ``1M``, ``8192``) into an int."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    match = _SIZE.match(str(value or ""))
    if not match:
        return None
    number = float(match.group(1).replace(",", ""))
    multiplier = {"": 1, "k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[
        (match.group(2) or "").lower()
    ]
    return int(number * multiplier)


def _scaled_number(number: str, scale: str | None) -> int:
    return int(float(number.replace(",", "")) * _SCALES[(scale or "").lower()])


def _limit_key(kind: str | None, unit: str) -> str | None:
    compact = "".join(unit.split()).lstrip("/").lower()
    if compact in _COMPACT_UNITS:
        return _COMPACT_UNITS[compact]
    period = _PERIODS.get(compact)
    if not period:
        return None
    family = "token" if str(kind or "").lower().startswith("tok") else "request"
    return _KEYS_BY_PERIOD[family][period]


def parse_rate_limit(value: Any) -> dict[str, int]:
    """Parse a quota label into numeric keys, keeping the raw label elsewhere.

    Understands ``30 RPM, 1,000 RPD``, ``200 req/hr``, ``20K TPD``,
    ``~1M tokens/month``, ``2/min per IP`` and ``1 concurrent request``.
    Currency amounts, ranges and non-request units (for example "neurons/day")
    are deliberately ignored rather than guessed.
    """
    if not isinstance(value, str):
        return {}
    result: dict[str, int] = {}
    for match in _RATE.finditer(value):
        unit = match.group("unit")
        kind = match.group("kind")
        if not unit and not kind:
            continue
        if kind and "concurrent" in kind.lower():
            key = "concurrency"
        else:
            key = _limit_key(kind, unit or "")
        if not key:
            continue
        scope = match.group("scope")
        if scope:
            key += _SCOPE_SUFFIXES[scope.lower()]
        # First occurrence wins: parenthetical notes often restate a smaller
        # per-model/anonymous quota that should not replace the overall limit.
        result.setdefault(key, _scaled_number(match.group("number"), match.group("scale")))
    return result


def parse_budget_limits(value: Any) -> dict[str, int]:
    """Parse a FreeLLMAPI ``monthlyTokenBudget`` label.

    In addition to the usual quota patterns this accepts a bare scaled amount
    such as ``~3M`` (tokens per month).  Ranges like ``~10-20M`` are left alone;
    the original label is preserved as ``quota_label`` for manual review.
    """
    result = parse_rate_limit(value)
    if not isinstance(value, str) or "tokens_per_month" in result:
        return result
    match = _BARE_BUDGET.match(value)
    if match:
        result["tokens_per_month"] = _scaled_number(match.group(1), match.group(2))
    return result


def first_value(
    records: Iterable[dict[str, Any]],
    field: str,
    *,
    default: Any = None,
) -> Any:
    """First non-empty value for *field* across records in priority order."""
    for record in records:
        value = record.get(field)
        if value not in (None, "", [], {}):
            return value
    return default


def infer_developer(canonical_slug: str, raw_ids: Iterable[Any]) -> str:
    """Best-effort developer name from a namespaced model ID."""
    prefix = canonical_slug.split("-", 1)[0]
    hint = DEVELOPER_HINTS.get(prefix)
    if hint:
        return hint
    for raw in raw_ids:
        text = str(raw or "")
        namespace = text.split("/", 1)[0].lstrip("@").lower()
        hint = DEVELOPER_HINTS.get(namespace)
        if hint:
            return hint
    return ""


def sort_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic source provenance ordering."""
    def key(item: dict[str, Any]) -> tuple[int, str, str]:
        try:
            priority = SOURCE_PRIORITY.index(item.get("source", ""))
        except ValueError:
            priority = len(SOURCE_PRIORITY)
        return priority, str(item.get("provider", "")), str(item.get("raw_id", ""))

    return sorted(sources, key=key)


def dedupe(values: Iterable[Any]) -> list[str]:
    """Sorted unique string values."""
    return sorted({str(value) for value in values if value not in (None, "")})


def catalog_quirks(
    payload: dict[str, Any],
    platform_id: str,
    model_id: str | None = None,
) -> list[dict[str, Any]]:
    """FreeLLMAPI quirks targeting one platform, optionally one model glob.

    The public feed stores quirk definitions once at the top level and points
    to affected platforms/models with ``targets``.  Returning only the matched
    subset keeps model records small without losing a stated caveat.
    """
    result: list[dict[str, Any]] = []
    for quirk in payload.get("quirks") or []:
        for target in quirk.get("targets") or []:
            if str(target.get("platform")) != str(platform_id):
                continue
            glob = target.get("modelGlob")
            if model_id is not None and glob and not fnmatch.fnmatch(str(model_id), str(glob)):
                continue
            result.append(
                {key: quirk.get(key) for key in ("slug", "title", "body", "severity")}
            )
            break
    return result
