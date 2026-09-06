"""Tests for the immediate bounded compaction retry.

DB-free by design: only the pure attempt-budget helper is exercised here
(the chain functions need a database, which this env cannot build —
pre-existing Django 4.2 vs 5.x migration drift).
"""
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def _load_script(relpath: str):
    """Load a manifest script module the same way registry/loader does."""
    spec = importlib.util.spec_from_file_location(
        relpath.replace("/", "_").replace(".", "_"),
        _ROOT / relpath,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


ingest_mod = _load_script(".agentone/scripts/compact/ingest_compaction.py")


class TestCompactRetryBudget:
    def test_budget_is_three_total_attempts(self):
        assert ingest_mod.MAX_COMPACT_ATTEMPTS == 3

    def test_first_failure_retries_as_attempt_one(self):
        assert ingest_mod._next_compact_attempt(0) == 1

    def test_second_failure_retries_as_attempt_two(self):
        assert ingest_mod._next_compact_attempt(1) == 2

    def test_third_failure_exhausts_budget(self):
        assert ingest_mod._next_compact_attempt(2) is None

    def test_over_budget_stays_exhausted(self):
        assert ingest_mod._next_compact_attempt(5) is None

    def test_garbage_attempt_counts_as_fresh(self):
        assert ingest_mod._next_compact_attempt("bad") == 1
        assert ingest_mod._next_compact_attempt(None) == 1
