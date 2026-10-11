from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, "/Users/Dirk/AgentOne/.agentone/agents/wiki/scripts")

from process_ingress import (  # noqa: E402
    _build_item_brief,
    _parse_result_block,
    _set_line_state,
    dispatch_items,
    finalize_item,
)

QUEUE_FM = """\
---
type: ingress
sources: ["timeline/**/*.md"]
---
"""


def _write(repo: Path, rel: str, text: str) -> Path:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def test_parse_result_block():
    ok_text = ("done work\n```ingress-result\nstatus: success\nfiles:\n"
               "- calendar/2022/10/20.md\n- calendar/2022/10/index.md\nnotes: booked\n```\ntail")
    status, files, notes = _parse_result_block(ok_text)
    assert status == "success"
    assert files == ["calendar/2022/10/20.md", "calendar/2022/10/index.md"]
    assert notes == "booked"
    status, files, notes = _parse_result_block("```ingress-result\nstatus: failed\nnotes: ad, skipping\n```")
    assert (status, files, notes) == ("failed", [], "ad, skipping")
    assert _parse_result_block(None)[0] == "failed"
    assert _parse_result_block("plain text, no fence")[0] == "failed"
    # Success with no files is legitimate (already recorded, nothing to write).
    status, files, _notes = _parse_result_block("```ingress-result\nstatus: success\nnotes: dup\n```")
    assert (status, files) == ("success", [])


def test_build_item_brief():
    brief = _build_item_brief("calendar", "timeline/x.md", "mail text", False, "## Rules\nDo stuff.")
    assert "calendar/AGENTS.md" in brief and "Do stuff." in brief
    assert "timeline/x.md" in brief and "mail text" in brief and "ingress-result" in brief
    assert "never edit `calendar/ingress.md`" in brief
    assert "re-read any shared index file" in brief  # concurrent siblings
    brief = _build_item_brief("calendar", "timeline/gone.md", None, True, None)
    assert "No AGENTS.md" in brief and "source vanished" in brief


def _spawned(tmp_path):
    """Fake spawn/schedule pair recording calls; spawn assigns session pks."""
    calls = {"spawn": [], "schedule": []}
    counter = {"n": 0}

    def spawn_fn(brief: str):
        calls["spawn"].append(brief)
        counter["n"] += 1
        return True, 1000 + counter["n"], {"ref": counter["n"]}

    def schedule_fn(ingress_rel: str, item: str, session_pk, ref):
        calls["schedule"].append((ingress_rel, item, session_pk, ref))
        return {"scheduled": True}

    return calls, spawn_fn, schedule_fn


def test_dispatch_items_fans_out_without_waiting(tmp_path):
    _write(tmp_path, "cal/ingress.md", QUEUE_FM)
    _write(tmp_path, "cal/AGENTS.md", "## Rules\nRecord bookings.")
    _write(tmp_path, "timeline/a.md", "# A\n")
    _write(tmp_path, "timeline/b.md", "# B\n")
    _write(tmp_path, "timeline/c.md", "# C\n")
    calls, spawn_fn, schedule_fn = _spawned(tmp_path)
    ok, info = dispatch_items(tmp_path, "cal/ingress.md", 10, spawn_fn, schedule_fn)
    assert ok, info
    # All three spawned + scheduled, none executed: dispatch never waits.
    assert [item for _i, item, _s, _r in calls["schedule"]] == ["timeline/a.md", "timeline/b.md", "timeline/c.md"]
    assert [s for _i, _t, s, _r in calls["schedule"]] == [1001, 1002, 1003]
    assert len(info["spawned"]) == 3 and info["spawn_failed"] == []
    assert info["remaining"] == 3  # flips happen later, in finalize tasks
    assert all("Record bookings." in b for b in calls["spawn"])
    # Lines are marked active (owned), not done.
    body = (tmp_path / "cal/ingress.md").read_text(encoding="utf-8")
    assert body.count("active") == 3 and "- [x]" not in body


def test_dispatch_items_limit_spawn_failure_and_stale_active(tmp_path):
    _write(tmp_path, "cal/ingress.md", QUEUE_FM)
    for name in ("a", "b", "c"):
        _write(tmp_path, f"timeline/{name}.md", f"# {name}\n")
    calls, _spawn, schedule_fn = _spawned(tmp_path)

    def flaky_spawn(brief: str):
        if "timeline/b.md" in brief:
            return False, None, "no wiki today"
        return True, 2000, {"ref": 1}

    ok, info = dispatch_items(tmp_path, "cal/ingress.md", 2, flaky_spawn, schedule_fn)
    assert ok and len(info["spawned"]) == 1 and len(info["spawn_failed"]) == 1
    assert info["spawn_failed"][0]["item"] == "timeline/b.md"
    body = (tmp_path / "cal/ingress.md").read_text(encoding="utf-8")
    assert "timeline/b.md <!-- queued" in body and "active" not in body.split("timeline/b.md")[1].split("\n")[0]

    # Fresh active marker = owned by another pass: skipped, never double-processed.
    import time
    queue = tmp_path / "cal/ingress.md"
    assert _set_line_state(queue, "timeline/c.md", False, int(time.time()), "2026-10-11")
    ok, info = dispatch_items(tmp_path, "cal/ingress.md", 10, flaky_spawn, schedule_fn)
    assert ok and info["spawned"] == [] and info["remaining"] == 3  # b retried + failed again

    # Stale active marker = crashed pass: reclaimed and dispatched.
    assert _set_line_state(queue, "timeline/c.md", False, 1000000000, "2026-10-11")
    ok, info = dispatch_items(tmp_path, "cal/ingress.md", 10, flaky_spawn, schedule_fn)
    assert ok and [s["item"] for s in info["spawned"]] == ["timeline/c.md"]


def test_finalize_item_success_and_failure(tmp_path):
    _write(tmp_path, "cal/ingress.md", QUEUE_FM)
    _write(tmp_path, "timeline/a.md", "# A\n")
    _write(tmp_path, "timeline/b.md", "# B\n")
    import time
    queue = tmp_path / "cal/ingress.md"
    queue.write_text(queue.read_text(encoding="utf-8")
                     + "- [ ] timeline/a.md\n- [ ] timeline/b.md\n", encoding="utf-8")
    assert _set_line_state(queue, "timeline/a.md", False, int(time.time()), "2026-10-11")
    assert _set_line_state(queue, "timeline/b.md", False, int(time.time()), "2026-10-11")

    good = finalize_item(tmp_path, "cal/ingress.md", "timeline/a.md",
                         "```ingress-result\nstatus: success\nfiles:\n- cal/x.md\nnotes: booked\n```")
    assert good == {"item": "timeline/a.md", "ok": True, "files": ["cal/x.md"],
                    "notes": "booked", "recorded": True}
    bad = finalize_item(tmp_path, "cal/ingress.md", "timeline/b.md",
                        "```ingress-result\nstatus: failed\nnotes: ad\n```")
    assert bad["ok"] is False and bad["notes"] == "ad"
    ugly = finalize_item(tmp_path, "cal/ingress.md", "timeline/b.md", "no fence here")
    assert ugly["ok"] is False and "no ```ingress-result" in ugly["notes"]
    body = queue.read_text(encoding="utf-8")
    assert "- [x] timeline/a.md" in body and "| done " in body
    assert "- [ ] timeline/b.md" in body and "active" not in body


def test_dispatch_items_missing_file(tmp_path):
    ok, info = dispatch_items(tmp_path, "cal/ingress.md", 2,
                              lambda brief: (True, 1, {}),
                              lambda *a: None)
    assert not ok and "not found" in info["message"]
