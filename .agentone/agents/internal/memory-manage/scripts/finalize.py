"""Programmatic completion for synthesized memory nodes.

A synthesizer writes ``memory.md`` / ``reflection.md`` and then ends its turn.
The harness — not the LLM — advances the node's manifest: ``memory_merge``
schedules the ``memory_finalize`` task with the synthesizer's task call as its
argument, so the framework auto-awaits the child session and hands its
``final_result`` to this module.  Keeping the write and the manifest advance in
separate, harness-owned steps means a failed run can never mark a node current.

Malformed playbook frontmatter is handled in layers: :mod:`playbook` first
quotes unsafe plain scalars and re-parses; the caller may escalate to a repair
subagent; as a bounded last resort the bad file is quarantined (with its text
preserved) and replaced by a valid skeleton so the node cannot wedge forever.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import paths as mempaths
import sources as memsources
from playbook import normalize_node

logger = logging.getLogger(__name__)

#: Frontmatter failures the deterministic repair could not fix.  The subagent
#: escalation may still handle these; if it cannot, they are quarantined.
FRONTMATTER_ERROR_KINDS = ("playbook_frontmatter", "improvements_frontmatter")


#: Files a synthesis run must produce before the manifest may advance.
OUTPUT_FILES = ("memory.md", "reflection.md")

#: Allow for coarse filesystem timestamps when comparing an output write to the
#: moment the synthesizer was dispatched.
MTIME_SLACK_SECONDS = 2.0


def quarantine_invalid(path: Path, error_kind: str) -> list[str]:
    """Preserve an unrepairable artifact and replace it with a valid skeleton.

    This is the last-resort safety valve: it keeps the node from wedging in
    ``needs_update`` forever when neither the deterministic repair nor the
    repair subagent could produce parseable YAML.  The original text is kept
    in a ``*.malformed-<stamp>.md`` sidecar and embedded in the replacement's
    body, so no content is lost.

    Returns the list of filenames that were quarantined.
    """
    filenames = {
        "playbook_frontmatter": ("reflection.md", "agentone.playbook/1", "directives"),
        "improvements_frontmatter": (
            "improvements.md", "agentone.improvements/1", "proposals"
        ),
    }
    if error_kind not in filenames:
        return []
    name, schema, list_key = filenames[error_kind]
    source = path / name
    if not source.is_file():
        return []
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path / f"{name}.malformed-{stamp}.md"
    try:
        raw = source.read_text(encoding="utf-8")
        source.replace(backup)
    except OSError as exc:
        logger.warning("could not quarantine %s: %s", source, exc)
        return []
    updated = datetime.now().astimezone().isoformat(timespec="seconds")
    skeleton = (
        f"---\nschema: {schema}\nupdated_at: '{updated}'\n{list_key}: []\n---\n\n"
        f"The previous frontmatter could not be parsed or repaired. The original\n"
        f"file is preserved as `{backup.name}` and reproduced below.\n\n"
        f"```text\n{raw}\n```\n"
    )
    try:
        source.write_text(skeleton, encoding="utf-8")
    except OSError as exc:
        logger.warning("could not write skeleton for %s: %s", source, exc)
        return []
    logger.warning("quarantined malformed frontmatter %s -> %s", source, backup)
    return [name]


def finalize_memory(
    target_dir: Any,
    *,
    started_at: float | str | None = None,
    allow_quarantine: bool = False,
) -> tuple[bool, dict[str, Any]]:
    """Validate a synthesized node and advance its ``.memory_sources.md``.

    Args:
        target_dir: Directory containing the node's manifest and output files.
        started_at: Unix timestamp when synthesis was dispatched.  When given,
            at least one output file must have been written after that moment,
            so a failed run cannot advance a manifest using stale output.
        allow_quarantine: When normalization still fails after deterministic
            repair, preserve the malformed artifact and replace it with an
            empty valid skeleton so the node can advance. Used only as a
            bounded last resort after subagent repair has been tried.

    Returns:
        ``(True, {...})`` when the manifest advanced, otherwise
        ``(False, {"status": "error", "message": ...})``.
    """
    from tree import mark_processed

    raw = str(target_dir or "").strip()
    if not raw:
        return False, {"status": "error", "message": "target_dir is required"}

    path = Path(raw).expanduser()
    try:
        path = path.resolve()
    except OSError as exc:
        return False, {"status": "error", "message": f"invalid target_dir: {exc}"}

    if not path.is_dir():
        return False, {
            "status": "error",
            "message": f"target_dir does not exist: {path}",
        }

    manifest = path / memsources.SOURCES_FILENAME
    if not manifest.is_file():
        return False, {
            "status": "error",
            "message": (
                f"no {memsources.SOURCES_FILENAME} in {path}; "
                "run memory_walk before synthesizing"
            ),
        }

    written = [name for name in OUTPUT_FILES if (path / name).is_file()]
    if not written:
        return False, {
            "status": "error",
            "message": (
                f"no memory output found in {path}; write memory.md and "
                "reflection.md before marking the node processed"
            ),
        }

    if started_at is not None:
        try:
            cutoff = float(started_at) - MTIME_SLACK_SECONDS
        except (TypeError, ValueError):
            cutoff = None
        if cutoff is not None:
            fresh = []
            for name in written:
                try:
                    if (path / name).stat().st_mtime >= cutoff:
                        fresh.append(name)
                except OSError:
                    continue
            if not fresh:
                return False, {
                    "status": "error",
                    "message": (
                        f"no output written since synthesis started in {path}; "
                        "the node stays pending"
                    ),
                    "files": written,
                }

    quarantined: list[str] = []
    quarantined_kinds: set[str] = set()
    for _ in range(3):
        try:
            normalized, playbook_report = normalize_node(path)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            return False, {
                "status": "error",
                "message": f"playbook normalization failed: {exc}",
                "files": written,
            }
        if normalized:
            break
        error_kind = playbook_report.get("error_kind")
        failure = {
            "status": "error",
            "error_kind": error_kind,
            "message": playbook_report.get("message")
            or "reflection.md / improvements.md are malformed",
            "files": written,
            "playbook": playbook_report,
        }
        if (
            not allow_quarantine
            or error_kind not in FRONTMATTER_ERROR_KINDS
            or error_kind in quarantined_kinds
        ):
            return False, failure
        moved = quarantine_invalid(path, error_kind)
        if not moved:
            return False, failure
        quarantined.extend(moved)
        quarantined_kinds.add(error_kind)
    else:
        return False, {
            "status": "error",
            "message": "frontmatter repair did not converge",
            "files": written,
        }

    try:
        if not mark_processed(path):
            return False, {
                "status": "error",
                "message": f"{path} is not a node in the memory tree",
            }
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return False, {"status": "error", "message": f"mark_processed failed: {exc}"}

    try:
        mempaths.inflight_path(path).unlink(missing_ok=True)
    except OSError:
        pass

    result: dict[str, Any] = {
        "status": "success",
        "target_dir": path.as_posix(),
        "files": written,
        "playbook": playbook_report,
        "message": "manifest advanced; this node is now current",
    }
    repaired = playbook_report.get("frontmatter_repaired")
    if repaired and any(repaired.values()):
        result["frontmatter_repaired"] = repaired
    if quarantined:
        result["quarantined"] = quarantined
        result["message"] = "manifest advanced after quarantining malformed frontmatter"
    return True, result
