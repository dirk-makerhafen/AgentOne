from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, "/Users/Dirk/AgentOne/.agentone/agents/wiki/scripts")

from update_timeline_daily import (  # noqa: E402
    _aggregate_day_lists,
    _build_day_check_brief,
    _build_day_session_brief,
    _build_day_update_brief,
    _canonicalize_list,
    _collect_day_summaries,
    _day_changed_files,
    _decide_stale_fingerprint,
    _git_head,
    _is_explicit_none,
    _parse_pair_lines,
    _pick_body,
    _read_child_session_texts,
    _read_index_facts,
    _replace_frontmatter_item,
    _sources_fingerprint,
    _validate_body,
    apply_dedup_to_files,
)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


SUMMARY = """---
type: summary
title: Anmeldung Siebdruck-Workshop - Henning Delius
date: 2022-10-04 15:23
updated: 2022-10-05
tags: [siebdruck]
persons: [Henning Delius]
companies: []
products: []
uids: []
sources: ["[[raw/emails/x/message.md]]"]
---

# Anmeldung Siebdruck-Workshop - Henning Delius

- Henning meldet sich zum Workshop am 15.10. an
"""


SUMMARY_B = """---
type: summary
title: Spende erhalten - Paypal
date: 2022-10-04 16:27
updated: 2022-10-05
tags:
  - spende
  - paypal
persons:
  - Luna Jeschke
companies:
  - paypal
groups:
  - Freifunk
products: []
uids: []
sources: ["[[raw/emails/y/message.md]]"]
---

# Spende erhalten - Paypal

- Spende über 50 Euro eingegangen
"""


# --- fingerprint staleness (no git needed: worktree content decides) --------

def _day_with_files(tmp_path, files: dict[str, str]) -> Path:
    day = tmp_path / "timeline" / "2022" / "10" / "04"
    for name, content in files.items():
        _write(day / name, content)
    return day


def _record_index(day: Path, fingerprint: str, head: str = "abc123"):
    """Write index.md stamped with *fingerprint* (simulates a finished build)."""
    from update_timeline_daily import _build_daily_index
    (day / "index.md").write_text(
        _build_daily_index("2022-10-04", {"tags": [], "persons": [], "companies": [], "products": []},
                           "# Summary for 2022-10-04\n\n- x\n", [], "2022-10-05", head, fingerprint),
        encoding="utf-8",
    )


def _stale(day: Path):
    """Run the staleness decision for a day dir like the dispatcher does."""
    exists, fm_type, _stored, stored_fp = _read_index_facts(day)
    current_fp = _sources_fingerprint(_collect_day_summaries(day)[0])
    return _decide_stale_fingerprint(index_exists=exists, fm_type=fm_type, stored_fp=stored_fp, current_fp=current_fp)


def test_decide_missing_legacy_unfingerprinted():
    assert _decide_stale_fingerprint(index_exists=False, fm_type=None, stored_fp=None, current_fp="x")[0]
    needs, reason = _decide_stale_fingerprint(index_exists=True, fm_type="index", stored_fp=None, current_fp="x")
    assert needs and "legacy" in reason
    needs, reason = _decide_stale_fingerprint(index_exists=True, fm_type="daily_summary", stored_fp=None, current_fp="x")
    assert needs and "sources_fingerprint" in reason
    needs, reason = _decide_stale_fingerprint(index_exists=True, fm_type="daily_summary", stored_fp="old", current_fp="new")
    assert needs and "changed" in reason
    assert not _decide_stale_fingerprint(index_exists=True, fm_type="daily_summary", stored_fp="same", current_fp="same")[0]


def test_fingerprint_stable_over_index_rewrite_no_loop(tmp_path):
    """The reported loop: recording + committing index.md must not re-flag the day."""
    day = _day_with_files(tmp_path, {"a.md": SUMMARY})
    fp = _sources_fingerprint(_collect_day_summaries(day)[0])
    _record_index(day, fp)
    # index.md itself was just (re)written — sources untouched -> fresh, no loop
    assert not _stale(day)[0]
    # same after the file is touched without content change
    (day / "a.md").write_text(SUMMARY, encoding="utf-8")
    assert not _stale(day)[0]


def test_fingerprint_catches_source_changes(tmp_path):
    day = _day_with_files(tmp_path, {"a.md": SUMMARY})
    fp = _sources_fingerprint(_collect_day_summaries(day)[0])
    _record_index(day, fp)
    assert not _stale(day)[0]
    (day / "a.md").write_text(SUMMARY + "\nappended\n", encoding="utf-8")  # edited (committed or not)
    needs, reason = _stale(day)
    assert needs and "changed" in reason


def test_fingerprint_catches_add_and_remove(tmp_path):
    day = _day_with_files(tmp_path, {"a.md": SUMMARY})
    fp = _sources_fingerprint(_collect_day_summaries(day)[0])
    _record_index(day, fp)
    (day / "b.md").write_text(SUMMARY_B, encoding="utf-8")  # late arrival, e.g. scanned mail
    assert _stale(day)[0]
    (day / "b.md").unlink()
    assert not _stale(day)[0]
    (day / "a.md").unlink()  # source removed
    assert _stale(day)[0]


def test_fingerprint_ignores_index_and_other_days(tmp_path):
    day_a = tmp_path / "timeline" / "2022" / "10" / "04"
    day_b = tmp_path / "timeline" / "2022" / "10" / "05"
    for day in (day_a, day_b):
        _write(day / "a.md", SUMMARY)
        _record_index(day, _sources_fingerprint(_collect_day_summaries(day)[0]))
    _write(day_b / "b.md", SUMMARY_B)
    with open(day_a / "index.md", "a", encoding="utf-8") as f:  # index-only change
        f.write("\n")
    assert not _stale(day_a)[0]
    assert _stale(day_b)[0]


def test_read_index_facts(tmp_path):
    day = tmp_path / "timeline" / "2022" / "10" / "04"
    assert _read_index_facts(day) == (False, None, None, None)
    _write(day / "index.md", "---\ntype: index\nupdated: 2022-10-05\n---\n\ncatalog")
    assert _read_index_facts(day) == (True, "index", None, None)
    _write(day / "index.md", "---\ntype: daily_summary\nupdated: 2022-10-05\nlast_checked_at: abc123\nsources_fingerprint: fp1\ntags: []\n---\n\nbody")
    assert _read_index_facts(day) == (True, "daily_summary", "abc123", "fp1")


def test_git_head_none_outside_repo(tmp_path):
    assert _git_head(tmp_path) is None


def test_day_changed_files_no_git(tmp_path):
    day = _day_with_files(tmp_path, {"a.md": SUMMARY})
    assert _day_changed_files(day, tmp_path, None) == (None, [])
    assert _day_changed_files(day, tmp_path, "deadbeef") == (None, [])


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.email=t@t.t", "-c", "user.name=t", *args],
        cwd=cwd.as_posix(), capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_day_changed_files_git_status_and_diff(tmp_path):
    day = _day_with_files(tmp_path, {"a.md": SUMMARY, "c.md": SUMMARY_B, "index.md": "old index"})
    _git(tmp_path, "init", "-q", ".")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "base")
    head = _git(tmp_path, "rev-parse", "HEAD")
    # worktree phase: modified + untracked + removed + own-output + non-md
    # (b.md deliberately duplicates c.md's content: git must NOT collapse
    # this into a rename — removals stay visible via --no-renames)
    (day / "a.md").write_text(SUMMARY + "more\n", encoding="utf-8")
    _write(day / "b.md", SUMMARY_B)
    (day / "c.md").unlink()
    _write(day / "index.md", "rebuilt index")  # own output — excluded
    _write(day / "notes.txt", "attachment")
    changed, removed = _day_changed_files(day, tmp_path, head)
    assert changed == ["a.md", "b.md", "notes.txt"]
    assert removed == ["c.md"]
    # committed phase: clean tree, changes visible only via diff-vs-hash
    _git(tmp_path, "add", "-A", ".")
    _git(tmp_path, "commit", "-qm", "work")
    changed, removed = _day_changed_files(day, tmp_path, head)
    assert changed == ["a.md", "b.md", "notes.txt"]
    assert removed == ["c.md"]
    # bad hash + clean tree: nothing determinable beyond "nothing pending"
    changed, removed = _day_changed_files(day, tmp_path, "0" * 40)
    assert (changed, removed) == ([], [])


def test_day_update_brief_marks_changed():
    brief = _build_day_update_brief(
        "timeline/2022/10/04", "2022-10-04",
        ["a.md", "b.md"], {"b.md"}, ["gone.md"])
    assert "timeline/2022/10/04" in brief
    assert "# Summary for 2022-10-04" in brief
    assert "- b.md (CHANGED since last build — re-read fully)" in brief
    assert "- a.md (CHANGED" not in brief  # unchanged files unmarked
    assert "- gone.md" in brief  # removed section
    assert "current `timeline/2022/10/04/index.md`" in brief  # revise, not fresh
    assert "as your LAST message" in brief
    assert "write NO files" in brief
    assert "no frontmatter" in brief
    assert "## Einträge" not in brief  # catalog is code-built
    assert "frontmatter-only spelling" in brief  # cascade churn note


def test_session_brief_returns_body_only():
    brief = _build_day_session_brief("timeline/2022/10/04", "2022-10-04", ["a.md"])
    assert "timeline/2022/10/04" in brief
    assert "# Summary for 2022-10-04" in brief
    assert "write NO files" in brief
    assert "no frontmatter" in brief
    assert "as your LAST message" in brief
    assert "## Einträge" not in brief  # catalog is code-built
    assert "type: daily_summary" not in brief  # frontmatter is code-built


def test_pick_body_prefers_final_result_then_longest():
    long_a = "a" * 100
    long_b = "b" * 200
    body, src = _pick_body([("ref", None), ("final_result", None), ("last_message", None)])
    assert body is None and src.count("unusable") == 3
    body, src = _pick_body([("ref", "short"), ("final_result", None), ("last_message", None)])
    assert body is None and "unusable" in src
    body, src = _pick_body([("ref", long_b), ("final_result", long_a), ("last_message", "x" * 300)])
    assert body == long_a and src.endswith("=> final_result")  # explicit delivery wins
    body, src = _pick_body([("ref", long_b), ("final_result", None), ("last_message", long_a)])
    assert body == long_b and src.endswith("=> ref")  # else longest wins


def test_child_session_texts_bad_pk_is_none():
    assert _read_child_session_texts(999999999) == (None, None)
    assert _read_child_session_texts("not-a-pk") == (None, None)
    assert _read_child_session_texts(None) == (None, None)


def test_extract_message_ref_unknown_pk_is_none():
    from update_timeline_daily import _extract_result_text
    assert _extract_result_text({"_type": "Message", "pk": 999999999}) is None
    assert _extract_result_text({"_type": "AgentTaskCall", "pk": 1}) is None
    assert _extract_result_text({"odd": "shape"}) is None


def test_check_brief_targets_index_only():
    brief = _build_day_check_brief("timeline/2022/10/04", "2022-10-04", ["a.md"], ["some hint"])
    assert "timeline/2022/10/04/index.md" in brief
    assert "some hint" in brief
    assert "only `index.md` is yours to fix" in brief
    assert "raw/" in brief  # never modify raw


def test_check_brief_embeds_index_format():
    brief = _build_day_check_brief("timeline/2022/10/04", "2022-10-04", ["a.md"], [])
    assert "authoritative" in brief  # no need to infer from other files
    assert "type: daily_summary" in brief
    assert "# Summary for 2022-10-04" in brief
    assert "## Einträge" in brief
    assert "- [[timeline/2022/10/04/<summary-file>.md|<summary-file>.md]]" in brief
    assert "sources_fingerprint" in brief and "never hand-edit" in brief
    assert "last_checked_at" in brief


def test_per_mail_format_reference():
    from update_timeline import SUMMARY_FORMAT_REFERENCE
    assert "type: summary" in SUMMARY_FORMAT_REFERENCE
    assert "always plural" in SUMMARY_FORMAT_REFERENCE
    assert "Never use `source:`" in SUMMARY_FORMAT_REFERENCE
    assert "`werbung`" in SUMMARY_FORMAT_REFERENCE
    assert "No date or time in the title" in SUMMARY_FORMAT_REFERENCE
    assert "never renamed" in SUMMARY_FORMAT_REFERENCE
    assert "groups:" in SUMMARY_FORMAT_REFERENCE
    # Entity feed: contact/relation capture must not regress.
    assert "## Entity-relevant facts" in SUMMARY_FORMAT_REFERENCE
    assert "VERBATIM" in SUMMARY_FORMAT_REFERENCE
    assert "IBAN" in SUMMARY_FORMAT_REFERENCE
    assert "distinguishing context" in SUMMARY_FORMAT_REFERENCE


SUMMARY_NO_GROUPS = """---
type: summary
title: Spende erhalten - Paypal
date: 2022-10-04 16:27
updated: 2022-11-01
tags: [spende]
persons: [Luna Jeschke]
companies: [PayPal]
products: []
uids: []
sources: ["[[raw/emails/y/message.md]]"]
---

# Spende erhalten - Paypal

- Spende über 50 Euro von Luna Jeschke über PayPal eingegangen
"""


def test_per_mail_groups_optional_for_legacy():
    from update_timeline import validate_summary
    raw = "Spende über 50 Euro von Luna Jeschke über PayPal eingegangen"
    hints, _fm, _body = validate_summary(SUMMARY_NO_GROUPS, raw, "raw/emails/y/message.md", "2022-11-01")
    assert not [h for h in hints if "groups" in h]  # legacy files without groups are fine
    bad = SUMMARY_NO_GROUPS.replace("products: []", "products: []\ngroups: somestring")
    hints, _fm, _body = validate_summary(bad, raw, "raw/emails/y/message.md", "2022-11-01")
    assert any("groups" in h and "YAML list" in h for h in hints)
    good = SUMMARY_NO_GROUPS.replace("products: []", "products: []\ngroups: [Freifunk]")
    hints, _fm, _body = validate_summary(good, raw + " für Freifunk", "raw/emails/y/message.md", "2022-11-01")
    assert not [h for h in hints if "groups" in h]


def test_validate_body():
    assert _validate_body("2022-10-04", "# Summary for 2022-10-04\n\n- event with substance here") == []
    assert any("too short" in h for h in _validate_body("2022-10-04", "too short"))
    assert any("exactly" in h for h in _validate_body("2022-10-04", "# Wrong heading\n\n- " + "x" * 60))


def test_build_daily_index():
    from update_timeline_daily import _build_daily_index
    text = _build_daily_index("2022-10-04", {"tags": ["a"], "persons": [], "companies": [], "groups": ["Freifunk"], "products": []},
                              "# Summary for 2022-10-04\n\n- x\n", ["[[timeline/2022/10/04/a.md|a.md]]"], "2026-10-08", "abc", "fp1")
    assert text.startswith("---\ntype: daily_summary\nupdated: 2026-10-08\nlast_checked_at: abc\nsources_fingerprint: fp1\n")
    assert "\ngroups: [Freifunk]\n" in text
    assert "## Einträge" in text and "[[timeline/2022/10/04/a.md|a.md]]" in text


# --- code-owned metadata: collect, dedup pairs, apply ------------------------

def test_collect_and_aggregate(tmp_path):
    day = tmp_path / "timeline" / "2022" / "10" / "04"
    day.mkdir(parents=True)
    (day / "a.md").write_text(SUMMARY, encoding="utf-8")
    (day / "b.md").write_text(SUMMARY_B, encoding="utf-8")
    (day / "index.md").write_text("legacy catalog", encoding="utf-8")
    summaries, hints = _collect_day_summaries(day)
    assert [s["path"].name for s in summaries] == ["a.md", "b.md"]
    assert not hints
    agg = _aggregate_day_lists(summaries)
    assert agg["tags"] == ["siebdruck", "spende", "paypal"]
    assert agg["persons"] == ["Henning Delius", "Luna Jeschke"]
    assert agg["companies"] == ["paypal"]
    assert agg["groups"] == ["Freifunk"]


def test_parse_pair_lines():
    items = ["Henning Delius", "L. Jeschke", "Luna Jeschke"]
    pairs, hints = _parse_pair_lines("Luna Jeschke, L. Jeschke\nbogus\nGhost, Nobody", "persons", items)
    assert pairs == [("persons", "Luna Jeschke", "L. Jeschke")]
    assert len(hints) == 1  # invented variant (bare lines are silently skipped)


def test_dedup_prompt_renders_groups():
    from update_timeline_daily import DEDUP_FIELD_PROMPT, _FIELD_PLURAL, _FIELD_SINGULAR
    assert _FIELD_SINGULAR["groups"] == "group" and _FIELD_PLURAL["groups"] == "groups"
    text = DEDUP_FIELD_PROMPT.format(field="groups", field_singular="group", field_plural="groups",
                                     day_str="2022-10", count=2, items="- Freifunk\n- freifunk e.V.")
    assert "list of groups" in text and "SAME group" in text and "output exactly `none`" in text


def test_is_explicit_none():
    for text in ("none", "None", "NONE", "  none\n", "`none`", '"none"', "'none'"):
        assert _is_explicit_none(text), text
    for text in (None, "", "   ", "none, x", "x, none", "nonetheless", "no duplicates"):
        assert not _is_explicit_none(text), text


def test_parse_pair_lines_none_sentinel():
    pairs, hints = _parse_pair_lines("none", "persons", ["Luna Jeschke"])
    assert pairs == [] and hints == []
    pairs, hints = _parse_pair_lines("None\n", "persons", ["Luna Jeschke"])
    assert pairs == [] and hints == []
    # sentinel mixed with real pairs: pairs still parsed
    pairs, hints = _parse_pair_lines("none\nLuna Jeschke, L. Jeschke", "persons", ["Luna Jeschke", "L. Jeschke"])
    assert pairs == [("persons", "Luna Jeschke", "L. Jeschke")]
    assert not hints


def test_parse_pair_lines_tolerates_field_prefix():
    pairs, hints = _parse_pair_lines("companies: PayPal, paypal", "companies", ["paypal", "PayPal"])
    assert pairs == [("companies", "PayPal", "paypal")]
    assert not hints


def test_parse_pair_lines_double_mapping_first_wins():
    pairs, hints = _parse_pair_lines("A B, A. B\nAB, A. B", "persons", ["A B", "A. B", "AB"])
    assert pairs == [("persons", "A B", "A. B")]
    assert any("twice" in h for h in hints)


def test_canonicalize_list():
    pairs = [("persons", "Luna Jeschke", "L. Jeschke")]
    assert _canonicalize_list(["Henning Delius", "L. Jeschke", "Luna Jeschke"], "persons", pairs) == ["Henning Delius", "Luna Jeschke"]


def test_replace_flow_style():
    fm = 'tags: [siebdruck, workshop]\npersons: [Henning Delius, "L. Jeschke"]'
    new, changed, _ = _replace_frontmatter_item(fm, "persons", "L. Jeschke", "Luna Jeschke")
    assert changed
    assert '"Luna Jeschke"' in new and "L. Jeschke" not in new


def test_replace_flow_style_drop_when_canonical_present():
    new, changed, detail = _replace_frontmatter_item("persons: [Luna Jeschke, L. Jeschke]", "persons", "L. Jeschke", "Luna Jeschke")
    assert changed and "dropped" in detail
    assert new == "persons: [Luna Jeschke]"


def test_replace_block_style():
    fm = "persons:\n  - Luna Jeschke\n  - L. Jeschke\ncompanies:\n  - paypal"
    new, changed, _ = _replace_frontmatter_item(fm, "persons", "L. Jeschke", "Luna Jeschke")
    assert changed
    assert new.count("Luna Jeschke") == 1  # dropped, canonical present
    assert "companies:\n  - paypal" in new  # other fields untouched


def test_replace_missing_field_or_item():
    _, changed, _ = _replace_frontmatter_item("tags: [a]", "persons", "X", "Y")
    assert not changed
    _, changed, _ = _replace_frontmatter_item("tags: [a]", "tags", "zzz", "Y")
    assert not changed


def test_apply_dedup_to_files_bumps_updated(tmp_path):
    day = tmp_path / "timeline" / "2022" / "10" / "04"
    day.mkdir(parents=True)
    (day / "a.md").write_text(SUMMARY, encoding="utf-8")
    (day / "b.md").write_text(SUMMARY_B, encoding="utf-8")
    fixed, hints = apply_dedup_to_files(day, [("companies", "PayPal", "paypal")], "2026-10-08")
    assert set(fixed) == {"b.md"}  # only b.md has companies: paypal
    assert not hints
    b = (day / "b.md").read_text(encoding="utf-8")
    companies_block = b.split("companies:")[1].split("products:")[0]
    assert "  - PayPal" in companies_block and "  - paypal" not in companies_block
    assert "updated: 2026-10-08" in b
    assert "  - paypal" in b.split("tags:")[1].split("persons:")[0]  # tags.paypal untouched
