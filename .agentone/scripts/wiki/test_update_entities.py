from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, "/Users/Dirk/AgentOne/.agentone/agents/wiki/scripts")


from update_entities import (  # noqa: E402
    ENTITY_KINDS,
    FIELD_BY_KIND,
    TOPIC_MIN_MONTHS,
    _MAX_ENTITY_EMBED_CHARS,
    _bucket_for_slug,
    _build_entity_file,
    _build_entity_session_brief,
    _build_new_entity_brief,
    _collect_entity_mentions,
    _decide_entity_stale,
    _apply_kind_move,
    _build_sources_import_entry,
    _embed_text_parts,
    _entity_rel,
    _extract_contact_facts,
    _find_kind_twin,
    _logged_sources,
    _parse_entity_fields,
    _fold,
    _log_rel,
    _parse_entity_result,
    _read_entity_facts,
    _read_existing_entities,
    _build_known_map,
    _resolve_mention,
    _slugify_name,
    _topic_qualifies,
)

# NOTE: all person/company/group names below are invented (German
# placeholder-style names like Max Mustermann) — never real vault names.


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


SUMMARY = """---
type: summary
title: Anmeldung Siebdruck-Workshop - Max Mustermann
date: 2022-10-04 15:23
updated: 2022-10-05
tags: [siebdruck, workshop]
persons: [Max Mustermann]
companies: []
groups: []
products: []
uids: []
sources: ["[[raw/emails/x/message.md]]"]
---

# Anmeldung Siebdruck-Workshop - Max Mustermann

- Max meldet sich zum Workshop am 15.10. an
"""

SUMMARY_B = """---
type: summary
title: Spende erhalten - Muster GmbH
date: 2022-11-06 16:27
updated: 2022-11-07
tags: [spende, workshop]
persons: [Erika Mustermann]
companies: [Muster GmbH]
groups: [Funkclub Nord]
products: [Wunderdrucker]
uids: []
sources: ["[[raw/emails/y/message.md]]"]
---

# Spende erhalten - Muster GmbH

- Spende über 50 Euro von Erika Mustermann über die Muster GmbH eingegangen
"""


def _vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    _write(root / "timeline/2022/10/04/20221004-1523_h.md", SUMMARY)
    _write(root / "timeline/2022/11/06/20221106-1627_p.md", SUMMARY_B)
    _write(root / "timeline/2022/10/04/index.md", "---\ntype: daily_summary\n---\n")
    return root


def test_slug_and_bucket():
    assert _slugify_name("Max Mustermann") == "Max_Mustermann"
    assert _slugify_name("Fiona  Falkenhorst ") == "Fiona_Falkenhorst"
    assert _slugify_name("Jonas Bäcker") == "Jonas_Bäcker"
    assert _slugify_name("a/b:c*d?e\"f<g>h|i") == "abcdefghi"
    assert _slugify_name("  ") == ""
    assert _bucket_for_slug("Max_Mustermann", "Persons") == "M"
    assert _bucket_for_slug("Max_Mustermann", "Companies") == "M"
    assert _bucket_for_slug("Muster_GmbH", "Companies") == "M"
    assert _bucket_for_slug("Funkclub_Nord", "Groups") == "F"
    assert _bucket_for_slug("Finn", "Persons") == "F"
    assert _bucket_for_slug("7M_Musterland", "Companies") == "#"
    assert _bucket_for_slug("", "Persons") == "#"
    assert _entity_rel("Persons", "Max Mustermann") == "entities/Persons/M/Max_Mustermann.md"
    assert _entity_rel("Groups", "Funkclub Nord") == "entities/Groups/F/Funkclub_Nord.md"
    assert _entity_rel("Nope", "X") is None
    assert _entity_rel("Persons", "  ") is None
    assert _log_rel("entities/Persons/M/Max_Mustermann.md") == "entities/Persons/M/Max_Mustermann.log.md"


def test_collect_mentions(tmp_path):
    root = _vault(tmp_path)
    mentions, hints = _collect_entity_mentions(root / "timeline", root)
    assert ("Persons", "Max Mustermann") in mentions
    assert ("Companies", "Muster GmbH") in mentions
    assert ("Groups", "Funkclub Nord") in mentions
    assert ("Products", "Wunderdrucker") in mentions
    assert ("Topics", "workshop") in mentions
    assert ("Topics", "siebdruck") in mentions
    entry = mentions[("Persons", "Max Mustermann")]
    assert entry["sources"] == ["timeline/2022/10/04/20221004-1523_h.md"]
    assert entry["months"] == {"2022-10"}
    # Day/month indices are rollups, not sources — never collected.
    assert not [k for k in mentions if k[1] == "daily_summary"]
    assert hints == []


def test_alias_case_resolution():
    existing = {"entities/Companies/M/Muster_GmbH.md": {"kind": "Companies", "name": "Muster GmbH", "aliases": ["muster gmbh europe"],
                                                        "sources": [], "fingerprint": None, "type": "entity", "text": ""}}
    known = _build_known_map(existing)
    assert _resolve_mention("Companies", "muster gmbh", known) == ("Companies", "Muster GmbH")
    assert _resolve_mention("Companies", "Muster GmbH Europe", known) == ("Companies", "Muster GmbH")
    # Cross-kind clashes keep the summary field's kind.
    assert _resolve_mention("Topics", "muster gmbh", known) == ("Topics", "muster gmbh")
    assert _resolve_mention("Persons", "Nobody", known) == ("Persons", "Nobody")
    # ...field kind wins cross-kind: the sweep relocates the misfiled copy.
    misfiled = {"entities/Companies/M/Max_Mustermann.md": {"kind": "Companies", "name": "Max Mustermann", "aliases": [],
                                                           "sources": [], "fingerprint": None, "type": "entity", "text": ""}}
    assert _resolve_mention("Persons", "Max Mustermann", _build_known_map(misfiled)) == ("Persons", "Max Mustermann")


def test_topic_qualifies():
    known = {_fold("Muster GmbH"): ("Companies", "Muster GmbH")}
    ok, _r = _topic_qualifies("workshop", {"2022-10", "2022-11", "2022-12"}, known)
    assert ok
    ok, r = _topic_qualifies("workshop", {"2022-10", "2022-11"}, known)
    assert not ok and str(TOPIC_MIN_MONTHS) in r
    ok, r = _topic_qualifies("muster gmbh", {"2022-10", "2022-11", "2022-12"}, known)
    assert not ok and "covered" in r
    ok, r = _topic_qualifies("Werbung", {"2022-10", "2022-11", "2022-12", "2023-01"}, known)
    assert not ok and "excluded" in r


def test_decide_entity_stale():
    assert _decide_entity_stale(exists=False, fm_type=None, stored_fp=None, current_fp="a")[0]
    stale, reason = _decide_entity_stale(exists=True, fm_type="daily_summary", stored_fp="a", current_fp="a")
    assert stale and "legacy" in reason
    stale, _r = _decide_entity_stale(exists=True, fm_type="entity", stored_fp=None, current_fp="a")
    assert stale
    stale, _r = _decide_entity_stale(exists=True, fm_type="entity", stored_fp="x", current_fp="a")
    assert stale
    stale, reason = _decide_entity_stale(exists=True, fm_type="entity", stored_fp="a", current_fp="a")
    assert not stale and reason == "up to date"


def test_build_entity_file():
    text = _build_entity_file("Persons", "Max Mustermann", ["Max"],
                              {"emails": ["max@example.org"], "phones": [],
                               "relations": [{"type": "spouse", "target": "[[entities/Persons/M/Maria_Mustermann.md]]"}]},
                              "# Max Mustermann\n\n- x\n",
                              "2022-10-01", "2026-10-10", "head", "fp")
    assert text.startswith("---\ntype: entity\nkind: Persons\nname: Max Mustermann\n")
    assert "aliases: [Max]" in text
    assert "date: 2022-10-01\nupdated: 2026-10-10\nlast_checked_at: head\nsources_fingerprint: fp" in text
    assert "emails: [max@example.org]" in text
    assert "phones:" not in text  # empty lists omitted
    assert "  - type: spouse\n    target: \"[[entities/Persons/M/Maria_Mustermann.md]]\"" in text
    assert "sources:" not in text  # provenance lives in the log now
    assert text.rstrip().endswith("- x")


def test_parse_entity_result(tmp_path):
    _write(tmp_path / "entities/Persons/M/Maria_Mustermann.md", "# Maria Mustermann\n")
    good = ("```markdown-fields\nemails: [max@example.org]\nrelations:\n  - type: spouse\n    target: \"[[entities/Persons/M/Maria_Mustermann.md]]\"\n```\n\n"
            "```markdown-body\n# Max Mustermann\n\n- Fact with enough length here yes\n```\n\n"
            "```markdown-log\n## 2026-10-10 12:00 — [[timeline/2022/10/04/a.md]]\n\n- Created page\n```")
    fields, body, entry, hints = _parse_entity_result(good, "Max Mustermann", "Persons", root=tmp_path)
    assert fields["emails"] == ["max@example.org"]
    assert fields["relations"] == [{"type": "spouse", "target": "[[entities/Persons/M/Maria_Mustermann.md]]"}]
    assert body.startswith("# Max Mustermann") and entry.startswith("## 2026-10-10") and hints == []
    fields, body, entry, hints = _parse_entity_result("no fences at all, just prose", "Max Mustermann", "Persons", root=tmp_path)
    assert fields is None and body is None and entry is None and len(hints) == 3
    bad_head = good.replace("# Max Mustermann", "# Somebody Else and more text here to pass length")
    _f, body, _e, hints = _parse_entity_result(bad_head, "Max Mustermann", "Persons", root=tmp_path)
    assert body is None and any("`# Max Mustermann`" in h for h in hints)
    bad_log = good.replace("## 2026-10-10 12:00 — ", "undated entry here ")
    _f, _b, entry, hints = _parse_entity_result(bad_log, "Max Mustermann", "Persons", root=tmp_path)
    assert entry is None and any("YYYY-MM-DD" in h for h in hints)


def test_parse_entity_fields(tmp_path):
    _write(tmp_path / "entities/Persons/M/Maria_Mustermann.md", "# Maria Mustermann\n")
    # Unknown keys dropped, wrong-kind keys dropped, dead relations dropped.
    text = ("```markdown-fields\nemails: [max@example.org]\nbank_iban: [DE89370400440532013000]\n"
            "nickname: Maxi\nrelations:\n  - type: spouse\n    target: \"[[entities/Persons/M/Maria_Mustermann.md]]\"\n"
            "  - type: employer\n    target: \"[[entities/Nowhere.md]]\"\n  - target: \"[[entities/X.md]]\"\n```")
    fields, hints = _parse_entity_fields(text, "Persons", root=tmp_path)
    assert fields["emails"] == ["max@example.org"]
    assert "bank_iban" not in fields and any("bank_iban" in h for h in hints)
    assert any("nickname" in h for h in hints)
    assert fields["relations"] == [{"type": "spouse", "target": "[[entities/Persons/M/Maria_Mustermann.md]]"}]
    assert len([h for h in hints if "relation" in h]) == 2
    fields, hints = _parse_entity_fields("```markdown-fields\n{}\n```", "Persons")
    assert fields == {} and hints == []
    fields, hints = _parse_entity_fields("```markdown-fields\n: broken\n  yaml: [x\n```", "Persons")
    assert fields is None and any("YAML" in h for h in hints)


def test_extract_contact_facts():
    facts = _extract_contact_facts(["Mail max@example.org, Tel +49 40 123456, IBAN DE89370400440532013000, bad IBAN DE00123456789012345678"])
    assert facts["emails"] == ["max@example.org"]
    assert facts["bank_iban"] == ["DE89370400440532013000"]
    assert facts["phones"] and all("40" in p or "123456" in p for p in facts["phones"])
    assert _extract_contact_facts(["no contact data here"]) == {}
    assert _extract_contact_facts([]) == {}


def test_logged_sources_and_import():
    log = ("# Log for X\n\n## 2026-10-10 12:00 — [[timeline/2022/10/04/a.md]]\n\n- did things\n\n"
           "## 2026-10-11 — sources import\n\n- [[timeline/2022/10/05/b.md]]\n- [[entities/Y.md]]\n")
    assert _logged_sources(log) == ["timeline/2022/10/04/a.md", "timeline/2022/10/05/b.md"]
    assert _logged_sources(None) == [] and _logged_sources("") == []
    entry = _build_sources_import_entry(["timeline/b.md", "timeline/a.md"], "2026-10-12 09:00")
    assert entry.startswith("## 2026-10-12 09:00 — sources import")
    assert "- [[timeline/a.md]]\n- [[timeline/b.md]]" in entry
    assert _logged_sources(entry) == ["timeline/a.md", "timeline/b.md"]


def test_legacy_and_old_fields(tmp_path):
    from update_entities import _legacy_fm_sources, _old_structured_fields
    p = _write(tmp_path / "entities/Companies/P/PayPal.md",
               "---\ntype: entity\nkind: Companies\nname: PayPal\nemails: [a@b.cd]\nbank_iban: [DE89370400440532013000]\n"
               "relations:\n  - type: vendor\n    target: \"[[entities/Companies/X.md]]\"\n"
               "sources: [\"[[timeline/2022/10/04/a.md]]\", \"[[timeline/2022/10/05/b.md]]\"]\n---\n\n# PayPal\n")
    assert _legacy_fm_sources(p) == ["timeline/2022/10/04/a.md", "timeline/2022/10/05/b.md"]
    old = _old_structured_fields(p, "Companies")
    assert old["emails"] == ["a@b.cd"] and old["bank_iban"] == ["DE89370400440532013000"]
    assert old["relations"] == [{"type": "vendor", "target": "[[entities/Companies/X.md]]"}]
    assert _old_structured_fields(tmp_path / "missing.md", "Companies") == {}


def test_briefs_reference_parts_not_contents():
    brief = _build_entity_session_brief("Persons", "Max Mustermann", "entities/Persons/M/Max_Mustermann.md",
                                        "entities/Persons/M/Max_Mustermann.log.md",
                                        ["timeline/new.md"])
    assert "UPDATE, not a fresh draft" in brief
    assert "separate message parts" in brief
    assert "timeline/new.md" in brief
    assert "FULL NEW SOURCE TEXT" not in brief  # bytes ride along as parts, never inline
    assert "markdown-body" in brief and "markdown-log" in brief and "markdown-fields" in brief
    assert "emails, phones, addresses, websites" in brief
    assert "write NO files" in brief
    new_brief = _build_new_entity_brief("Groups", "Funkclub Nord", "entities/Groups/F/Funkclub_Nord.md",
                                        "entities/Groups/F/Funkclub_Nord.log.md",
                                        ["timeline/a.md"])
    assert "no page yet" in new_brief and "timeline/a.md" in new_brief
    assert "MENTION TEXT" not in new_brief
    prefill_brief = _build_new_entity_brief("Persons", "Max Mustermann", "entities/Persons/M/Max_Mustermann.md",
                                            "entities/Persons/M/Max_Mustermann.log.md",
                                            ["timeline/a.md"], {"emails": ["max@example.org"]})
    assert "max@example.org" in prefill_brief and "birthday, role" in prefill_brief


def test_origin_section_block():
    from update_entities import _origin_section_block, _raw_rels_from_texts
    assert _origin_section_block([]) == ""
    block = _origin_section_block(["raw/emails/x/message.md"])
    assert "raw/emails/x/message.md" in block
    assert "never modify anything under `raw/`" in block
    assert "never for bulk marketing" in block
    text = "---\ntype: summary\nsources: [\"[[raw/emails/x/message.md]]\", \"https://example.com\"]\n---\n\n# T\n"
    assert _raw_rels_from_texts([text, "no frontmatter here"]) == ["raw/emails/x/message.md"]
    assert _raw_rels_from_texts([]) == []
    brief = _build_entity_session_brief("Persons", "Max Mustermann", "entities/Persons/M/Max_Mustermann.md",
                                        "entities/Persons/M/Max_Mustermann.log.md",
                                        ["timeline/new.md"], {}, ["raw/emails/x/message.md"])
    assert "Missing details? Go to the origin" in brief
    assert "raw/emails/x/message.md" in brief
    plain = _build_entity_session_brief("Persons", "Max Mustermann", "entities/Persons/M/Max_Mustermann.md",
                                        "entities/Persons/M/Max_Mustermann.log.md",
                                        ["timeline/new.md"])
    assert "Go to the origin" not in plain


def test_embed_text_parts():
    parts = _embed_text_parts("CURRENT ENTITY FILE (entities/Persons/M/Max_Mustermann.md)", "# Max Mustermann\n\n- fact\n")
    assert len(parts) == 2
    assert "CURRENT ENTITY FILE" in parts[0]["content"]
    assert parts[1]["content"] == "# Max Mustermann\n\n- fact\n"
    assert _embed_text_parts("LOG", "   ")[0]["content"].endswith("<empty>\n")
    long_parts = _embed_text_parts("BIG", "x" * (_MAX_ENTITY_EMBED_CHARS + 10))
    assert len(long_parts) == 3 and "truncated" in long_parts[0]["content"]
    assert "[... truncated ...]" in long_parts[2]["content"]


def test_read_existing_and_facts(tmp_path):
    root = _vault(tmp_path)
    rel = "entities/Companies/M/Muster_GmbH.md"
    _write(root / rel, "---\ntype: entity\nkind: Companies\nname: Muster GmbH\naliases: [muster]\n"
                       "sources_fingerprint: abc\nsources: []\n---\n\n# Muster GmbH\n")
    _write(root / "entities/Companies/M/Muster_GmbH.log.md", "# Log for Muster GmbH\n")
    existing = _read_existing_entities(root / "entities", root)
    assert existing[rel]["name"] == "Muster GmbH" and existing[rel]["aliases"] == ["muster"]
    assert "entities/Companies/M/Muster_GmbH.log.md" not in existing
    exists, fm_type, fp = _read_entity_facts(root / rel)
    assert (exists, fm_type, fp) == (True, "entity", "abc")
    assert _read_entity_facts(root / "entities/Companies/M/Missing.md")[0] is False


def test_field_kind_maps_cover_day_fields():
    from update_timeline_daily import DAY_FIELDS
    assert set(FIELD_BY_KIND.values()) == set(DAY_FIELDS) | {"tags"}
    assert set(ENTITY_KINDS) == set(FIELD_BY_KIND)


def test_guess_kind():
    assert _guess_kind("Muster GmbH", "Bezahldienst.") == ("Companies", True)
    assert _guess_kind("Musterland", "Bezahldienst. Zahlungen laufen über die Bank.") == ("Companies", False)
    assert _guess_kind("Musterland_GmbH", "") == ("Companies", True)
    assert _guess_kind("Funkclub Nord", "Community Netz") == ("Persons", False)  # shape wins; sweep relocates via group mentions
    assert _guess_kind("Funkclub", "Community Netz") == ("Groups", False)
    assert _guess_kind("Bürgerstiftung Musterstadt", "") == ("Groups", False)  # -stiftung suffix, unconfident
    assert _guess_kind("Musterhafen e.V.", "") == ("Groups", True)
    assert _guess_kind("Max Mustermann", "Meldet sich zum Workshop an") == ("Persons", False)
    # Name evidence outranks a vendor-heavy body; frontmatter never counts.
    assert _guess_kind("Kiosk", "Bestellung, Versand, Zahlung") == ("Companies", False)
    assert _guess_kind("Max Mustermann", "---\nsources: [[timeline/x-Versand-y]]\n---\nMeldet sich an") == ("Persons", False)
    # Two title-case words file as persons even with trade words in the body…
    assert _guess_kind("Max Mustermann", "Bestellung, Versand, Zahlung") == ("Persons", False)
    assert _guess_kind("Otis Mohr", "Kunde seit 2021, Bankeinzug") == ("Persons", False)
    # …unless the body carries a legal form (Hamburg Invest GmbH).
    assert _guess_kind("Hamburg Invest", "Die Hamburg Invest GmbH foerdert Startups") == ("Companies", False)
    # Word boundaries: compounds don't trigger (`Workshopladen` is no `shop`).
    assert _guess_kind("Mia Muster", "kauft Zubehör im Workshopladen") == ("Persons", False)


def test_plan_migration_moves_and_collisions(tmp_path):
    ent = tmp_path / "entities"
    _write(ent / "Muster GmbH.md", "---\ntype: entity\nsources: []\n---\n\n# Muster GmbH\n\nBezahldienst Bank Kram\n")
    _write(ent / "Fiona Falkenhorst.md", "---\ntype: entity\n---\n\n# Fiona Falkenhorst\n\nlange Bio " + "x" * 200 + "\n")
    _write(ent / "Fiona_Falkenhorst.md", "---\ntype: entity\n---\n\n# Fiona\n\nkurz\n")
    _write(ent / "index.md", "# Entities\n")
    _write(ent / "hersteller" / "ACME GmbH.md", "---\ntype: entity\n---\n\n# ACME\n")
    moves, hints = _plan_migration(ent)
    targets = {m["target_rel"] for m in moves}
    assert "entities/Companies/M/Muster_GmbH.md" in targets
    assert "entities/Persons/F/Fiona_Falkenhorst.md" in targets
    assert "entities/Persons/F/Fiona_Falkenhorst.merge-pending.md" in targets
    assert "entities/Companies/A/ACME_GmbH.md" in targets
    assert not [m for m in moves if m["src"].name == "index.md"]
    assert any("slug collision" in h for h in hints)


def test_fold_dupe_candidates(tmp_path):
    ent = tmp_path / "entities"
    _write(ent / "Tora Tellheim.md", "# x\n")
    _write(ent / "Torla_Tellheim.md", "# x\n")
    _write(ent / "Max Mustermann.md", "# x\n")
    groups = _find_fold_dupe_candidates(ent)
    assert any({"Tora Tellheim.md", "Torla_Tellheim.md"} <= set(g) for g in groups)
    assert not any("Max Mustermann.md" in g for g in groups)


def test_find_kind_twin():
    existing = {
        "entities/Companies/M/Max_Mustermann.md": {"kind": "Companies", "name": "Max Mustermann"},
        "entities/Persons/M/Marta_Muster.md": {"kind": "Persons", "name": "Marta Muster"},
    }
    assert _find_kind_twin(existing, "Persons", "Max Mustermann") == "entities/Companies/M/Max_Mustermann.md"
    assert _find_kind_twin(existing, "Persons", "max mustermann") == "entities/Companies/M/Max_Mustermann.md"
    assert _find_kind_twin(existing, "Companies", "Max Mustermann") is None  # same kind is no twin
    assert _find_kind_twin(existing, "Persons", "Nobody") is None
    assert _find_kind_twin(existing, "Persons", "Max Musterman") is None  # near-miss is no twin


def test_apply_kind_move(tmp_path):
    root = tmp_path / "vault"
    src = _write(root / "entities/Companies/M/Max_Mustermann.md", "# Max Mustermann\n")
    _write(root / "entities/Companies/M/Max_Mustermann.log.md", "# Log for Max Mustermann\n\n## 2022-01-01 — [[x]]\n")
    moved, hints = _apply_kind_move(root, "entities/Companies/M/Max_Mustermann.md",
                                    "entities/Persons/M/Max_Mustermann.md")
    assert moved and not src.exists()
    assert (root / "entities/Persons/M/Max_Mustermann.md").read_text().startswith("# Max Mustermann")
    assert (root / "entities/Persons/M/Max_Mustermann.log.md").read_text().startswith("# Log for Max Mustermann")
    assert not (root / "entities/Companies/M/Max_Mustermann.log.md").exists()
    assert any("kind correction" in h for h in hints)
    # Genuine both-exist conflict never clobbers.
    _write(root / "entities/Companies/M/Marta_Muster.md", "# twin\n")
    _write(root / "entities/Persons/M/Marta_Muster.md", "# target\n")
    moved, hints = _apply_kind_move(root, "entities/Companies/M/Marta_Muster.md",
                                    "entities/Persons/M/Marta_Muster.md")
    assert not moved and any("both exist" in h for h in hints)
    assert (root / "entities/Persons/M/Marta_Muster.md").read_text() == "# target\n"
    # Vanished source is a skip, not an error.
    moved, hints = _apply_kind_move(root, "entities/Companies/M/Gone.md", "entities/Persons/M/Gone.md")
    assert not moved and any("vanished" in h for h in hints)


def test_plan_case_insensitive_collision(tmp_path):
    ent = tmp_path / "entities"
    _write(ent / "Musterfirma.md", "---\ntype: entity\n---\n\n# Musterfirma\n\nGmbH langer Text " + "x" * 100 + "\n")
    # Same name, different case, different folder — one file on APFS, two moves planned.
    _write(ent / "hersteller" / "musterfirma.md", "---\ntype: entity\n---\n\n# musterfirma\n\nGmbH kurz\n")
    moves, hints = _plan_migration(ent)
    targets = sorted(m["target_rel"] for m in moves)
    assert len(targets) == 2
    assert targets[0] == "entities/Companies/M/Musterfirma.md"
    assert targets[1] == "entities/Companies/M/Musterfirma.merge-pending.md"
    assert any("slug collision" in h for h in hints)


def test_free_target(tmp_path):
    root = tmp_path / "vault"
    assert _free_target(root, "entities/Companies/M/X.merge-pending.md") == "entities/Companies/M/X.merge-pending.md"
    _write(root / "entities/Companies/M/X.merge-pending.md", "# taken\n")
    assert _free_target(root, "entities/Companies/M/X.merge-pending.md") == "entities/Companies/M/X.merge-pending-2.md"


def test_rebuild_entity_indices(tmp_path):
    from update_entities import rebuild_entity_indices
    root = tmp_path / "vault"
    _write(root / "entities/Persons/M/Max_Mustermann.md",
           "---\ntype: entity\nkind: Persons\nname: Max Mustermann\naliases: [Max]\n---\n\n# Max Mustermann\n\n- Member since 2020\n")
    _write(root / "entities/Persons/M/Max_Mustermann.log.md", "# Log for Max Mustermann\n")
    _write(root / "entities/Persons/M/Marta_Muster.md", "---\ntype: entity\nkind: Persons\nname: Marta Muster\n---\n\n# Marta Muster\n")
    _write(root / "entities/Persons/M/Marta_Muster.merge-pending.md", "# pending\n")
    _write(root / "entities/Companies/A/Muster_GmbH.md", "---\ntype: entity\nkind: Companies\nname: Muster GmbH\n---\n\n# Muster GmbH\n\nVendor.\n")
    first = rebuild_entity_indices(root)
    assert "entities/Persons/M/index.md" in first["wrote"]
    assert "entities/Persons/index.md" in first["wrote"]
    assert "entities/Companies/index.md" in first["wrote"]
    assert "entities/index.md" in first["wrote"]
    letter = (root / "entities/Persons/M/index.md").read_text(encoding="utf-8")
    assert "- [[entities/Persons/M/Max_Mustermann.md|Max Mustermann]] (aka Max) — - Member since 2020" in letter
    assert "Marta_Muster.md|Marta Muster]]" in letter
    assert ".log.md" not in letter and "merge-pending" not in letter
    assert "Parent: [[entities/Persons/index.md|Persons]]" in letter
    kind = (root / "entities/Persons/index.md").read_text(encoding="utf-8")
    assert "- [[entities/Persons/M/index.md|M]]" in kind
    top = (root / "entities/index.md").read_text(encoding="utf-8")
    assert "- [[entities/Persons/index.md|Persons]] — People" in top
    assert "- [[entities/Companies/index.md|Companies]] — Commercial" in top
    assert "Topics" not in top  # no Topics dir yet
    # Idempotent: second run writes nothing.
    second = rebuild_entity_indices(root)
    assert second["wrote"] == [] and second["skipped"] == 5
