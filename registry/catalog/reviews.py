"""Validate curated free-tier reviews and build the final free dataset.

Generated leads and curated verdicts are re-creatable dev inputs in the global
``~/.agentone/var/cache/free-tier/`` cache (``candidates/`` and ``reviews/``).
This module checks the reviews and writes a deterministic, self-contained
``<root>/free/`` dataset.  It never edits the generated inputs and never invents
a verdict: invalid reviews are reported, not guessed at.

The final dataset is rebuilt from scratch on every run, so deleting or changing
a review always removes the old verdict.  Output is byte-stable and idempotent.
"""

# The writer intentionally mirrors registry.catalog.write's atomic sync loop.
# pylint: disable=duplicate-code

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from registry.catalog.normalize import GENERATED_BY
from registry.catalog.write import write_json

CANDIDATES_DIR = Path("candidates")
REVIEWS_DIR = Path("reviews")
FREE_DIR = Path("free")
MERGED_SOURCE = "free-reviews"  # provenance marker, not a directory path
REVIEW_SCHEMA_VERSION = 1
MERGED_SCHEMA_VERSION = 1
VERDICTS = ("free", "payment_gated", "rejected", "needs_followup")
API_BASE_STATUSES = ("verified", "changed", "unverifiable")

_LIMIT_KEY = re.compile(
    r"^(?:rps|rpm|rph|rpd|tps|tpm|tph|tpd|"
    r"requests_per_(?:week|month)|tokens_per_(?:week|month)|"
    r"concurrency)(?:_(?:model|ip|account))?$"
)
_MONEY_HINTS = ("cost", "price", "credit", "budget", "currency", "usd", "eur", "money", "$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_STALE_DAYS = 365

_REVIEW_FIELDS = {
    "schema_version",
    "provider",
    "name",
    "reviewed_at",
    "sources",
    "api_base",
    "limits",
    "models",
}
_MODEL_FIELDS = {
    "verdict",
    "provider_model_id",
    "conditions",
    "limits",
    "verified",
    "source_ids",
    "notes",
    "gate",
    "reason",
}
_API_BASE_FIELDS = {"value", "status", "verified", "source_ids", "notes"}
_SOURCE_FIELDS = {"id", "url", "title", "accessed"}


@dataclass(frozen=True)
class Issue:
    """One validation problem."""

    level: str
    code: str
    message: str
    provider: str = ""
    model: str = ""

    def format(self) -> str:
        scope = self.provider or "-"
        if self.model:
            scope = f"{scope} {self.model}"
        return f"{self.level} [{scope}] {self.code}: {self.message}"


@dataclass
class MergeResult:
    """Validated merge output plus its problems and counts."""

    documents: dict[str, dict[str, Any]]
    index: dict[str, Any]
    issues: list[Issue]
    counts: dict[str, int]

    @property
    def errors(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.level == "warning"]


def _add(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    issues: list[Issue],
    level: str,
    code: str,
    message: str,
    provider: str = "",
    model: str = "",
) -> None:
    issues.append(Issue(level, code, message, provider, model))


def _is_date(value: Any) -> bool:
    if not isinstance(value, str) or not _ISO_DATE.match(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _check_date(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    value: Any,
    issues: list[Issue],
    code: str,
    label: str,
    provider: str,
    model: str = "",
) -> None:
    if not _is_date(value):
        _add(issues, "error", code, f"{label} must be a YYYY-MM-DD date", provider, model)
        return
    parsed = date.fromisoformat(value)
    if parsed > date.today():
        _add(issues, "warning", f"{code}-future", f"{label} is in the future", provider, model)
    if parsed < date.today() - timedelta(days=_STALE_DAYS):
        _add(issues, "warning", f"{code}-stale", f"{label} is older than {_STALE_DAYS} days", provider, model)


def _valid_limit(key: Any, value: Any) -> bool:
    text = str(key)
    lowered = text.lower()
    if any(hint in lowered for hint in _MONEY_HINTS):
        return False
    if not _LIMIT_KEY.match(text):
        return False
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _sanitize_limits(limits: Any) -> dict[str, int]:
    if not isinstance(limits, dict):
        return {}
    return {str(key): value for key, value in sorted(limits.items()) if _valid_limit(key, value)}


def _check_limits(
    limits: Any,
    issues: list[Issue],
    provider: str,
    model: str = "",
) -> dict[str, int]:
    if limits is None:
        return {}
    if not isinstance(limits, dict):
        _add(issues, "error", "invalid-limits", "limits must be an object", provider, model)
        return {}
    for key, value in sorted(limits.items()):
        if not _valid_limit(key, value):
            _add(
                issues,
                "error",
                "invalid-limit",
                f"{key!r} is not a canonical positive integer limit",
                provider,
                model,
            )
    return _sanitize_limits(limits)


def _check_sources(
    provider: str,
    sources: Any,
    issues: list[Issue],
) -> dict[str, dict[str, Any]]:
    if sources is None:
        _add(issues, "error", "missing-sources", "review has no sources list", provider)
        return {}
    if not isinstance(sources, list):
        _add(issues, "error", "invalid-sources", "sources must be a list", provider)
        return {}
    if not sources:
        _add(issues, "warning", "empty-sources", "review has an empty sources list", provider)

    by_id: dict[str, dict[str, Any]] = {}
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            _add(issues, "error", "invalid-source", f"sources[{index}] must be an object", provider)
            continue
        unknown = sorted(set(source) - _SOURCE_FIELDS)
        if unknown:
            _add(
                issues,
                "warning",
                "unknown-source-field",
                f"sources[{index}] has unknown keys: {', '.join(unknown)}",
                provider,
            )
        source_id = source.get("id")
        if not isinstance(source_id, str) or not source_id.strip():
            _add(issues, "error", "invalid-source-id", f"sources[{index}] needs a non-empty id", provider)
            continue
        if source_id in by_id:
            _add(issues, "error", "duplicate-source-id", f"duplicate source id {source_id!r}", provider)
            continue
        url = source.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            _add(issues, "error", "invalid-source-url", f"source {source_id!r} needs an http(s) url", provider)
        if "accessed" in source:
            _check_date(source.get("accessed"), issues, "invalid-source-date", f"source {source_id!r} accessed", provider)
        by_id[source_id] = source
    return by_id


def _check_source_ids(
    source_ids: Any,
    source_map: dict[str, dict[str, Any]],
    issues: list[Issue],
    provider: str,
    model: str,
) -> None:
    if not isinstance(source_ids, list) or not source_ids:
        _add(issues, "error", "missing-source-ids", "needs at least one source id", provider, model)
        return
    for source_id in source_ids:
        if not isinstance(source_id, str) or source_id not in source_map:
            _add(issues, "error", "unknown-source-id", f"unknown source id {source_id!r}", provider, model)


def _check_api_base(
    provider: str,
    api_base: Any,
    source_map: dict[str, dict[str, Any]],
    issues: list[Issue],
) -> None:
    if api_base is None:
        return
    if not isinstance(api_base, dict):
        _add(issues, "error", "invalid-api-base", "api_base must be an object", provider)
        return
    unknown = sorted(set(api_base) - _API_BASE_FIELDS)
    if unknown:
        _add(issues, "warning", "unknown-api-base-field", f"api_base has unknown keys: {', '.join(unknown)}", provider)
    if not isinstance(api_base.get("value"), str) or not api_base["value"].strip():
        _add(issues, "error", "invalid-api-base-value", "api_base.value must be a non-empty string", provider)
    status = api_base.get("status")
    if status not in API_BASE_STATUSES:
        _add(issues, "error", "invalid-api-base-status", f"api_base.status must be one of {API_BASE_STATUSES}", provider)
    if "verified" in api_base:
        _check_date(api_base.get("verified"), issues, "invalid-api-base-date", "api_base.verified", provider)
    if status in ("verified", "changed"):
        _check_source_ids(api_base.get("source_ids"), source_map, issues, provider, "api_base")


def _check_model_entry(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    provider: str,
    model: str,
    entry: Any,
    base_candidate: dict[str, Any],
    source_map: dict[str, dict[str, Any]],
    issues: list[Issue],
) -> None:
    if not isinstance(entry, dict):
        _add(issues, "error", "invalid-model-entry", "entry must be an object", provider, model)
        return

    unknown = sorted(set(entry) - _MODEL_FIELDS)
    if unknown:
        _add(issues, "warning", "unknown-model-field", f"unknown keys: {', '.join(unknown)}", provider, model)

    verdict = entry.get("verdict")
    if verdict not in VERDICTS:
        _add(issues, "error", "invalid-verdict", f"verdict must be one of {VERDICTS}", provider, model)
        return

    expected_id = str(base_candidate.get("provider_model_id") or "")
    provider_model_id = entry.get("provider_model_id")
    if provider_model_id not in (None, "") and str(provider_model_id) != expected_id:
        _add(
            issues,
            "error",
            "provider-model-id-mismatch",
            f"expected {expected_id!r}, found {provider_model_id!r}",
            provider,
            model,
        )

    if "verified" in entry:
        _check_date(entry.get("verified"), issues, "invalid-verified", "verified", provider, model)
    else:
        _add(issues, "error", "missing-verified", "verified is required", provider, model)

    _check_source_ids(entry.get("source_ids"), source_map, issues, provider, model)
    _check_limits(entry.get("limits"), issues, provider, model)

    if verdict in ("free", "payment_gated"):
        if not isinstance(entry.get("conditions"), str) or not entry["conditions"].strip():
            _add(issues, "error", "missing-conditions", "conditions is required", provider, model)
        if not provider_model_id:
            _add(issues, "error", "missing-provider-model-id", "provider_model_id is required", provider, model)
    if verdict == "payment_gated" and (not isinstance(entry.get("gate"), str) or not entry["gate"].strip()):
        _add(issues, "error", "missing-gate", "gate is required for payment_gated", provider, model)
    if verdict in ("rejected", "needs_followup") and (
        not isinstance(entry.get("reason"), str) or not entry["reason"].strip()
    ):
        _add(issues, "error", "missing-reason", "reason is required", provider, model)

    if "notes" in entry and not isinstance(entry["notes"], str):
        _add(issues, "error", "invalid-notes", "notes must be a string", provider, model)


def load_free_documents(
    free_dir: Path,
    issues: list[Issue],
) -> dict[str, dict[str, Any]]:
    """Read generated per-provider free documents."""
    documents: dict[str, dict[str, Any]] = {}
    if not free_dir.is_dir():
        _add(issues, "error", "missing-free-dir", f"no generated candidate directory at {free_dir}")
        return documents
    for path in sorted(free_dir.glob("*.json")):
        if path.name == "index.json":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            _add(issues, "error", "invalid-free-json", f"{path.name}: {exc}")
            continue
        if not isinstance(payload, dict):
            _add(issues, "error", "invalid-free-document", f"{path.name} must be an object")
            continue
        provider = str(payload.get("provider") or path.stem)
        if provider != path.stem:
            _add(
                issues,
                "warning",
                "free-provider-filename-mismatch",
                f"provider {provider!r} does not match {path.name}",
                provider,
            )
        documents[provider] = payload
    return documents


def load_reviews(
    reviews_dir: Path,
    free_documents: dict[str, dict[str, Any]],
    issues: list[Issue],
) -> dict[str, dict[str, Any]]:
    """Read review files and reject ones that cannot be merged."""
    reviews: dict[str, dict[str, Any]] = {}
    if not reviews_dir.is_dir():
        _add(issues, "error", "missing-reviews-dir", f"no review directory at {reviews_dir}")
        return reviews
    paths = sorted(reviews_dir.glob("*.json"))
    if not paths:
        _add(issues, "error", "no-reviews", f"no review files in {reviews_dir}")
        return reviews

    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            _add(issues, "error", "invalid-review-json", f"{path.name}: {exc}")
            continue
        if not isinstance(payload, dict):
            _add(issues, "error", "invalid-review-document", f"{path.name} must be an object")
            continue

        provider = str(payload.get("provider") or path.stem)
        if provider != path.stem:
            _add(
                issues,
                "error",
                "review-provider-filename-mismatch",
                f"provider {provider!r} does not match {path.name}",
                provider,
            )
        if provider in reviews:
            _add(issues, "error", "duplicate-review-provider", f"duplicate review for {provider}", provider)
            continue
        if provider not in free_documents:
            _add(
                issues,
                "error",
                "unknown-provider",
                f"no generated candidate file for provider {provider!r}",
                provider,
            )
            continue
        reviews[provider] = payload
    return reviews


def validate_review(
    provider: str,
    review: dict[str, Any],
    base_document: dict[str, Any],
    issues: list[Issue],
) -> dict[str, dict[str, Any]]:
    """Validate one review and return its source-id map."""
    unknown = sorted(set(review) - _REVIEW_FIELDS)
    if unknown:
        _add(issues, "warning", "unknown-review-field", f"unknown keys: {', '.join(unknown)}", provider)

    if review.get("schema_version") != REVIEW_SCHEMA_VERSION:
        _add(
            issues,
            "error",
            "invalid-schema-version",
            f"schema_version must be {REVIEW_SCHEMA_VERSION}",
            provider,
        )
    if "name" in review and not isinstance(review["name"], str):
        _add(issues, "error", "invalid-name", "name must be a string", provider)
    _check_date(review.get("reviewed_at"), issues, "invalid-reviewed-at", "reviewed_at", provider)

    source_map = _check_sources(provider, review.get("sources"), issues)
    _check_api_base(provider, review.get("api_base"), source_map, issues)
    _check_limits(review.get("limits"), issues, provider)

    base_candidates = {
        str(candidate.get("model")): candidate
        for candidate in base_document.get("candidates") or []
        if isinstance(candidate, dict)
    }
    models = review.get("models")
    if not isinstance(models, dict):
        _add(issues, "error", "invalid-models", "models must be an object", provider)
        return source_map
    if not models:
        _add(issues, "warning", "empty-models", "models is empty", provider)

    for model, entry in sorted(models.items()):
        model_key = str(model)
        candidate = base_candidates.get(model_key)
        if candidate is None:
            _add(issues, "error", "unknown-model", f"no generated candidate named {model_key!r}", provider, model_key)
            continue
        _check_model_entry(provider, model_key, entry, candidate, source_map, issues)

    for model in sorted(set(base_candidates) - {str(key) for key in models}):
        _add(issues, "warning", "unreviewed-candidate", "candidate has no review entry", provider, model)

    return source_map


def _merged_candidate(
    candidate: dict[str, Any],
    entry: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(candidate)
    if not entry:
        return merged
    for key in ("verdict", "conditions", "verified", "gate", "source_ids", "notes"):
        value = entry.get(key)
        if value not in (None, "", [], {}):
            merged[key] = value
    review_limits = _sanitize_limits(entry.get("limits"))
    if review_limits:
        merged["limits"] = {**(merged.get("limits") or {}), **review_limits}
    return merged


def build_merged_documents(
    free_documents: dict[str, dict[str, Any]],
    reviews: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, int]]:
    # pylint: disable=too-many-locals
    """Build the merged per-provider documents and index."""
    documents: dict[str, dict[str, Any]] = {}
    index_rows: list[dict[str, Any]] = []
    total_candidates = 0
    total_reviewed = 0
    verdicts: Counter[str] = Counter()

    for provider in sorted(free_documents):
        base = free_documents[provider]
        review = reviews.get(provider) or {}
        entries = review.get("models") if isinstance(review.get("models"), dict) else {}
        candidates = []
        for candidate in sorted(base.get("candidates") or [], key=lambda item: str(item.get("model") or "")):
            model = str(candidate.get("model") or "")
            entry = entries.get(model)
            merged = _merged_candidate(candidate, entry)
            if merged.get("verdict") in VERDICTS:
                total_reviewed += 1
                verdicts[str(merged["verdict"])] += 1
            candidates.append(merged)
        total_candidates += len(candidates)

        document: dict[str, Any] = {
            "_generated_by": GENERATED_BY,
            "generated_from": MERGED_SOURCE,
            "schema_version": MERGED_SCHEMA_VERSION,
            "provider": provider,
            "name": base.get("name") or provider,
            "candidate_count": len(candidates),
            "sources": list(base.get("sources") or []),
            "candidates": candidates,
        }
        review_verdicts = Counter(
            str(candidate.get("verdict"))
            for candidate in candidates
            if candidate.get("verdict") in VERDICTS
        )
        if review:
            document["reviewed_at"] = review.get("reviewed_at")
            document["review_sources"] = list(review.get("sources") or [])
            if review.get("api_base"):
                document["api_base"] = review["api_base"]
            review_limits = _sanitize_limits(review.get("limits"))
            if review_limits:
                document["limits"] = review_limits
        document["reviewed_count"] = sum(review_verdicts.values())
        if review_verdicts:
            document["verdicts"] = dict(sorted(review_verdicts.items()))

        documents[f"{provider}.json"] = document
        index_rows.append(
            {
                "provider": provider,
                "file": f"{provider}.json",
                "name": document["name"],
                "candidate_count": len(candidates),
                "reviewed_count": document["reviewed_count"],
                "verdicts": document.get("verdicts") or {},
            }
        )

    counts = {
        "providers": len(documents),
        "candidates": total_candidates,
        "reviewed": total_reviewed,
        "unreviewed": total_candidates - total_reviewed,
        **{verdict: verdicts.get(verdict, 0) for verdict in VERDICTS},
    }
    index = {
        "_generated_by": GENERATED_BY,
        "generated_from": MERGED_SOURCE,
        "schema_version": MERGED_SCHEMA_VERSION,
        "counts": counts,
        "providers": index_rows,
    }
    return documents, index, counts


def collect_reviews(
    root: Path,
    *,
    free_dir: Path | None = None,
    reviews_dir: Path | None = None,
) -> MergeResult:
    """Load, validate and merge reviews without writing anything."""
    root = Path(root)
    issues: list[Issue] = []
    free_documents = load_free_documents(free_dir or root / CANDIDATES_DIR, issues)
    reviews = load_reviews(reviews_dir or root / REVIEWS_DIR, free_documents, issues)

    for provider, review in sorted(reviews.items()):
        base = free_documents.get(provider)
        if base is None:
            continue
        validate_review(provider, review, base, issues)

    documents, index, counts = build_merged_documents(free_documents, reviews)
    return MergeResult(documents=documents, index=index, issues=issues, counts=counts)


def _is_merged(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (
        isinstance(payload, dict)
        and payload.get("_generated_by") == GENERATED_BY
        and payload.get("generated_from") == MERGED_SOURCE
    )


def sync_merged(
    documents: dict[str, dict[str, Any]],
    index: dict[str, Any],
    output_dir: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Write the merged dataset and prune stale merged files only."""
    output_dir = Path(output_dir)
    expected = {
        output_dir / name: document for name, document in sorted(documents.items())
    }
    expected[output_dir / "index.json"] = index
    written = 0
    unchanged = 0
    removed: list[str] = []

    for path, record in sorted(expected.items(), key=lambda item: str(item[0])):
        text = json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        if path.exists():
            if path.read_text(encoding="utf-8") == text:
                unchanged += 1
                continue
            if not _is_merged(path):
                raise ValueError(f"Refusing to overwrite non-merged file: {path}")
        if not dry_run:
            write_json(path, record)
        written += 1

    if output_dir.is_dir():
        for path in sorted(output_dir.glob("*.json")):
            if path in expected or not _is_merged(path):
                continue
            if not dry_run:
                path.unlink()
            removed.append(path.name)

    return {
        "written": written,
        "unchanged": unchanged,
        "removed": len(removed),
        "removed_examples": removed[:20],
        "total_files": len(expected),
        "directory": output_dir.as_posix(),
        "dry_run": dry_run,
    }
