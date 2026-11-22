"""The UI update Celery task."""

from __future__ import annotations

import pytest

from launcher import tasks, updates


@pytest.mark.parametrize("fails", [False, True])
def test_task_releases_queue(monkeypatch, fails):
    finished = []
    released = []

    monkeypatch.setattr(tasks, "append_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(tasks, "finish_run", lambda run_id, status, **kwargs: finished.append((run_id, status)))
    monkeypatch.setattr(tasks, "release_queue", lambda: released.append(True))

    def fake_run_update(**kwargs):
        if fails:
            raise updates.UpdateError("nope")
        return {"status": "updated", "after": "0.1.0+bbb"}

    monkeypatch.setattr(updates, "run_update", fake_run_update)

    tasks.update_agentone("run1")

    assert released == [True]
    assert finished == [("run1", "failed" if fails else "updated")]
