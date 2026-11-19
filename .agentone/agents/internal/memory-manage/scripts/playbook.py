"""Playbook and improvement-proposal schemas for synthesized memory nodes.

The synthesizer is an LLM: it proposes.  This module is the harness side of
that contract.  It parses ``reflection.md`` and ``improvements.md``, validates
their frontmatter, and normalizes what it finds — stable IDs from
fingerprints, deduplication, evidence caps, status clamping — before
:mod:`finalize` is allowed to advance a node's manifest.

Two artifacts live beside ``memory.md`` in every memory node:

``reflection.md`` — the *playbook* (schema ``agentone.playbook/1``)
    YAML frontmatter with a ``directives`` list.  A directive is one
    behavioural rule: when *trigger* applies, do *rule*.  The body stays free
    markdown for humans; only the frontmatter is injected into sessions.

``improvements.md`` — the *improvement ledger* (schema
    ``agentone.improvements/1``)
    YAML frontmatter with a ``proposals`` list.  A proposal is a change that
    is bigger than a behavioural rule: a prompt edit, a skill, a tool, a
    standalone script, or a harness fix.  Proposals are never applied by the
    memory loop; they are filed as work items by a human or an assistant.

Legacy nodes have plain-markdown ``reflection.md`` without frontmatter.  They
stay valid (nothing is injected from them) and are upgraded the next time the
node is synthesized.  Malformed *new* frontmatter first goes through a narrow
deterministic repair (unquoted plain scalars containing ``": "``), because a
single bad colon should not wedge a node in ``needs_update`` forever; anything
still unparseable is reported to :mod:`finalize`, which escalates to a repair
subagent and finally to quarantine with the original content preserved.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import frontmatter
import yaml

#: Filenames owned by the memory synthesizer.
REFLECTION_FILENAME = "reflection.md"
IMPROVEMENTS_FILENAME = "improvements.md"

#: Frontmatter schema markers.
PLAYBOOK_SCHEMA = "agentone.playbook/1"
IMPROVEMENTS_SCHEMA = "agentone.improvements/1"

#: Where a directive can be implemented.  ``prompt`` covers system prompts,
#: instructions and bootstrap text; the rest are capability rungs.
ROUTING = (
    "prompt",
    "system_prompt",
    "memory",
    "skill",
    "tool",
    "script",
    "harness",
)

#: Directive lifecycle.  ``candidate`` is injected only when opted in;
#: ``retired`` is kept so a dead lesson is not re-proposed every synthesis.
DIRECTIVE_STATUSES = ("active", "candidate", "retired")

#: Proposal kinds.  ``prompt`` and ``system_prompt`` are edits an agent owner
#: can make directly; the rest need a coding/implementation pass.
PROPOSAL_KINDS = ("prompt", "system_prompt", "skill", "tool", "script", "harness")

#: Proposal lifecycle (mirrors the capability ladder).
PROPOSAL_STATUSES = ("candidate", "specified", "implemented", "active", "retired")

#: Harness-side caps.  The synthesizer is told softer budgets; these are the
#: limits the harness enforces regardless of what it was told.
MAX_DIRECTIVES = 40
MAX_PROPOSALS = 30
MAX_RULE_CHARS = 600
MAX_SUMMARY_CHARS = 400
MAX_DETAIL_CHARS = 4000
MAX_EVIDENCE_ITEMS = 10
MAX_ID_CHARS = 64

_ROUTING_ALIASES = {
    "instruction": "prompt",
    "instructions": "prompt",
    "prompt": "prompt",
    "system-prompt": "system_prompt",
    "system_prompt": "system_prompt",
    "systemprompt": "system_prompt",
    "memory": "memory",
    "memory-knowledge": "memory",
    "knowledge": "memory",
    "skill": "skill",
    "tool": "tool",
    "tooling": "tool",
    "script": "script",
    "code": "script",
    "harness": "harness",
    "framework": "harness",
}

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_WORD_RE = re.compile(r"[a-z0-9]+")

#: Status ordering used when trimming a node to its caps (lower = keep first).
_STATUS_RANK = {"active": 0, "candidate": 1, "retired": 2}
_PROPOSAL_RANK = {
    "specified": 0,
    "candidate": 1,
    "implemented": 2,
    "active": 3,
    "retired": 4,
}


class PlaybookError(ValueError):
    """Raised when a playbook or improvement file is structurally invalid."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _as_list(value: Any) -> list[Any]:
    """Return *value* as a list (``None`` → empty, scalars → one element)."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _clean_text(value: Any, limit: int) -> str:
    """Collapse whitespace and cut *value* to *limit* characters."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) > limit:
        text = text[: max(0, limit - 1)].rstrip() + "…"
    return text


def normalize_rule(rule: str) -> str:
    """Return the comparable form of a directive rule (dedupe key input)."""
    text = str(rule or "").lower()
    return " ".join(_WORD_RE.findall(text))


def fingerprint_for(rule: str) -> str:
    """Return a stable fingerprint for a directive rule.

    Punctuation, casing and whitespace changes keep the fingerprint, so a
    synthesizer that rewords the same lesson does not create a duplicate.
    """
    normalized = normalize_rule(rule)
    if not normalized:
        return ""
    slug = "-".join(normalized.split()[:10])[:48].strip("-")
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{digest}" if slug else digest


def _valid_id(value: Any) -> str:
    text = str(value or "").strip()
    return text if _ID_RE.match(text) else ""


def _status(value: Any, allowed: Iterable[str], default: str) -> str:
    text = str(value or "").strip().lower()
    return text if text in allowed else default


def _evidence(value: Any) -> list[str]:
    out: list[str] = []
    for item in _as_list(value):
        text = _clean_text(item, 120)
        if text and text not in out:
            out.append(text)
    return out[:MAX_EVIDENCE_ITEMS]


def _support(value: Any, evidence: list[str]) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = len(evidence)
    return max(0, count)


# ---------------------------------------------------------------------------
# Directive schema
# ---------------------------------------------------------------------------


def normalize_directive(raw: Any) -> dict[str, Any] | None:
    """Return one normalized directive, or ``None`` when it has no rule."""
    if not isinstance(raw, dict):
        return None

    rule = _clean_text(raw.get("rule") or raw.get("instruction"), MAX_RULE_CHARS)
    if not rule:
        return None

    trigger = _clean_text(raw.get("trigger") or raw.get("when"), 200)
    verification = _clean_text(raw.get("verification") or raw.get("check"), 300)
    capability = _clean_text(raw.get("capability"), 120)
    evidence = _evidence(raw.get("evidence"))
    support = _support(raw.get("support"), evidence)

    fingerprint = _clean_text(raw.get("fingerprint"), 120).lower()
    if not fingerprint:
        fingerprint = fingerprint_for(rule)
    if not fingerprint:
        return None

    status = _status(raw.get("status"), DIRECTIVE_STATUSES, "candidate")
    # Nothing supports it → it cannot be active yet.  A rule with evidence (or
    # an explicit support count) may be active; retirement is always allowed.
    if status == "active" and support <= 0:
        status = "candidate"

    directive_id = _valid_id(raw.get("id"))
    if not directive_id:
        directive_id = f"PB-{fingerprint.split('-')[-1]}"

    routing = _ROUTING_ALIASES.get(
        _clean_text(raw.get("routing") or raw.get("where"), 40).lower(), "prompt"
    )

    return {
        "id": directive_id,
        "fingerprint": fingerprint,
        "rule": rule,
        "trigger": trigger,
        "routing": routing,
        "status": status,
        "support": support,
        "evidence": evidence,
        "verification": verification,
        "capability": capability,
    }


def _merge_duplicate(kept: dict[str, Any], other: dict[str, Any]) -> dict[str, Any]:
    """Fold *other* into *kept*, keeping the stronger signal."""
    merged_evidence = list(kept["evidence"])
    for item in other["evidence"]:
        if item not in merged_evidence:
            merged_evidence.append(item)

    stronger = other if other["support"] > kept["support"] else kept
    status = kept["status"]
    if _STATUS_RANK.get(other["status"], 9) < _STATUS_RANK.get(status, 9):
        status = other["status"]

    return {
        **kept,
        "rule": stronger["rule"] if len(stronger["rule"]) >= len(kept["rule"]) else kept["rule"],
        "trigger": kept["trigger"] or other["trigger"],
        "verification": kept["verification"] or other["verification"],
        "capability": kept["capability"] or other["capability"],
        "support": max(kept["support"], other["support"]),
        "status": status,
        "evidence": merged_evidence[:MAX_EVIDENCE_ITEMS],
    }


def normalize_directives(items: Any) -> list[dict[str, Any]]:
    """Normalize, dedupe and cap a list of raw directives."""
    kept: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for raw in _as_list(items):
        directive = normalize_directive(raw)
        if directive is None:
            continue
        key = directive["fingerprint"]
        if key in kept:
            kept[key] = _merge_duplicate(kept[key], directive)
        else:
            kept[key] = directive
            order.append(key)

    ranked = sorted(
        (kept[key] for key in order),
        key=lambda d: (_STATUS_RANK.get(d["status"], 9), -d["support"]),
    )
    return ranked[:MAX_DIRECTIVES]


# ---------------------------------------------------------------------------
# Improvement proposals
# ---------------------------------------------------------------------------


def normalize_proposal(raw: Any) -> dict[str, Any] | None:
    """Return one normalized improvement proposal, or ``None`` when empty."""
    if not isinstance(raw, dict):
        return None

    summary = _clean_text(
        raw.get("summary") or raw.get("title") or raw.get("rule"), MAX_SUMMARY_CHARS
    )
    detail = _clean_text(raw.get("detail") or raw.get("body"), MAX_DETAIL_CHARS)
    if not summary and not detail:
        return None
    if not summary:
        summary = detail[:MAX_SUMMARY_CHARS]

    evidence = _evidence(raw.get("evidence"))
    fingerprint = _clean_text(raw.get("fingerprint"), 120).lower()
    if not fingerprint:
        # Identity is the summary: adding detail or evidence must not fork the
        # proposal into a duplicate on the next synthesis.
        fingerprint = fingerprint_for(summary or detail)
    if not fingerprint:
        return None

    proposal_id = _valid_id(raw.get("id"))
    if not proposal_id:
        proposal_id = f"IMP-{fingerprint.split('-')[-1]}"

    return {
        "id": proposal_id,
        "fingerprint": fingerprint,
        "kind": _status(raw.get("kind"), PROPOSAL_KINDS, "prompt"),
        "scope": _clean_text(raw.get("scope"), 40) or "task",
        "owner": _clean_text(raw.get("owner"), 120),
        "status": _status(raw.get("status"), PROPOSAL_STATUSES, "candidate"),
        "trigger": _clean_text(raw.get("trigger"), 200),
        "summary": summary,
        "detail": detail,
        "acceptance": _clean_text(raw.get("acceptance"), 400),
        "evidence": evidence,
    }


def normalize_proposals(items: Any) -> list[dict[str, Any]]:
    """Normalize, dedupe and cap a list of raw proposals."""
    kept: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for raw in _as_list(items):
        proposal = normalize_proposal(raw)
        if proposal is None:
            continue
        key = proposal["fingerprint"]
        if key in kept:
            current = kept[key]
            evidence = list(current["evidence"])
            for item in proposal["evidence"]:
                if item not in evidence:
                    evidence.append(item)
            kept[key] = {
                **current,
                "detail": current["detail"] or proposal["detail"],
                "acceptance": current["acceptance"] or proposal["acceptance"],
                "status": min(
                    (current["status"], proposal["status"]),
                    key=lambda s: _PROPOSAL_RANK.get(s, 9),
                ),
                "evidence": evidence[:MAX_EVIDENCE_ITEMS],
            }
        else:
            kept[key] = proposal
            order.append(key)

    ranked = sorted(
        (kept[key] for key in order),
        key=lambda p: (_PROPOSAL_RANK.get(p["status"], 9), p["kind"]),
    )
    return ranked[:MAX_PROPOSALS]


# ---------------------------------------------------------------------------
# File parsing / rendering
# ---------------------------------------------------------------------------


_SCALAR_LINE_RE = re.compile(
    r"^(?P<prefix>\s*(?:-\s+)?[A-Za-z_][\w.-]*:\s*)(?P<value>.*)$"
)


def _repair_frontmatter_text(text: str) -> str | None:
    """Quote plain scalars that contain ``": "`` in a frontmatter block.

    An LLM synthesizer occasionally writes ``rule: do X, then: do Y``.  YAML
    reads the inner ``": "`` as a nested mapping and the whole file fails to
    parse, which used to leave the memory node pending forever.  Wrap such
    values in double quotes (a JSON string is a valid YAML double-quoted
    scalar) and return the repaired text; ``normalize_reflection`` / 
    ``normalize_improvements`` then rewrite the file with ``yaml.safe_dump``,
    so the repair is permanent.  Returns ``None`` when nothing needed fixing.
    """
    lines = text.splitlines(keepends=True)
    if not lines or not lines[0].lstrip().startswith("---"):
        return None
    end = None
    for index, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end = index
            break
    if end is None:
        return None

    output = list(lines)
    block_indent: int | None = None
    changed = False
    for index in range(1, end):
        line = lines[index].rstrip("\r\n")
        newline = lines[index][len(line):]
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if block_indent is not None:
            if not stripped or indent > block_indent:
                continue
            block_indent = None
        if not stripped or stripped.startswith("#"):
            continue
        match = _SCALAR_LINE_RE.match(line)
        if not match:
            continue
        value = match.group("value")
        if not value:
            continue
        # Already quoted, a flow collection, an anchor/alias/tag, or a block
        # scalar.  Block-scalar continuation lines are skipped by block_indent.
        if value[0] in "\"'[{\\&*!|>" or value.startswith("- "):
            if value[0] in "|>":
                block_indent = indent
            continue
        needs_quote = (
            ": " in value
            or value.endswith(":")
            or " #" in value
            or value[0] in "@`"
        )
        if not needs_quote:
            continue
        output[index] = match.group("prefix") + json.dumps(
            value, ensure_ascii=False
        ) + newline
        changed = True
    return "".join(output) if changed else None


def read_frontmatter(
    path: Path, _repair_info: dict[str, bool] | None = None
) -> tuple[dict[str, Any], str, bool]:
    """Return ``(metadata, body, has_frontmatter)`` for a markdown file.

    Missing files yield ``({}, "", False)``.  Malformed YAML in a file that
    looks like new-format frontmatter is repaired when the damage is a plain
    scalar containing ``": "`` (see :func:`_repair_frontmatter_text`); when
    the repair is used, ``_repair_info["repaired"]`` is set to ``True`` so the
    finalize step can report it.  Unrepairable files raise
    :class:`PlaybookError`.  Legacy prose merely starting with ``---`` stays
    valid.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, "", False
    except (OSError, UnicodeError) as exc:
        raise PlaybookError(f"cannot read {path.name}: {exc}") from exc

    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return {}, text, False

    try:
        post = frontmatter.loads(text)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # A prose file may legitimately start with a ``---`` horizontal rule.
        # Only call that malformed *new-format* frontmatter when the block
        # actually looks like our schema; otherwise treat it as legacy prose.
        head = text[:2000]
        if any(marker in head for marker in ("schema:", "directives:", "proposals:")):
            repaired = _repair_frontmatter_text(text)
            if repaired is not None:
                try:
                    fixed = frontmatter.loads(repaired)
                except Exception:  # pylint: disable=broad-exception-caught
                    fixed = None
                if fixed is not None:
                    if _repair_info is not None:
                        _repair_info["repaired"] = True
                    return dict(fixed.metadata or {}), fixed.content, True
            raise PlaybookError(
                f"invalid YAML frontmatter in {path.as_posix()}: {exc}"
            ) from exc
        return {}, text, False
    return dict(post.metadata or {}), post.content, True


def _render(metadata: dict[str, Any], body: str) -> str:
    front = yaml.safe_dump(
        metadata,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=1000,
    ).strip()
    body = (body or "").strip()
    return f"---\n{front}\n---\n" + (f"\n{body}\n" if body else "")


def load_playbook(path: Path, _repair_info: dict[str, bool] | None = None) -> dict[str, Any]:
    """Parse a ``reflection.md`` file into normalized directives.

    Returns ``{"present", "legacy", "directives", "metadata", "body"}``.
    A file with frontmatter but the wrong schema raises :class:`PlaybookError`.
    """
    metadata, body, has_frontmatter = read_frontmatter(path, _repair_info)
    present = Path(path).is_file()
    if not has_frontmatter:
        return {
            "present": present,
            "legacy": present,
            "directives": [],
            "metadata": {},
            "body": body,
        }

    schema = str(metadata.get("schema") or "").strip()
    if schema and schema != PLAYBOOK_SCHEMA:
        raise PlaybookError(
            f"{Path(path).name}: unsupported schema {schema!r} "
            f"(expected {PLAYBOOK_SCHEMA!r})"
        )
    raw = metadata.get("directives")
    if raw is not None and not isinstance(raw, (list, tuple)):
        raise PlaybookError(f"{Path(path).name}: directives must be a list")

    return {
        "present": True,
        "legacy": not schema and raw is None,
        "directives": normalize_directives(raw or []),
        "metadata": metadata,
        "body": body,
    }


def load_improvements(path: Path, _repair_info: dict[str, bool] | None = None) -> dict[str, Any]:
    """Parse an ``improvements.md`` file into normalized proposals."""
    metadata, body, has_frontmatter = read_frontmatter(path, _repair_info)
    present = Path(path).is_file()
    if not has_frontmatter:
        return {"present": present, "proposals": [], "metadata": {}, "body": body}

    schema = str(metadata.get("schema") or "").strip()
    if schema and schema != IMPROVEMENTS_SCHEMA:
        raise PlaybookError(
            f"{Path(path).name}: unsupported schema {schema!r} "
            f"(expected {IMPROVEMENTS_SCHEMA!r})"
        )
    raw = metadata.get("proposals")
    if raw is not None and not isinstance(raw, (list, tuple)):
        raise PlaybookError(f"{Path(path).name}: proposals must be a list")

    return {
        "present": True,
        "proposals": normalize_proposals(raw or []),
        "metadata": metadata,
        "body": body,
    }


def _playbook_metadata(directives: list[dict[str, Any]], previous: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {"schema": PLAYBOOK_SCHEMA}
    for key in ("agent", "scope", "owner"):
        if previous.get(key):
            metadata[key] = previous[key]
    metadata["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    metadata["directives"] = directives
    return metadata


def _improvements_metadata(proposals: list[dict[str, Any]], previous: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {"schema": IMPROVEMENTS_SCHEMA}
    for key in ("agent", "scope"):
        if previous.get(key):
            metadata[key] = previous[key]
    metadata["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    metadata["proposals"] = proposals
    return metadata


def normalize_reflection(
    path: Path, _repair_info: dict[str, bool] | None = None
) -> dict[str, Any]:
    """Validate and rewrite *path* with normalized directives.

    Legacy prose files are left untouched.  Returns a small report dict.
    """
    loaded = load_playbook(path, _repair_info)
    if not loaded["present"] or loaded["legacy"]:
        return {
            "present": loaded["present"],
            "legacy": loaded["legacy"],
            "directives": len(loaded["directives"]),
            "changed": False,
        }

    content = _render(
        _playbook_metadata(loaded["directives"], loaded["metadata"]),
        loaded["body"],
    )
    try:
        previous = Path(path).read_text(encoding="utf-8")
    except OSError:
        previous = ""
    changed = content != previous
    if changed:
        Path(path).write_text(content, encoding="utf-8")
    return {
        "present": True,
        "legacy": False,
        "directives": len(loaded["directives"]),
        "changed": changed,
    }


def normalize_improvements(
    path: Path, _repair_info: dict[str, bool] | None = None
) -> dict[str, Any]:
    """Validate and rewrite *path* with normalized proposals."""
    loaded = load_improvements(path, _repair_info)
    if not loaded["present"] or not loaded["proposals"]:
        return {
            "present": loaded["present"],
            "proposals": len(loaded["proposals"]),
            "changed": False,
        }

    content = _render(
        _improvements_metadata(loaded["proposals"], loaded["metadata"]),
        loaded["body"],
    )
    try:
        previous = Path(path).read_text(encoding="utf-8")
    except OSError:
        previous = ""
    changed = content != previous
    if changed:
        Path(path).write_text(content, encoding="utf-8")
    return {
        "present": True,
        "proposals": len(loaded["proposals"]),
        "changed": changed,
    }


def normalize_node(target_dir: Any) -> tuple[bool, dict[str, Any]]:
    """Validate and normalize both artifacts in one memory node.

    Returns ``(ok, report)``.  ``ok`` is ``False`` only for structurally
    invalid *new-format* files; legacy prose and absent files are fine.
    """
    path = Path(str(target_dir or "")).expanduser()
    report: dict[str, Any] = {"target_dir": path.as_posix()}
    reflection_repair: dict[str, bool] = {}
    improvements_repair: dict[str, bool] = {}

    try:
        report["reflection"] = normalize_reflection(
            path / REFLECTION_FILENAME, reflection_repair
        )
    except (PlaybookError, OSError) as exc:
        return False, {
            **report,
            "status": "error",
            "error_kind": "playbook_frontmatter",
            "message": f"invalid playbook: {exc}",
        }

    try:
        report["improvements"] = normalize_improvements(
            path / IMPROVEMENTS_FILENAME, improvements_repair
        )
    except (PlaybookError, OSError) as exc:
        return False, {
            **report,
            "status": "error",
            "error_kind": "improvements_frontmatter",
            "message": f"invalid improvement ledger: {exc}",
        }

    report["frontmatter_repaired"] = {
        "reflection": reflection_repair.get("repaired", False),
        "improvements": improvements_repair.get("repaired", False),
    }
    report["status"] = "success"
    return True, report


# ---------------------------------------------------------------------------
# Discovery helpers (used by the improvement queue)
# ---------------------------------------------------------------------------


def iter_playbook_files(memory_roots: Iterable[Path]) -> list[Path]:
    """Return every ``reflection.md`` and ``improvements.md`` under *roots*."""
    found: list[Path] = []
    for root in memory_roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for name in (REFLECTION_FILENAME, IMPROVEMENTS_FILENAME):
            found.extend(sorted(root.rglob(name)))
    return found
