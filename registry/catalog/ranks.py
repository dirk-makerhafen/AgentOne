"""Model leaderboard ranks: download, match, and curate them.

The old research tree had a one-off ``generate_leaderboard.py`` that mixed
Hugging Face's LMArena ratings with ZeroEval benchmark scores, then wrote a CSV
that fed model-card frontmatter.  This module keeps that idea in the catalog
pipeline:

* ``download_leaderboard`` refreshes the raw inputs in the free-tier cache and
  rebuilds a deterministic ``leaderboard.csv``;
* ``match_leaderboard`` maps leaderboard IDs onto canonical model slugs using
  exact, normalized and alias matches from the generated model files;
* ``apply_ranks`` writes ``leaderboard_id`` / ``leaderboard_rank`` /
  ``leaderboard_rank_estimated`` onto every provider record for a model;
* ``export_markdown`` / ``parse_markdown`` maintain ``docs/model-ranks.md``, the
  editable table agents use to fill in missing ranks by research.

Generated catalog files never use the ranks as a source: the markdown table is
the curated overlay and is re-applied on every refresh.
"""

from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Any

from registry.catalog.normalize import canonical_model_slug, slugify
from registry.catalog.write import write_json
from runtime.paths import free_tier_cache_dir

LEADERBOARD_DIRNAME = "leaderboard"
LEADERBOARD_CSV = "leaderboard.csv"
SCORES_JSON = "model_scores.json"
RANKS_FILE = Path("docs/model-ranks.md")
_REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = _REPO_ROOT / "docs/free-tier-research/raw/rankings/leaderboard.csv"
SNAPSHOT_SCORES_PATH = _REPO_ROOT / "docs/free-tier-research/raw/rankings/model_scores.json"
HF_PARQUET_URL = (
    "https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset/"
    "resolve/main/text/latest-00000-of-00001.parquet"
)
ZEROEVAL_URL = "https://api.zeroeval.com/stats/v1/scores"
ZEROEVAL_CATEGORIES = ("code", "coding", "reasoning", "agents", "tool_calling")
ZEROEVAL_KEY_ENV = "ZEROEVAL_API_KEY"
LEGACY_KEY_FILE = _REPO_ROOT / "docs/free-tier-research/scripts/secret_api_keys"

RANK_FIELDS = ("leaderboard_id", "leaderboard_rank", "leaderboard_rank_estimated")
_ESTIMATE = re.compile(r"^~\s*(\d+)$")
_INTEGER = re.compile(r"^\d+$")
# Catalog names often arrive as ``Vendor: Model (Provider)`` or
# ``vendor/model``. Sorting on that groups by vendor instead of by model, so
# derive the bare model name for the rank table. Bracketed IDs such as
# ``[ctx:65536] Magidonia`` are deliberately left alone.
_LEADING_VENDOR = re.compile(r"^([^:\[\]()]{1,40})[:/]\s*")
_LEADING_BRACKET = re.compile(r"^\[[^\]]*\]\s*")
_TRAILING_ANNOTATION = re.compile(r"\s*\([^)]*\)\s*$")


def leaderboard_cache_dir() -> Path:
    """Return the cache directory holding raw leaderboard inputs and output."""
    return free_tier_cache_dir() / LEADERBOARD_DIRNAME


def ranks_file(root: Path) -> Path:
    """Return the editable markdown table for a manifest root."""
    return Path(root).parent / RANKS_FILE


def clean_model_id(model_id: Any) -> str:
    """Normalize a leaderboard ID the same way the legacy generator did.

    Dated builds, preview/ throttle suffixes and four-digit version tails are
    folded into the base model name so different spellings share one rank.
    """
    text = str(model_id or "").strip()
    if "-202" in text:
        text = text.split("-202", 1)[0]
    if "-preview-" in text:
        text = text.split("-preview-", 1)[0]
    for suffix in (
        " (xHigh)",
        "-xhigh",
        "-high",
        "-medium",
        " (thinking-minimal)",
        " (non-thinking)",
        "-preview",
    ):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            break
    if text.endswith("-max") and "qwen" not in text:
        text = text[:-4]
    if "-" in text:
        tail = text.rsplit("-", 1)[-1]
        if len(tail) == 4 and tail.isdigit():
            text = text[:-5]
    return text.strip()


def _match_key(value: Any) -> str:
    """Comparison key shared by exact and normalized leaderboard matches."""
    cleaned = clean_model_id(value)
    return canonical_model_slug(cleaned)


def zeroeval_token(explicit: str | None = None) -> str | None:
    """Resolve the ZeroEval bearer token without ever printing it."""
    if explicit:
        return explicit
    env = os.environ.get(ZEROEVAL_KEY_ENV, "").strip()
    if env:
        return env
    if LEGACY_KEY_FILE.is_file():
        for line in LEGACY_KEY_FILE.read_text(encoding="utf-8").splitlines():
            if ":" not in line:
                continue
            name, value = line.split(":", 1)
            if name.strip().upper() in ("ZEROEVAL", "ZEROEVAL_API_KEY"):
                return value.strip()
    return None


def _download_parquet(cache_dir: Path) -> dict[str, list[float]]:
    import pandas as pd  # pylint: disable=import-outside-toplevel

    try:
        import requests  # pylint: disable=import-outside-toplevel
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("requests is required to download the leaderboard") from exc

    path = Path(cache_dir) / "lmsys-arena-latest.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(HF_PARQUET_URL, stream=True, timeout=120) as response:
        response.raise_for_status()
        with path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1 << 16):
                handle.write(chunk)

    frame = pd.read_parquet(path)
    overall = frame[frame["category"] == "overall"].sort_values("rating", ascending=False)
    scores: dict[str, list[float]] = {}
    for _, row in overall.iterrows():
        model_id = _match_key(row.get("model_name", ""))
        if model_id:
            scores.setdefault(f"{model_id}\thf_elo", []).append(float(row.get("rating", 0)))
    path.unlink(missing_ok=True)
    return scores


def _download_zeroeval(cache_dir: Path, token: str) -> tuple[dict[str, list[float]], dict[str, str], dict[str, str]]:
    import requests  # pylint: disable=import-outside-toplevel

    scores: dict[str, list[float]] = {}
    names: dict[str, str] = {}
    orgs: dict[str, str] = {}
    headers = {"Authorization": f"Bearer {token}"}
    for category in ZEROEVAL_CATEGORIES:
        cursor: str | None = None
        for _ in range(100):
            params = {"category": category, "limit": 500}
            if cursor:
                params["cursor"] = cursor
            response = requests.get(ZEROEVAL_URL, params=params, headers=headers, timeout=120)
            response.raise_for_status()
            payload = response.json()
            for item in payload.get("scores") or []:
                model_id = _match_key(item.get("model_id"))
                if not model_id:
                    continue
                if item.get("model_name"):
                    names[model_id] = str(item["model_name"])
                if item.get("organization"):
                    orgs[model_id] = str(item["organization"])
                normalized = item.get("normalized_score")
                if normalized is None:
                    continue
                benchmark = str(item.get("benchmark_id") or "unknown")
                scores.setdefault(f"{model_id}\t{benchmark}", []).append(float(normalized))
            cursor = payload.get("next_cursor")
            if not cursor:
                break
    return scores, names, orgs


def compute_leaderboard(
    model_scores: dict[str, Any],
    names: dict[str, str] | None = None,
    orgs: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Combine benchmark contests into one conservative TrueSkill ranking."""
    import pandas as pd  # pylint: disable=import-outside-toplevel
    import trueskill  # pylint: disable=import-outside-toplevel

    averages: dict[str, float] = {}
    for key, value in model_scores.items():
        if isinstance(value, list):
            if not value:
                continue
            averages[key] = sum(float(item) for item in value) / len(value)
        elif value is not None:
            averages[key] = float(value)

    records = [
        (key.split("\t", 1)[0], key.split("\t", 1)[1] if "\t" in key else "unknown", score)
        for key, score in averages.items()
    ]
    if not records:
        return []

    frame = pd.DataFrame(records, columns=["model_id", "benchmark_id", "normalized_score"])
    frame = frame.drop_duplicates(subset=["model_id", "benchmark_id", "normalized_score"])
    env = trueskill.TrueSkill(
        mu=25.0,
        sigma=8.333,
        beta=4.167,
        tau=0.083,
        draw_probability=0.0,
    )
    ratings = {model_id: env.create_rating() for model_id in frame["model_id"].unique()}
    for _, group in frame.groupby("benchmark_id"):
        ordered = group.sort_values(by="normalized_score", ascending=False)
        if len(ordered) < 2:
            continue
        teams = [[ratings[row.model_id]] for row in ordered.itertuples()]
        try:
            updated = env.rate(teams, ranks=list(range(len(ordered))))
        except ValueError:
            continue
        for index, row in enumerate(ordered.itertuples()):
            ratings[row.model_id] = updated[index][0]

    rows = []
    for model_id, rating in ratings.items():
        rows.append(
            {
                "Rank": 0,
                "Model ID": model_id,
                "Name": (names or {}).get(model_id, ""),
                "Organization": (orgs or {}).get(model_id, ""),
                "Score": round(rating.mu - (3 * rating.sigma), 2),
            }
        )
    rows.sort(key=lambda row: (-row["Score"], row["Model ID"]))
    for index, row in enumerate(rows, start=1):
        row["Rank"] = index
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["Rank", "Model ID", "Name", "Organization", "Score"],
        )
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def read_csv(path: Path) -> list[dict[str, Any]]:
    """Read a leaderboard CSV into typed rows."""
    with Path(path).open(encoding="utf-8", newline="") as handle:
        rows = []
        for record in csv.DictReader(handle):
            model_id = str(record.get("Model ID") or "").strip()
            if not model_id:
                continue
            try:
                rank = int(record.get("Rank") or 0)
            except ValueError:
                rank = 0
            rows.append(
                {
                    "Rank": rank,
                    "Model ID": model_id,
                    "Name": str(record.get("Name") or "").strip(),
                    "Organization": str(record.get("Organization") or "").strip(),
                    "Score": record.get("Score") or "",
                }
            )
        return rows


def _snapshot_scores(path: Path) -> tuple[dict[str, list[float]], dict[str, str]]:
    """Fold the legacy score snapshot into the current key/name convention.

    The live feeds rotate older models out. Keeping the snapshot as a lower
    priority layer means those models keep a rank instead of silently becoming
    blank in the curated table. The snapshot benchmark is namespaced so its
    ratings form a separate TrueSkill contest rather than mixing two dataset
    vintages into one.
    """
    if not Path(path).is_file():
        return {}, {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    scores: dict[str, list[float]] = {}
    names: dict[str, str] = {}
    if isinstance(payload, dict):
        for key, value in payload.items():
            model_id, _, benchmark = str(key).partition("\t")
            slug = _match_key(model_id)
            if not slug:
                continue
            if isinstance(value, list):
                ratings = [float(item) for item in value]
            elif value is not None:
                ratings = [float(value)]
            else:
                continue
            scores.setdefault(f"{slug}\tsnapshot_{benchmark or 'hf_elo'}", []).extend(ratings)
    csv_path = Path(path).with_name("leaderboard.csv")
    if csv_path.is_file():
        for row in read_csv(csv_path):
            slug = _match_key(row["Model ID"])
            if slug and row.get("Name"):
                names.setdefault(slug, row["Name"])
    return scores, names


def download_leaderboard(
    cache_dir: Path,
    *,
    token: str | None = None,
    offline: bool = False,
    snapshot: Path | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return ranked rows plus human-readable warnings about the fetch."""
    cache_dir = Path(cache_dir)
    output = cache_dir / LEADERBOARD_CSV
    warnings: list[str] = []

    if not offline:
        try:
            scores = _download_parquet(cache_dir)
            names: dict[str, str] = {}
            orgs: dict[str, str] = {}
            try:
                zeroeval_scores, zeroeval_names, zeroeval_orgs = _download_zeroeval(
                    cache_dir, token or ""
                )
            except Exception as exc:  # noqa: BLE001 - partial data still useful
                warnings.append(f"ZeroEval fetch failed ({exc}); using arena ratings only")
                zeroeval_scores, zeroeval_names, zeroeval_orgs = {}, {}, {}
            scores.update(zeroeval_scores)
            names.update(zeroeval_names)
            orgs.update(zeroeval_orgs)
            snapshot_path = Path(snapshot) if snapshot else SNAPSHOT_PATH
            legacy_scores, legacy_names = _snapshot_scores(
                snapshot_path.with_name(SNAPSHOT_SCORES_PATH.name)
            )
            merged_scores = {**legacy_scores, **scores}
            merged_names = {**legacy_names, **names}
            rows = compute_leaderboard(merged_scores, merged_names, orgs)
            scores = merged_scores
            write_json(cache_dir / SCORES_JSON, scores)
            _write_csv(output, rows)
            return rows, warnings
        except Exception as exc:  # noqa: BLE001 - fall back to cached data
            warnings.append(f"live leaderboard download failed ({exc}); using cached data")

    for candidate in (output, snapshot or SNAPSHOT_PATH):
        if candidate and Path(candidate).is_file():
            return read_csv(candidate), warnings
    raise RuntimeError(
        f"no leaderboard data available: checked {output} and {snapshot or SNAPSHOT_PATH}"
    )


def display_name(name: Any, slug: str) -> str:
    """Return a sortable model name, stripping vendor/provider decorations."""
    text = str(name or "").strip()
    if not text:
        return slug
    text = _TRAILING_ANNOTATION.sub("", text).strip()
    text = _LEADING_BRACKET.sub("", text, count=1).strip()
    prefix = _LEADING_VENDOR.match(text)
    if prefix and canonical_model_slug(prefix.group(1)) != canonical_model_slug(slug):
        # Keep Ollama-style ``gemma3:12b`` intact but drop a real vendor prefix.
        text = text[prefix.end():].strip()
    return text or slug


def collect_models(root: Path) -> tuple[dict[str, list[Path]], dict[str, str]]:
    """Map canonical slugs to model files and to a clean display name."""
    paths: dict[str, list[Path]] = {}
    names: dict[str, str] = {}
    penalties: dict[str, tuple[int, int]] = {}
    for path in sorted(Path(root).glob("providers/*/*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(payload, dict) or payload.get("_generated_by") != "registry.catalog":
            continue
        slug = str(payload.get("model") or "").strip()
        if not slug:
            continue
        paths.setdefault(slug, []).append(path)
        raw_name = str(payload.get("name") or "").strip()
        if not raw_name:
            continue
        label = display_name(raw_name, slug)
        penalty = (label != raw_name, len(label))
        if slug not in names or penalty < penalties[slug]:
            names[slug] = label
            penalties[slug] = penalty
    return paths, names


def model_ids(payload: dict[str, Any]) -> set[str]:
    """Every identifier a generated model record is known by."""
    values = [payload.get("model"), payload.get("canonical_id"), payload.get("provider_model_id")]
    for key in ("aliases", "provider_model_ids", "provider_model_id_variants"):
        value = payload.get(key)
        if isinstance(value, list):
            values.extend(value)
        elif isinstance(value, str):
            values.append(value)
    return {_match_key(value) for value in values if value}


def match_leaderboard(
    rows: list[dict[str, Any]],
    root: Path,
) -> dict[str, dict[str, Any]]:
    """Match ranked leaderboard rows onto canonical model slugs.

    Exact slug wins, then normalized ID, then a raw alias.  When several rows
    resolve to the same model the best (lowest) rank is kept.
    """
    paths, _ = collect_models(root)
    exact: dict[str, str] = {}
    normalized: dict[str, str] = {}
    aliases: dict[str, set[str]] = {}
    for slug, model_paths in paths.items():
        exact.setdefault(slugify(slug), slug)
        normalized.setdefault(_match_key(slug), slug)
        for path in model_paths:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(payload, dict):
                continue
            for identifier in model_ids(payload):
                aliases.setdefault(identifier, set()).add(slug)

    matches: dict[str, dict[str, Any]] = {}
    for row in rows:
        raw = str(row.get("Model ID") or "")
        key = _match_key(raw)
        slug = (
            exact.get(slugify(raw))
            or normalized.get(key)
            or (sorted(aliases.get(key, set()))[0] if aliases.get(key) else None)
        )
        if not slug:
            continue
        rank = int(row.get("Rank") or 0)
        if not rank:
            continue
        previous = matches.get(slug)
        if previous and previous["rank"] <= rank:
            continue
        matches[slug] = {
            "leaderboard_id": raw,
            "leaderboard_rank": rank,
            "rank": rank,
        }
    return matches


def parse_rank_cell(value: Any) -> int | str | None:
    """Parse a markdown rank cell into an int, an ``~N`` estimate, or None."""
    text = str(value or "").strip().replace("`", "")
    if not text or text in {"-", "—"}:
        return None
    if _INTEGER.match(text):
        return int(text)
    estimate = _ESTIMATE.match(text)
    if estimate:
        return f"~{estimate.group(1)}"
    return None


def parse_markdown(path: Path) -> dict[str, int | str | None]:
    """Read the editable rank table; blank cells map to None."""
    result: dict[str, int | str | None] = {}
    if not Path(path).is_file():
        return result
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] in {"model_id", "---"}:
            continue
        if set(cells[0]) <= {"-", ":"}:
            continue
        result[cells[0]] = parse_rank_cell(cells[1])
    return result


def _rank_values(payload: dict[str, Any]) -> int | str | None:
    rank = payload.get("leaderboard_rank")
    if isinstance(rank, int) and not isinstance(rank, bool) and rank > 0:
        return rank
    estimate = payload.get("leaderboard_rank_estimated")
    if estimate:
        return parse_rank_cell(estimate)
    return None


def current_ranks(root: Path) -> tuple[dict[str, int | str | None], dict[str, str]]:
    """Read ranks currently stored in model files, keyed by canonical slug."""
    paths, names = collect_models(root)
    ranks: dict[str, int | str | None] = {}
    for slug, model_paths in paths.items():
        for path in model_paths:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(payload, dict):
                value = _rank_values(payload)
                if value is not None:
                    ranks[slug] = value
                    break
    return ranks, names


def apply_ranks(
    root: Path,
    matches: dict[str, dict[str, Any]] | None,
    overrides: dict[str, int | str | None],
    *,
    clear_unranked: bool = True,
    dry_run: bool = False,
) -> dict[str, int]:
    """Write rank fields onto every model file; return change counts."""
    paths, _ = collect_models(root)
    written = 0
    unchanged = 0
    for slug, model_paths in sorted(paths.items()):
        override = overrides.get(slug)
        override_present = slug in overrides
        match = (matches or {}).get(slug)
        for path in model_paths:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(payload, dict):
                continue
            updated = dict(payload)
            if clear_unranked:
                # A refresh replaces the rank overlay wholesale; a plain import
                # only touches cells the agent actually filled in.
                for field in RANK_FIELDS:
                    updated.pop(field, None)

            value = override if override_present else None
            if value is None and match:
                value = int(match["leaderboard_rank"])
            if clear_unranked and match:
                # Keep the provenance even when a curated cell overrides the
                # number; this also makes repeated refreshes idempotent.
                updated["leaderboard_id"] = match["leaderboard_id"]
            if isinstance(value, int):
                updated["leaderboard_rank"] = value
                updated.pop("leaderboard_rank_estimated", None)
            elif isinstance(value, str) and value.startswith("~"):
                updated["leaderboard_rank_estimated"] = value
                updated.pop("leaderboard_rank", None)

            if updated == payload:
                unchanged += 1
                continue
            if not dry_run:
                write_json(path, updated)
            written += 1
    return {"written": written, "unchanged": unchanged, "models": len(paths)}


def export_markdown(
    root: Path,
    ranks: dict[str, int | str | None],
    names: dict[str, str],
    destination: Path,
    *,
    dry_run: bool = False,
) -> int:
    """Write the curated rank table, sorted by model name then slug."""
    paths, model_names = collect_models(root)
    labels = {**model_names, **names}
    lines = [
        "# Model leaderboard ranks",
        "",
        "Generated by `venv/bin/python manage.py sync_model_ranks`. Rows are sorted",
        "by model name, ignoring vendor prefixes and provider annotations. An empty",
        "`rank` cell means the leaderboard has no entry for",
        "that model: research it and fill in an exact integer or an estimate such as",
        "`~120`, then run `venv/bin/python manage.py sync_model_ranks --import` to",
        "write the table back into `.agentone/providers/<provider>/<model>.json`.",
        "",
        "Do not edit other columns. Ranks are re-applied on every `--refresh`.",
        "",
        "| model_id | rank |",
        "|---|---|",
    ]
    for slug in sorted(paths, key=lambda item: (labels.get(item, item).lower(), item)):
        value = ranks.get(slug)
        cell = "" if value is None else str(value)
        lines.append(f"| {slug} | {cell} |")

    destination = Path(destination)
    text = "\n".join(lines) + "\n"
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
    return len(paths)
