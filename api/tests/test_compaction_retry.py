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


class TestCompactionResponseWrapper:
    """ingest_compaction_response reshapes the awaited retry result into the
    old success shape (response/parts/message) without touching the DB."""

    def test_dict_result_unpacks_marker(self):
        marker, response = object(), object()
        parts = [{"type": "text"}]
        out = ingest_mod.ingest_compaction_response(
            None,
            compaction_result={"message": marker},
            response=response,
            parts=parts,
            message=object(),
            compact_attempt=1,
        )
        assert out["message"] is marker
        assert out["response"] is response
        assert out["parts"] == parts
        assert out["compaction_retried"] is True
        assert out["compact_attempt"] == 1

    def test_missing_marker_falls_back_to_carried_message(self):
        carried = object()
        out = ingest_mod.ingest_compaction_response(
            None, compaction_result={}, response=None, parts=None, message=carried
        )
        assert out["message"] is carried

    def test_none_result_falls_back_to_carried_message(self):
        carried = object()
        out = ingest_mod.ingest_compaction_response(None, compaction_result=None, message=carried)
        assert out["message"] is carried
        assert out["response"] is None
