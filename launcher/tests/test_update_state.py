"""Run state helpers used by the UI update panel."""

from __future__ import annotations

import pytest

from launcher import update_state


@pytest.fixture
def fake_cache(monkeypatch):
    store = {}
    monkeypatch.setattr(update_state, "_get", lambda key: store.get(key))
    monkeypatch.setattr(update_state, "_set", lambda key, value, ttl=None: store.__setitem__(key, value))
    return store


def test_run_lifecycle(fake_cache):
    run = update_state.start_run("0.1.0+aaa")

    assert run["status"] == "running"
    assert update_state.current_run()["id"] == run["id"]

    update_state.append_log(run["id"], "Fetching remote", "info")
    update_state.append_log(run["id"], "Migration failed", "error")
    update_state.finish_run(run["id"], "failed", error="Migration failed")

    finished = update_state.get_run(run["id"])
    assert finished["status"] == "failed"
    assert finished["error"] == "Migration failed"
    assert [entry["message"] for entry in finished["logs"]] == ["Fetching remote", "Migration failed"]
    assert update_state.current_run()["id"] == run["id"]


def test_queue_reservation_is_exclusive(fake_cache, monkeypatch):
    """The UI queue uses cache.add so two clicks cannot both queue a run."""

    class FakeCache:
        def add(self, key, value, ttl):
            if key in fake_cache:
                return False
            fake_cache[key] = value
            return True

        def delete(self, key):
            fake_cache.pop(key, None)

    monkeypatch.setattr(update_state, "cache", FakeCache())
    assert update_state.reserve_queue() is True
    assert update_state.reserve_queue() is False
    update_state.release_queue()
    assert update_state.reserve_queue() is True


def test_stale_run_is_reconciled(fake_cache):
    from datetime import datetime, timedelta, timezone

    run = update_state.start_run("0.1.0+aaa")
    old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="seconds")
    update_state._set(update_state._KEY_PREFIX + run["id"], {**run, "started_at": old})

    assert update_state.is_stale_run(update_state.current_run()) is True
    result = update_state.reconcile_stale_run()
    assert result["status"] == "failed"
    assert update_state.current_run()["status"] == "failed"


def test_log_is_bounded(fake_cache):
    run = update_state.start_run("0.1.0+aaa")
    for index in range(update_state._MAX_LOG_LINES + 25):
        update_state.append_log(run["id"], f"line {index}")

    logs = update_state.get_run(run["id"])["logs"]
    assert len(logs) == update_state._MAX_LOG_LINES
    assert logs[-1]["message"] == f"line {update_state._MAX_LOG_LINES + 24}"
