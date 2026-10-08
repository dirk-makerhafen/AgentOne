from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, "/Users/Dirk/AgentOne/.agentone/agents/wiki/scripts")

from update_timeline_monthly import (  # noqa: E402
    _apply_month_pairs,
    _build_month_check_brief,
    _build_month_session_brief,
    _build_month_update_brief,
    _build_monthly_index,
    _collect_month_days,
    _decide_month_stale,
    _month_changed_days,
    _month_sources_fingerprint,
    _tage_entries,
    apply_month_dedup_to_day_indices,
)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


DAY_INDEX_A = """---
type: daily_summary
updated: 2022-10-04
last_checked_at: abc123
sources_fingerprint: fp-day-a
tags: [siebdruck, workshop]
persons: [Henning Delius]
companies: []
products: []
---

# Summary for 2022-10-04

- Henning meldet sich zum Siebdruck-Workshop an
"""


DAY_INDEX_B = """---
type: daily_summary
updated: 2022-10-05
last_checked_at: abc123
sources_fingerprint: fp-day-b
tags: [spende]
persons: [Luna Jeschke]
companies: [PayPal]
products: []
---

# Summary for 2022-10-05

- Spende über 50 Euro von Luna eingegangen
"""


LEGACY_DAY_INDEX = """---
type: index
updated: 2022-10-06
---

# Timeline 06
"""


def _month_with(tmp_path, files: dict[str, str]) -> Path:
    month = tmp_path / "timeline" / "2022" / "10"
    for name, content in files.items():
        _write(month / name, content)
    return month


def _record_month_index(month: Path, fingerprint: str, head: str = "abc123"):
    """Write index.md stamped with *fingerprint* (simulates a finished build)."""
    (month / "index.md").write_text(
        _build_monthly_index("2022-10", {"tags": [], "persons": [], "companies": [], "products": []},
                             "# Summary for 2022-10\n\n- x\n", [], "2022-11-01", head, fingerprint),
        encoding="utf-8",
    )


def _stale(month: Path):
    """Run the staleness decision for a month dir like the dispatcher does."""
    from update_timeline_monthly import _read_index_facts
    exists, fm_type, _stored, stored_fp = _read_index_facts(month)
    days, _dirnames, strays, _hints = _collect_month_days(month)
    return _decide_month_stale(index_exists=exists, fm_type=fm_type, stored_fp=stored_fp,
                               current_fp=_month_sources_fingerprint(days, strays))


# --- staleness --------------------------------------------------------------

def test_decide_month_missing_legacy_unfingerprinted():
    assert _decide_month_stale(index_exists=False, fm_type=None, stored_fp=None, current_fp="x")[0]
    needs, reason = _decide_month_stale(index_exists=True, fm_type="index", stored_fp=None, current_fp="x")
    assert needs and "legacy" in reason
    needs, reason = _decide_month_stale(index_exists=True, fm_type="monthly_summary", stored_fp=None, current_fp="x")
    assert needs and "sources_fingerprint" in reason
    needs, reason = _decide_month_stale(index_exists=True, fm_type="monthly_summary", stored_fp="old", current_fp="new")
    assert needs and "changed" in reason
    assert not _decide_month_stale(index_exists=True, fm_type="monthly_summary", stored_fp="same", current_fp="same")[0]


def test_fingerprint_stable_over_index_rewrite_no_loop(tmp_path):
    month = _month_with(tmp_path, {"04/index.md": DAY_INDEX_A, "05/index.md": DAY_INDEX_B})
    days, _d, strays, _h = _collect_month_days(month)
    _record_month_index(month, _month_sources_fingerprint(days, strays))
    assert not _stale(month)[0]
    with open(month / "index.md", "a", encoding="utf-8") as f:  # index-only change
        f.write("\n")
    assert not _stale(month)[0]


def test_fingerprint_keyed_by_day_not_filename(tmp_path):
    """Every day index is named index.md — identical bodies on different days must hash differently."""
    month_a = _month_with(tmp_path / "a", {"04/index.md": DAY_INDEX_A})
    month_b = _month_with(tmp_path / "b", {"05/index.md": DAY_INDEX_A})  # same body, other day
    days_a, _d, strays_a, _h = _collect_month_days(month_a)
    days_b, _d2, strays_b, _h2 = _collect_month_days(month_b)
    assert [d["day_str"] for d in days_a] == ["2022-10-04"]
    assert [d["day_str"] for d in days_b] == ["2022-10-05"]
    assert _month_sources_fingerprint(days_a, strays_a) != _month_sources_fingerprint(days_b, strays_b)


def test_fingerprint_catches_day_changes(tmp_path):
    month = _month_with(tmp_path, {"04/index.md": DAY_INDEX_A, "05/index.md": DAY_INDEX_B})
    days, _d, strays, _h = _collect_month_days(month)
    _record_month_index(month, _month_sources_fingerprint(days, strays))
    assert not _stale(month)[0]
    (month / "05" / "index.md").write_text(DAY_INDEX_B + "\nappended\n", encoding="utf-8")  # day rebuilt
    needs, reason = _stale(month)
    assert needs and "changed" in reason
    (month / "05" / "index.md").unlink()  # day index removed
    assert _stale(month)[0]


def test_stray_names_feed_fingerprint(tmp_path):
    month = _month_with(tmp_path, {"04/index.md": DAY_INDEX_A, "20221005-xyz.md": "stray summary"})
    days, _d, strays, _h = _collect_month_days(month)
    assert strays == ["20221005-xyz.md"]
    _record_month_index(month, _month_sources_fingerprint(days, strays))
    assert not _stale(month)[0]
    (month / "20221005-xyz.md").unlink()  # stray cleaned up -> rebuild to drop the hint
    assert _stale(month)[0]


# --- collection --------------------------------------------------------------

def test_collect_month_days(tmp_path):
    month = _month_with(tmp_path, {
        "04/index.md": DAY_INDEX_A,
        "05/index.md": DAY_INDEX_B,
        "06/index.md": LEGACY_DAY_INDEX,
        "07/notes.txt": "no index here",
        "20221001-stray.md": "misplaced summary",
    })
    (month / "weird-dir").mkdir(parents=True)
    days, dirnames, strays, hints = _collect_month_days(month)
    assert [d["day_str"] for d in days] == ["2022-10-04", "2022-10-05"]
    assert dirnames == ["04", "05", "06", "07"]
    assert strays == ["20221001-stray.md"]
    assert any("06" in h and "daily_summary" in h for h in hints)  # legacy day index
    assert any("07" in h and "no index.md" in h for h in hints)  # missing day index
    assert any("stray" in h or "directly in month folder" in h for h in hints)
    assert any("weird-dir" in h for h in hints)


def test_collect_month_days_aggregate_union(tmp_path):
    from update_timeline_monthly import _aggregate_day_lists
    month = _month_with(tmp_path, {"04/index.md": DAY_INDEX_A, "05/index.md": DAY_INDEX_B})
    days, _d, _s, hints = _collect_month_days(month)
    assert not hints
    agg = _aggregate_day_lists(days)
    assert agg["tags"] == ["siebdruck", "workshop", "spende"]
    assert agg["persons"] == ["Henning Delius", "Luna Jeschke"]
    assert agg["companies"] == ["PayPal"]


def test_read_month_index_facts(tmp_path):
    from update_timeline_monthly import _read_index_facts
    month = tmp_path / "timeline" / "2022" / "10"
    assert _read_index_facts(month) == (False, None, None, None)
    _write(month / "index.md", "---\ntype: index\nupdated: 2022-11-01\n---\n\ncatalog")
    assert _read_index_facts(month) == (True, "index", None, None)
    _write(month / "index.md", "---\ntype: monthly_summary\nmonth: 2022-10\nupdated: 2022-11-01\nlast_checked_at: abc123\nsources_fingerprint: fp1\ntags: []\n---\n\nbody")
    assert _read_index_facts(month) == (True, "monthly_summary", "abc123", "fp1")


# --- build + briefs -----------------------------------------------------------

def test_build_monthly_index():
    text = _build_monthly_index("2022-10", {"tags": ["spende"], "persons": [], "companies": [], "products": []},
                                "# Summary for 2022-10\n\n- x\n",
                                ["[[timeline/2022/10/04/index.md|2022-10-04]]", "2022-10-05 (no daily index yet)"],
                                "2022-11-01", "abc", "fp1")
    assert text.startswith("---\ntype: monthly_summary\nmonth: 2022-10\nupdated: 2022-11-01\nlast_checked_at: abc\nsources_fingerprint: fp1\n")
    assert "## Tage" in text
    assert "[[timeline/2022/10/04/index.md|2022-10-04]]" in text
    assert "2022-10-05 (no daily index yet)" in text


def test_month_session_brief_returns_body_only():
    brief = _build_month_session_brief("timeline/2022/10", "2022-10", ["04/index.md"])
    assert "timeline/2022/10" in brief
    assert "# Summary for 2022-10" in brief
    assert "write NO files" in brief
    assert "no frontmatter" in brief
    assert "as your LAST message" in brief
    assert "## Tage" not in brief  # catalog is code-built
    assert "type: monthly_summary" not in brief  # frontmatter is code-built


def test_month_check_brief_targets_index_only():
    brief = _build_month_check_brief("timeline/2022/10", "2022-10", ["04/index.md"], ["some hint"])
    assert "timeline/2022/10/index.md" in brief
    assert "some hint" in brief
    assert "only `index.md` is yours to fix" in brief
    assert "day folders" in brief  # never modify days


def test_validate_month_body():
    from update_timeline_monthly import _validate_body
    assert _validate_body("2022-10", "# Summary for 2022-10\n\n- event with substance here") == []
    assert any("too short" in h for h in _validate_body("2022-10", "too short"))


# --- month fix-back into day indices -------------------------------------------

DAY_INDEX_VARIANT = """---
type: daily_summary
updated: 2022-10-06
last_checked_at: abc123
sources_fingerprint: fp-day-c
tags: [workshop]
persons: [L. Jeschke]
companies: [paypal]
products: []
---

# Summary for 2022-10-06

- L. Jeschke beim Workshop
"""


def test_apply_month_dedup_to_day_indices(tmp_path):
    month = _month_with(tmp_path, {
        "04/index.md": DAY_INDEX_A,
        "05/index.md": DAY_INDEX_B,  # already canonical — untouched
        "06/index.md": DAY_INDEX_VARIANT,
        "07/index.md": LEGACY_DAY_INDEX,  # legacy day catalog — never touched
    })
    pairs = [("persons", "Luna Jeschke", "L. Jeschke"), ("companies", "PayPal", "paypal")]
    fixed, hints = apply_month_dedup_to_day_indices(month, ["04", "05", "06", "07", "08"], pairs, "2022-11-01")
    assert not hints
    assert set(fixed) == {"06/index.md"}  # only 06 carries the variants
    text = (month / "06" / "index.md").read_text(encoding="utf-8")
    fm_text = text.split("---")[1]
    assert "persons: [Luna Jeschke]" in fm_text
    assert "companies: [PayPal]" in fm_text
    assert "L. Jeschke" not in fm_text
    assert "paypal" not in fm_text.replace("PayPal", "")  # no variant spelling left
    assert "updated: 2022-11-01" in text
    # untouched: day without variants, legacy catalog, bodies
    assert (month / "04" / "index.md").read_text(encoding="utf-8") == DAY_INDEX_A
    assert (month / "07" / "index.md").read_text(encoding="utf-8") == LEGACY_DAY_INDEX
    assert "- L. Jeschke beim Workshop" in text  # body prose untouched
    # idempotent: second run fixes nothing (no self-retrigger)
    fixed_again, _ = apply_month_dedup_to_day_indices(month, ["04", "05", "06", "07"], pairs, "2022-11-01")
    assert fixed_again == {}


def test_apply_month_dedup_drops_variant_when_canonical_present(tmp_path):
    month = _month_with(tmp_path, {"04/index.md": DAY_INDEX_A})
    idx = month / "04" / "index.md"
    idx.write_text(DAY_INDEX_A.replace("persons: [Henning Delius]", "persons: [Henning Delius, H. Delius]"), encoding="utf-8")
    fixed, _ = apply_month_dedup_to_day_indices(month, ["04"], [("persons", "Henning Delius", "H. Delius")], "2022-11-01")
    assert set(fixed) == {"04/index.md"}
    assert "H. Delius" not in idx.read_text(encoding="utf-8")


def test_fix_back_changes_fingerprint_but_recollects_stable(tmp_path):
    """The write path fingerprints AFTER fixing: post-fix re-collect is the recorded hash."""
    month = _month_with(tmp_path, {"06/index.md": DAY_INDEX_VARIANT})
    days_before, _d, strays, _h = _collect_month_days(month)
    fp_before = _month_sources_fingerprint(days_before, strays)
    fixed, _ = apply_month_dedup_to_day_indices(month, ["06"], [("persons", "Luna Jeschke", "L. Jeschke")], "2022-11-01")
    assert fixed
    days_after, _d2, _s2, _h2 = _collect_month_days(month)
    fp_after = _month_sources_fingerprint(days_after, strays)
    assert fp_after != fp_before  # fix-back is a real source change...
    fixed_again, _ = apply_month_dedup_to_day_indices(month, ["06"], [("persons", "Luna Jeschke", "L. Jeschke")], "2022-11-01")
    assert fixed_again == {}
    days_stable, _d3, _s3, _h3 = _collect_month_days(month)
    assert _month_sources_fingerprint(days_stable, strays) == fp_after  # ...but settles immediately


MAIL_SUMMARY_VARIANT = """---
type: summary
title: Workshop-Anmeldung - L. Jeschke
date: 2022-10-06 10:00
updated: 2022-10-06
tags:
  - workshop
persons:
  - L. Jeschke
companies:
  - paypal
products: []
uids: []
sources: ["[[raw/emails/z/message.md]]"]
---

# Workshop-Anmeldung - L. Jeschke

- L. Jeschke meldet sich zum Workshop an
"""


def test_apply_month_pairs_three_layers(tmp_path):
    """Month pairs unify day index AND per-mail summaries; second run is a no-op."""
    month = _month_with(tmp_path, {
        "06/index.md": DAY_INDEX_VARIANT,
        "06/mail.md": MAIL_SUMMARY_VARIANT,
        "07/index.md": LEGACY_DAY_INDEX,  # legacy day — whole day skipped
        "07/mail.md": MAIL_SUMMARY_VARIANT,
    })
    days, dirnames, _strays, _hints = _collect_month_days(month)
    assert [d["day_str"] for d in days] == ["2022-10-06"]
    pairs = [("persons", "Luna Jeschke", "L. Jeschke"), ("companies", "PayPal", "paypal")]
    fixed_files, fixed_summaries, hints = _apply_month_pairs(month, days, dirnames, pairs, "2022-11-01")
    assert not hints
    assert set(fixed_files) == {"06/index.md"}
    assert set(fixed_summaries) == {"06/mail.md"}  # 07/mail.md untouched — no usable day index
    mail = (month / "06" / "mail.md").read_text(encoding="utf-8")
    persons_block = mail.split("persons:")[1].split("companies:")[0]
    assert "  - Luna Jeschke" in persons_block and "L. Jeschke" not in persons_block
    assert "  - PayPal" in mail.split("companies:")[1].split("products:")[0]
    assert "updated: 2022-11-01" in mail
    assert "title: Workshop-Anmeldung - L. Jeschke" in mail  # titles are history, never rewritten
    assert "- L. Jeschke meldet sich zum Workshop an" in mail  # body prose untouched
    assert "L. Jeschke" in (month / "07" / "mail.md").read_text(encoding="utf-8")  # skipped day intact
    # idempotent across both layers (no self-retrigger)
    days2, dirnames2, _s2, _h2 = _collect_month_days(month)
    fixed2, summaries2, _ = _apply_month_pairs(month, days2, dirnames2, pairs, "2022-11-01")
    assert fixed2 == {} and summaries2 == {}


# --- month change detection (git paths → days) ----------------------------------

def test_month_changed_days_no_git(tmp_path):
    month = _month_with(tmp_path, {"04/index.md": DAY_INDEX_A})
    assert _month_changed_days(month, tmp_path, None) == (None, [], [])
    assert _month_changed_days(month, tmp_path, "deadbeef") == (None, [], [])


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.email=t@t.t", "-c", "user.name=t", *args],
        cwd=cwd.as_posix(), capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


DAY_INDEX_C = DAY_INDEX_A.replace("2022-10-04", "2022-10-06").replace("Henning meldet sich", "Neuer Tag, neuer Inhalt")


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_month_changed_days_git(tmp_path):
    month = _month_with(tmp_path, {
        "04/index.md": DAY_INDEX_A,
        "05/index.md": DAY_INDEX_B,
        "07/index.md": DAY_INDEX_A.replace("2022-10-04", "2022-10-07"),
        "07/mail.md": "mail",
        "08/index.md": DAY_INDEX_B.replace("2022-10-05", "2022-10-08"),
        "08/mail.md": "mail",
        "index.md": "old month index",
        "20221001-stray.md": "stray",
    })
    _git(tmp_path, "init", "-q", ".")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "base")
    head = _git(tmp_path, "rev-parse", "HEAD")
    # worktree phase: index modified / new day / day removed / index dropped /
    # mail-only change / month index + stray touched (both excluded from days)
    (month / "04" / "index.md").write_text(DAY_INDEX_A + "\nappended\n", encoding="utf-8")
    _write(month / "06" / "index.md", DAY_INDEX_C)
    shutil.rmtree(month / "05")
    (month / "07" / "index.md").unlink()
    (month / "08" / "mail.md").write_text("mail changed", encoding="utf-8")
    (month / "index.md").write_text("rebuilt month index", encoding="utf-8")
    (month / "20221001-stray.md").write_text("stray changed", encoding="utf-8")
    changed, removed, notes = _month_changed_days(month, tmp_path, head)
    assert changed == ["2022-10-04", "2022-10-06"]
    assert removed == ["2022-10-05"]
    assert any("2022-10-07" in n and "lost its index" in n for n in notes)
    assert any("2022-10-08" in n and "not yet reflected" in n for n in notes)
    assert any("20221001-stray.md" in n and "hygiene" in n for n in notes)
    # committed phase: clean tree, everything visible only via diff-vs-hash
    _git(tmp_path, "add", "-A", ".")
    _git(tmp_path, "commit", "-qm", "work")
    changed, removed, notes = _month_changed_days(month, tmp_path, head)
    assert changed == ["2022-10-04", "2022-10-06"]
    assert removed == ["2022-10-05"]
    assert len(notes) == 3
    # bad hash + clean tree: nothing determinable
    assert _month_changed_days(month, tmp_path, "0" * 40) == ([], [], [])


def test_month_update_brief_and_tage_entries(tmp_path):
    month = _month_with(tmp_path, {"04/index.md": DAY_INDEX_A, "05/index.md": DAY_INDEX_B})
    days, dirnames, _s, _h = _collect_month_days(month)
    catalog, missing = _tage_entries(None, month, days, dirnames, {"2022-10-04"})
    assert missing == []
    assert any("2022-10-04" in e and "CHANGED" in e for e in catalog)
    assert any(e.endswith("2022-10-05]]") for e in catalog)  # unchanged, unmarked
    brief = _build_month_update_brief("timeline/2022/10", "2022-10", catalog, ["2022-10-03"], ["some note"])
    assert "# Summary for 2022-10" in brief
    assert "UPDATE, not a fresh build" in brief
    assert "current `timeline/2022/10/index.md`" in brief
    assert "- 2022-10-03" in brief  # removed section
    assert "some note" in brief
    assert "as your LAST message" in brief
    assert "write NO files" in brief
    assert "no frontmatter" in brief
    assert "spelling normalizations" in brief  # cascade churn note
