from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

from runtime.session.session import Session

sys.path.insert(0, Path(__file__).resolve().parent.as_posix())
from update_timeline_daily import (  # noqa: E402
    DAY_FIELDS,
    FRONTMATTER_RE,
    _extract_result_text,
    _fm_list_values,
    _git_head,
    _parse_frontmatter,
    _pick_body,
    _read_child_session_texts,
    _spawn_baseagent,
    _vault_rel,
    _workspace_root,
    _yaml_flow_list,
)


# Pipeline: update_entities keeps entities/<Kind>/<Letter>/<Slug>.md (+ .log.md)
# in sync with the timeline summaries' name fields, mirroring the
# daily/monthly index architecture (code owns structure and metadata, LLM
# sessions own prose judgment):
# - code collects every persons/companies/groups/products/tags value from
#   timeline summaries into per-entity mention sets (sources + YYYY-MM
#   months), resolving aliases/case against existing entity files;
# - tags become Topics/ pages only when they qualify (>= TOPIC_MIN_MONTHS
#   distinct months, no name clash with another entity, not marketing noise);
# - each stale entity (missing file, legacy frontmatter, or a sources
#   fingerprint mismatch) gets one baseagent prose session whose brief holds
#   the current .md, the log tail, and ONLY the new source summaries;
# - the session returns three fenced blocks (structured fields, revised
#   body, new log entry) via its last message and writes nothing;
#   write_entity validates all three, builds the .md frontmatter in code
#   (identity/provenance plus validated fields — NO `sources:` list) and
#   appends the log entry verbatim. Code regex finds (emails, IBANs,
#   phones) are unioned into the fields so machine patterns survive.
#
# Staleness is a content fingerprint (sha1 over the log-linked sources'
# rel paths + full texts): editing a summary restales its entities, while
# our own writes never do — rebuilding self-terminates. The .log.md is the
# provenance: legacy frontmatter `sources:` are absorbed into it via a
# code-written import entry on first rewrite.

ENTITY_KINDS = ("Persons", "Companies", "Groups", "Products", "Topics")
FIELD_BY_KIND = {
    "Persons": "persons",
    "Companies": "companies",
    "Groups": "groups",
    "Products": "products",
    "Topics": "tags",
}
KIND_BY_FIELD = {field: kind for kind, field in FIELD_BY_KIND.items()}

# A tag earns a Topics/ page only after recurring across this many distinct
# YYYY-MM months — one-off keywords stay plain tags, not pages.
TOPIC_MIN_MONTHS = 3
# Marketing-only tags must never become topic pages no matter how often
# they recur.
TOPIC_EXCLUDE = {"werbung"}

ENTITY_BODY_FENCE = "markdown-body"
ENTITY_LOG_FENCE = "markdown-log"
ENTITY_FIELDS_FENCE = "markdown-fields"

# Verbatim-content cap per embedded part, mirroring _MAX_EMBED_CHARS in
# update_timeline.py (entity files can be long; explicit truncation beats
# silent model-side clipping).
_MAX_ENTITY_EMBED_CHARS = 50000

# Structured frontmatter schema. The .md frontmatter is the entity's
# database record: machine-readable contact data and typed relations live
# here, prose lives in the body, provenance lives in the .log.md (which is
# why frontmatter carries NO `sources:` list anymore). Code owns
# type/kind/name/aliases/date/updated/provenance; the LLM fills the
# structured fields below via the ```markdown-fields block (validated by
# `_parse_entity_fields`), with code regex finds unioned in.
ENTITY_COMMON_FIELDS = ("emails", "phones", "addresses", "websites")
ENTITY_KIND_FIELDS = {
    "Persons": ("birthday", "role"),
    "Companies": ("bank_name", "bank_iban", "bank_bic", "tax_id", "customer_no"),
    "Groups": ("contact", "meets", "location"),
    "Products": ("price",),
    "Topics": (),
}
# Suggested relation vocabularies per kind (guidance for the session, not
# enforced — structure is validated, wording is free).
ENTITY_RELATION_HINTS = {
    "Persons": "spouse, partner, parent, child, sibling, friend, colleague, employer, member-of, contact",
    "Companies": "owner, employee, customer, vendor, subsidiary, parent-company, partner, contact",
    "Groups": "member, organizer, venue, partner, contact",
    "Products": "vendor, manufacturer, accessory-of, successor-of",
    "Topics": "related",
}

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_IBAN_RE = re.compile(r"\b[A-Z]{2}\s?\d{2}(?:\s?[A-Z0-9]{4})+(?:\s?[A-Z0-9]{1,3})?\b")
_PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s/\-()]*)?(?:\(?0\d{1,5}\)?[\s/\-]*\d[\d\s/\-()]{5,}\d)")


def _is_valid_iban(value: str) -> bool:
    """mod97 check over the spaceless IBAN (cheap, precise)."""
    compact = re.sub(r"\s+", "", value).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", compact):
        return False
    rearranged = compact[4:] + compact[:4]
    digits = "".join(str(int(ch, 36)) if ch.isalpha() else ch for ch in rearranged)
    return int(digits) % 97 == 1


def _extract_contact_facts(texts: list[str]) -> dict[str, list[str]]:
    """Deterministic pre-fill: emails, valid IBANs, phone-ish numbers.

    Tight patterns only (IBANs must pass mod97) — the session confirms and
    completes them in the fields block, and code unions these finds with
    whatever the session returns, so machine patterns are never lost to
    LLM inattention.
    """
    emails: list[str] = []
    ibans: list[str] = []
    phones: list[str] = []
    for text in texts or []:
        for m in _EMAIL_RE.findall(text or ""):
            if m not in emails:
                emails.append(m)
        for m in _IBAN_RE.findall(text or ""):
            compact = re.sub(r"\s+", "", m).upper()
            if _is_valid_iban(compact) and compact not in ibans:
                ibans.append(compact)
        for m in _PHONE_RE.findall(text or ""):
            phone = re.sub(r"\s+", " ", m).strip()
            if len(re.sub(r"\D", "", phone)) >= 6 and phone not in phones:
                phones.append(phone)
    out: dict[str, list[str]] = {}
    if emails:
        out["emails"] = emails
    if ibans:
        out["bank_iban"] = ibans
    if phones:
        out["phones"] = phones
    return out


def _parse_entity_fields(text: str | None, kind: str, root=None) -> tuple[dict | None, list[str]]:
    """Validate a session's ```markdown-fields block into frontmatter-ready fields.

    Unknown or wrong-kind keys are dropped with a hint; scalar/list shape
    mismatches are coerced when unambiguous, else dropped. Relation items
    need a non-empty `type` and a `[[wikilink]]` target — when *root* is
    given, targets must also resolve to an existing vault file, otherwise
    the dead relation is dropped, never kept. Returns (fields_or_None,
    hints); an explicitly empty mapping is valid ({}, no hints).
    """
    from server.models.enums.message_enums import MessageContentType, MessagePartType  # noqa: F401
    hints: list[str] = []
    if not isinstance(text, str) or not text.strip():
        return None, [f"missing ```{ENTITY_FIELDS_FENCE}``` block — structured fields not updated"]
    m = re.search(rf"```{re.escape(ENTITY_FIELDS_FENCE)}\s*\n(.*?)```", text, re.DOTALL)
    if m is None:
        return None, [f"missing ```{ENTITY_FIELDS_FENCE}``` block — structured fields not updated"]
    try:
        import yaml
        data = yaml.safe_load(m.group(1))
    except Exception as e:
        return None, [f"fields block is not valid YAML ({e}) — structured fields not updated"]
    if data is None:
        return {}, []
    if not isinstance(data, dict):
        return None, ["fields block must be a YAML mapping — structured fields not updated"]
    allowed = set(ENTITY_COMMON_FIELDS) | set(ENTITY_KIND_FIELDS.get(kind, ())) | {"relations"}
    fields: dict = {}
    for key, value in data.items():
        if key not in allowed:
            hints.append(f"fields: unknown key `{key}` for kind {kind} — dropped")
            continue
        if key == "relations":
            items = value if isinstance(value, list) else []
            if not isinstance(value, list):
                hints.append("fields: `relations` must be a list — dropped")
                continue
            kept = []
            for item in items:
                if not isinstance(item, dict) or not isinstance(item.get("type"), str) or not item["type"].strip():
                    hints.append(f"fields: relation without a `type` ({item!r}) — dropped")
                    continue
                target = item.get("target")
                link_m = re.search(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", target) if isinstance(target, str) else None
                if link_m is None:
                    hints.append(f"fields: relation without a `[[wikilink]]` target ({item!r}) — dropped")
                    continue
                target_rel = link_m.group(1).strip()
                if root is not None and not (root / target_rel).is_file():
                    hints.append(f"fields: relation target `{target_rel}` does not exist — dropped")
                    continue
                kept.append({"type": item["type"].strip(), "target": f"[[{target_rel}]]"})
            fields["relations"] = kept
            continue
        if isinstance(value, list):
            items = [str(v).strip() for v in value if str(v).strip()]
            if key == "emails":
                for item in items:
                    if not _EMAIL_RE.fullmatch(item):
                        hints.append(f"fields: `{item}` is not an email address — kept anyway")
            if key == "bank_iban":
                for item in items:
                    if not _is_valid_iban(item):
                        hints.append(f"fields: `{item}` fails the IBAN check — kept anyway")
            fields[key] = items
            continue
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        if isinstance(value, (str, int, float)):
            fields[key] = [str(value).strip()] if key in ENTITY_COMMON_FIELDS else str(value).strip()
            if key in ENTITY_COMMON_FIELDS:
                hints.append(f"fields: scalar `{key}` coerced to a one-item list")
            continue
        hints.append(f"fields: `{key}` has an unusable shape — dropped")
    return fields, hints

_UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


def _slugify_name(name: str) -> str:
    """Canonical entity slug: whitespace runs become one underscore, unsafe chars dropped.

    Umlauts and case are preserved (Peter_Miller, Léon_Göttsche) — only
    separators normalize, so `Gwendolyn Gimpel` and `Gwendolyn_Gimpel`
    collapse to one file. Returns "" for unusable names.
    """
    slug = re.sub(r"\s+", "_", (name or "").strip())
    slug = _UNSAFE_FILENAME_CHARS.sub("", slug)
    slug = re.sub(r"_+", "_", slug).strip("._")
    return slug


def _bucket_for_slug(slug: str, kind: str = "Companies") -> str:
    """Letter bucket for a slug: persons bucket by surname (last component),
    all other kinds by first letter; '#' for non A-Z (3M…, É…)."""
    if not slug:
        return "#"
    part = slug.split("_")[-1] if kind == "Persons" else slug
    first = (part[0] if part else slug[0]).upper()
    return first if "A" <= first <= "Z" else "#"


def _entity_rel(kind: str, name: str) -> str | None:
    """Vault-relative entity path (entities/<Kind>/<Letter>/<Slug>.md), or None."""
    slug = _slugify_name(name)
    if not slug or kind not in ENTITY_KINDS:
        return None
    return f"entities/{kind}/{_bucket_for_slug(slug, kind)}/{slug}.md"


def _log_rel(entity_rel: str) -> str:
    """Companion log path: Slug.md -> Slug.log.md."""
    return entity_rel[:-len(".md")] + ".log.md" if entity_rel.endswith(".md") else entity_rel + ".log.md"


# Static per-kind descriptions for the entities root index (code-owned,
# rewritten by every sweep — no counts, per the vault's no-counts rule).
ENTITY_KIND_DESCRIPTIONS = {
    "Persons": "People — members, contacts, customers, donors, and everyone else with a name.",
    "Companies": "Commercial entities — vendors, suppliers, platforms, service providers, and authorities.",
    "Groups": "Collectives — clubs, associations, crews, teams, initiatives, and communities.",
    "Products": "Products, tools, machines, and product lines bought, used, or sold.",
    "Topics": "Recurring topics distilled from timeline tags.",
}


def _index_entry_description(fm: dict, body: str) -> str:
    """One-line catalog description: first content line of the body (truncated).

    Falls back to "" when the body holds nothing usable — the link alone
    still catalogs the page.
    """
    for line in (body or "").split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"\s+", " ", line)
        return line[:160] + ("…" if len(line) > 160 else "")
    return ""


def _write_if_different(path: Path, text: str) -> bool:
    """Write only on change (keeps mtimes/git quiet); returns True when written."""
    try:
        if path.exists() and path.read_text(encoding="utf-8") == text:
            return False
    except Exception:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def rebuild_entity_indices(root: Path) -> dict:
    """(Re)build the three-level entities catalog: letter, kind, and root indices.

    - ``entities/<Kind>/<Letter>/index.md``: one bullet per entity page
      (``.log.md`` and ``.merge-pending.md`` working files excluded), with
      aliases and a one-line body description.
    - ``entities/<Kind>/index.md``: one bullet per letter index.
    - ``entities/index.md``: one bullet per kind with a static description.
    Everything is deterministic code output (no LLM prose, no counts), so
    rebuilding is idempotent — files are only written on change. Returns
    {"wrote": [rel...], "skipped": n}.
    """
    wrote: list[str] = []
    skipped = 0
    entities_dir = root / "entities"

    for kind in ENTITY_KINDS:
        kind_dir = entities_dir / kind
        if not kind_dir.is_dir():
            continue
        for letter_dir in sorted(d for d in kind_dir.iterdir() if d.is_dir()):
            entries: list[str] = []
            for fp in sorted(letter_dir.glob("*.md")):
                if fp.name in ("index.md",) or fp.name.endswith(".log.md") or ".merge-pending." in fp.name:
                    continue
                try:
                    text = fp.read_text(encoding="utf-8")
                except Exception:
                    continue
                fm, body, _error = _parse_frontmatter(text)
                fm = fm if isinstance(fm, dict) else {}
                name = fm["name"] if isinstance(fm.get("name"), str) and fm["name"].strip() else re.sub(r"[_-]+", " ", fp.stem)
                rel = f"entities/{kind}/{letter_dir.name}/{fp.name}"
                bullet = f"- [[{rel}|{name}]]"
                aliases = [a for a in _fm_list_values(fm, "aliases") if a != name]
                if aliases:
                    bullet += f" (aka {', '.join(aliases)})"
                desc = _index_entry_description(fm, body)
                if desc:
                    bullet += f" — {desc}"
                entries.append(bullet)
            if not entries:
                continue
            noun = "surnames" if kind == "Persons" else "names"
            letter_text = (
                f"---\ntype: index\nupdated: {datetime.datetime.now().date().isoformat()}\n---\n\n"
                f"# {kind} — {letter_dir.name}\n\n"
                f"Parent: [[entities/{kind}/index.md|{kind}]]\n\n"
                f"## {_bucket_label(letter_dir.name)} ({noun})\n\n" + "\n".join(entries) + "\n"
            )
            if _write_if_different(letter_dir / "index.md", letter_text):
                wrote.append(f"entities/{kind}/{letter_dir.name}/index.md")
            else:
                skipped += 1
        letters = [d.name for d in sorted(kind_dir.iterdir()) if d.is_dir() and (d / "index.md").exists()]
        if letters:
            kind_text = (
                f"---\ntype: index\nupdated: {datetime.datetime.now().date().isoformat()}\n---\n\n"
                f"# {kind}\n\n"
                f"Parent: [[entities/index.md|Entities]]\n\n"
                f"{ENTITY_KIND_DESCRIPTIONS.get(kind, '')}\n\n"
                f"## Letters\n\n"
                + "\n".join(f"- [[entities/{kind}/{letter}/index.md|{_bucket_label(letter)}]]" for letter in letters)
                + "\n"
            )
            if _write_if_different(kind_dir / "index.md", kind_text):
                wrote.append(f"entities/{kind}/index.md")
            else:
                skipped += 1

    kinds_present = [k for k in ENTITY_KINDS if (entities_dir / k / "index.md").exists()]
    if kinds_present:
        root_text = (
            f"---\ntype: index\nupdated: {datetime.datetime.now().date().isoformat()}\n---\n\n"
            f"# Entities\n\n"
            f"Parent: [[index.md|Wiki]]\n\n"
            f"People, companies, groups, products, and topics — one page per entity, "
            f"each with a structured record and an update log.\n\n"
            f"## Kinds\n\n"
            + "\n".join(f"- [[entities/{k}/index.md|{k}]] — {ENTITY_KIND_DESCRIPTIONS.get(k, '')}" for k in kinds_present)
            + "\n"
        )
        if _write_if_different(entities_dir / "index.md", root_text):
            wrote.append("entities/index.md")
        else:
            skipped += 1
    return {"wrote": wrote, "skipped": skipped}


def _bucket_label(letter: str) -> str:
    """Display label for a bucket dir: '#' covers digits and symbols."""
    return "0–9 and symbols" if letter == "#" else letter


def _fold(name: str) -> str:
    """Aggressive fold for near-duplicate detection: lowercase, umlauts flattened, alnum only."""
    text = (name or "").lower()
    for src, dst in (("ä", "a"), ("ö", "o"), ("ü", "u"), ("ß", "ss"), ("é", "e"), ("è", "e"),
                     ("ê", "e"), ("á", "a"), ("à", "a"), ("ó", "o"), ("ú", "u"), ("ñ", "n")):
        text = text.replace(src, dst)
    return re.sub(r"[^a-z0-9]", "", text)


def _month_of_summary(fm: dict) -> str | None:
    """YYYY-MM month of a summary from its `date:` field, or None."""
    date = fm.get("date")
    if isinstance(date, str) and re.match(r"^\d{4}-\d{2}(-\d{2})?", date.strip()):
        return date.strip()[:7]
    return None


def _collect_entity_mentions(timeline_dir: Path, root: Path) -> tuple[dict, list[str]]:
    """Walk timeline summaries into {(kind, name): {"sources": [rel...], "months": {YYYY-MM}}}.

    Only ``type: summary`` files count (day/month indices are rollups, not
    sources). Returns (mentions, hints).
    """
    mentions: dict[tuple[str, str], dict] = {}
    hints: list[str] = []
    if not timeline_dir.is_dir():
        return mentions, hints
    for fp in sorted(timeline_dir.rglob("*.md")):
        try:
            text = fp.read_text(encoding="utf-8")
        except Exception as e:
            hints.append(f"unreadable file {fp.name}: {e} — skipped")
            continue
        fm, _body, error = _parse_frontmatter(text)
        if error or not isinstance(fm, dict):
            hints.append(f"{fp.name}: {error} — skipped")
            continue
        if fm.get("type") != "summary":
            continue
        try:
            rel = fp.resolve().relative_to(root.resolve()).as_posix()
        except Exception:
            rel = fp.as_posix()
        month = _month_of_summary(fm)
        for field in DAY_FIELDS + ("tags",):
            kind = KIND_BY_FIELD.get(field)
            if kind is None:
                continue
            for name in _fm_list_values(fm, field):
                key = (kind, name)
                entry = mentions.setdefault(key, {"sources": [], "months": set()})
                if rel not in entry["sources"]:
                    entry["sources"].append(rel)
                if month:
                    entry["months"].add(month)
    for entry in mentions.values():
        entry["sources"].sort()
    return mentions, hints


def _read_existing_entities(entities_dir: Path, root: Path) -> dict[str, dict]:
    """Read already-migrated entities/<Kind>/<Letter>/*.md into {rel: facts}.

    Facts: kind (from folder), name, aliases, sources (known provenance =
    log links ∪ legacy frontmatter `sources:`), fm_sources (legacy only),
    fingerprint, text. Frontmatter no longer carries `sources:` — the log
    is the provenance — but legacy files still do until their first rewrite.
    """
    existing: dict[str, dict] = {}
    if not entities_dir.is_dir():
        return existing
    for kind in ENTITY_KINDS:
        for fp in sorted((entities_dir / kind).rglob("*.md")):
            if fp.name.endswith(".log.md"):
                continue
            try:
                rel = fp.resolve().relative_to(root.resolve()).as_posix()
            except Exception:
                rel = fp.as_posix()
            try:
                text = fp.read_text(encoding="utf-8")
            except Exception:
                continue
            fm, _body, _error = _parse_frontmatter(text)
            fm = fm if isinstance(fm, dict) else {}
            fm_sources: list[str] = []
            for s in _fm_list_values(fm, "sources"):
                link_m = re.search(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", s)
                cand = (link_m.group(1) if link_m else s).strip().strip("\"'")
                if cand.startswith("timeline/") and cand.endswith(".md") and cand not in fm_sources:
                    fm_sources.append(cand)
            log_path = fp.parent / (fp.stem + ".log.md")
            try:
                logged = _logged_sources(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
            except Exception:
                logged = []
            known = sorted(set(logged) | set(fm_sources))
            existing[rel] = {
                "kind": kind,
                "name": fm.get("name") if isinstance(fm.get("name"), str) else fp.stem,
                "aliases": _fm_list_values(fm, "aliases"),
                "sources": known,
                "fm_sources": fm_sources,
                "logged": logged,
                "fingerprint": fm.get("sources_fingerprint") if isinstance(fm.get("sources_fingerprint"), str) else None,
                "type": fm.get("type"),
                "text": text,
            }
    return existing


def _build_known_map(existing: dict[str, dict]) -> dict[str, tuple[str, str]]:
    """Folded-name -> (kind, canonical name) over entity names + aliases."""
    known: dict[str, tuple[str, str]] = {}
    for _rel, facts in existing.items():
        for variant in [facts.get("name"), *(facts.get("aliases") or [])]:
            if variant and _fold(variant) not in known:
                known[_fold(variant)] = (facts["kind"], facts["name"])
    return known


def _resolve_mention(kind: str, name: str, known: dict[str, tuple[str, str]]) -> tuple[str, str]:
    """Map a summary mention to its canonical (kind, name).

    Same-kind names/aliases win fold-insensitively (summary `muster gmbh`
    -> entity `Muster GmbH`). Cross-kind exact matches keep the summary
    field's kind — the timeline feed outranks the folder: a misfiled
    `Companies/Max_Mustermann.md` mentioned as persons is rebuilt under
    `Persons/`, and the sweep relocates the old file (see `_find_kind_twin`).
    Tags never adopt either.
    """
    if kind != "Topics":
        lowered = name.strip().lower()
        for _folded, (k, canonical) in known.items():
            if k == "Topics":
                continue
            if k == kind and _folded == _fold(name):
                return k, canonical
    return kind, name


def _topic_qualifies(tag: str, months: set[str], known: dict[str, tuple[str, str]]) -> tuple[bool, str]:
    """True when a tag earns a Topics/ page: recurring, unique, not noise."""
    if tag.strip().lower() in TOPIC_EXCLUDE:
        return False, f"tag '{tag}' is excluded from topic pages"
    if len(months) < TOPIC_MIN_MONTHS:
        return False, f"tag '{tag}' seen in {len(months)} month(s), needs {TOPIC_MIN_MONTHS}"
    if _fold(tag) in known:
        return False, f"tag '{tag}' already covered by another entity"
    return True, "qualifies"


def _fingerprint_sources(root: Path, rels: list[str]) -> str:
    """Content fingerprint over sorted source rel paths + full texts (sha1, hex)."""
    import hashlib
    h = hashlib.sha1()
    for rel in sorted(rels):
        h.update(rel.encode("utf-8") + b"\0")
        try:
            h.update((root / rel).read_text(encoding="utf-8").encode("utf-8") + b"\0")
        except Exception:
            h.update(b"<unreadable>\0")
    return h.hexdigest()


def _find_kind_twin(existing: dict[str, dict], kind: str, name: str) -> str | None:
    """Vault-rel path of a same-named entity filed under another kind, if any.

    Exact case-insensitive name match only — near-duplicates are the
    migration report's job, not the sweep's. Used to relocate misfiled
    pages (timeline field kind wins) instead of spawning a twin.
    """
    wanted = name.strip().lower()
    for rel, facts in existing.items():
        if facts.get("kind") != kind and isinstance(facts.get("name"), str) \
                and facts["name"].strip().lower() == wanted:
            return rel
    return None


def _apply_kind_move(root: Path, move_from_rel: str, target_rel: str) -> tuple[bool, list[str]]:
    """Relocate a misfiled entity .md (+ companion .log.md) to its kind folder.

    Never clobbers: when the target already holds a file this is a genuine
    cross-kind duplicate for humans, not a move. Returns (moved, hints).
    """
    hints: list[str] = []
    src = root / move_from_rel
    dst = root / target_rel
    if not src.exists():
        return False, [f"kind move: {move_from_rel} vanished — skipped"]
    if dst.exists():
        return False, [f"kind conflict: {move_from_rel} and {target_rel} both exist — human merge needed"]
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
    except Exception as e:
        return False, [f"kind move {move_from_rel} -> {target_rel} failed: {e}"]
    hints.append(f"kind correction: moved {move_from_rel} -> {target_rel}")
    src_log = src.parent / (src.stem + ".log.md")
    if src_log.exists():
        dst_log = dst.parent / (dst.stem + ".log.md")
        if dst_log.exists():
            hints.append(f"kind correction: log {src_log.name} left in place ({dst_log.name} already exists)")
        else:
            try:
                src_log.rename(dst_log)
            except Exception as e:
                hints.append(f"kind correction: log move failed: {e}")
    return True, hints


def _decide_entity_stale(*, exists: bool, fm_type, stored_fp: str | None, current_fp: str) -> tuple[bool, str]:
    """Pure staleness decision, same shape as the index deciders."""
    if not exists:
        return True, "no entity file yet"
    if fm_type != "entity":
        return True, f"legacy entity file (type {fm_type!r}) — regenerating"
    if not stored_fp:
        return True, "entity file has no sources_fingerprint — regenerating"
    if stored_fp != current_fp:
        return True, "linked sources changed since last build"
    return False, "up to date"


def _read_entity_facts(path: Path) -> tuple[bool, object, str | None]:
    """(exists, fm_type_or_None, stored_fingerprint_or_None) for an entity .md."""
    if not path.exists():
        return False, None, None
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return True, None, None
    fm, _body, _error = _parse_frontmatter(text)
    if not isinstance(fm, dict):
        return True, None, None
    fp = fm.get("sources_fingerprint")
    return True, fm.get("type"), (fp.strip() if isinstance(fp, str) and fp.strip() else None)


def _logged_sources(log_text: str | None) -> list[str]:
    """Vault-rel source paths linked from a .log.md (timeline/ only, sorted).

    The log is the entity's provenance: every entry links the summaries it
    was built from, so these links replace the old frontmatter `sources:`.
    """
    if not isinstance(log_text, str):
        return []
    found: list[str] = []
    for m in re.finditer(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", log_text):
        rel = m.group(1).strip().strip("\"'")
        if rel.startswith("timeline/") and rel.endswith(".md") and rel not in found:
            found.append(rel)
    return sorted(found)


def _build_sources_import_entry(sources: list[str], stamp: str) -> str:
    """One code-written log entry absorbing legacy frontmatter `sources:`.

    First-touch rewrites drop the `sources:` key; this entry preserves the
    provenance in the log where it belongs. No LLM prose — just the links.
    """
    lines = [f"## {stamp} — sources import", "",
             f"Imported {len(sources)} previously-linked source(s) into the log (frontmatter no longer carries sources):", ""]
    lines.extend(f"- [[{rel}]]" for rel in sorted(sources))
    return "\n".join(lines) + "\n"


def _embed_text_parts(label: str, content: str | None) -> list:
    """Split a file dump into timeline-style message parts: a label part plus
    a verbatim content part (truncated with an explicit marker past the cap).

    Separate parts keep instruction apart from evidence: downstream readers
    (message-history mining, content tracking, dedup) can tell the work
    order from the file bytes, exactly like `_embed_for_prompt` in
    update_timeline.py.
    """
    from server.models.enums.message_enums import MessageContentType, MessagePartType

    def _part(text: str) -> dict:
        return {"type": MessagePartType.MESSAGE, "content_type": MessageContentType.TEXT, "content": text}

    if not isinstance(content, str) or not content.strip():
        return [_part(f"# {label}: <empty>\n")]
    if len(content) > _MAX_ENTITY_EMBED_CHARS:
        return [
            _part(f"# {label} (truncated to {_MAX_ENTITY_EMBED_CHARS} chars):\n"),
            _part(content[:_MAX_ENTITY_EMBED_CHARS]),
            _part("\n[... truncated ...]\n"),
        ]
    return [_part(f"# {label}:\n"), _part(content)]


def _raw_rels_from_texts(texts: list[str]) -> list[str]:
    """Original `raw/` source paths referenced by summary frontmatter (ordered, deduped).

    Summaries are lossy — these give the entity session somewhere to go
    when contact data or relations smell missing. URLs are skipped (files
    only); unparseable texts contribute nothing.
    """
    out: list[str] = []
    for text in texts or []:
        try:
            fm, _body, _error = _parse_frontmatter(text)
        except Exception:
            continue
        if not isinstance(fm, dict):
            continue
        for s in _fm_list_values(fm, "sources"):
            link_m = re.search(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", s)
            cand = (link_m.group(1) if link_m else s).strip().strip("\"'")
            if cand.startswith("raw/") and cand not in out:
                out.append(cand)
    return out


def _origin_section_block(raw_rels: list[str]) -> str:
    """Prompt section licensing reads of the original raw sources."""
    if not raw_rels:
        return ""
    listing = "\n".join(f"- {rel}" for rel in raw_rels)
    return f"""
## Missing details? Go to the origin

Summaries are lossy: if the evidence suggests the original message held
more than the summary captured — a business mail naming no email address,
an order naming no order number, a person with no contact, an invoice with
no IBAN, a signature the summary skipped — read the ORIGINAL source
file(s) and transcribe the missing facts verbatim into the right block:

{listing}

Rules: read-only — never modify anything under `raw/`; fill ONLY the gaps
the summary left (never re-synthesize what the summary already covers);
cite the summary as usual. Do NOT go digging by default — only on concrete
suspicion, and never for bulk marketing (ads promise nothing to find).
"""


def _fields_spec_block(kind: str, prefill: dict) -> str:
    """Prompt section describing the ```markdown-fields block for *kind*."""
    keys = list(ENTITY_COMMON_FIELDS) + list(ENTITY_KIND_FIELDS.get(kind, ())) + ["relations"]
    rel_hint = ENTITY_RELATION_HINTS.get(kind, "related")
    if prefill:
        found = "\n".join(f"- {k}: {', '.join(prefill[k])}" for k in sorted(prefill))
        pre_block = f"""
Deterministic code already found these in the sources — verify each against
the sources and include the correct ones (plus anything else you find):

{found}
"""
    else:
        pre_block = ""
    return f"""
## Structured record (first fenced block)

The page frontmatter is a structured record — fill it from the sources.
Return it as the FIRST block below. Allowed keys for kind {kind} (omit keys
with no data — never invent values, never use other keys):

{", ".join(keys)}

- `emails`/`phones`/`addresses`/`websites` are lists of strings.
- `relations` is a list of `type:` + `target:` items; `target` MUST be an
  existing vault page as `[[vault/rel/path.md]]` (cite it from the
  sources). Suggested relation types: {rel_hint}.
- Record relations here, NOT as body sections — the body is prose.
{pre_block}"""


def _build_entity_session_brief(kind: str, name: str, entity_rel: str, log_rel: str,
                                new_rels: list[str], prefill: dict | None = None,
                                raw_rels: list[str] | None = None) -> str:
    """Work order for revising an existing entity (instruction only).

    File bytes travel as separate message parts (current .md, log tail, new
    sources) — this string only names them. See `_embed_text_parts`.
    """
    if new_rels:
        src_list = "\n".join(f"- {rel}" for rel in new_rels)
    else:
        src_list = "- (none — reconcile the file against its own linked sources)"
    return f"""Revise the entity page `{entity_rel}` ({kind}: {name}). This is an UPDATE, not a fresh draft.

Your working dir is the vault root; all paths below are vault-relative.

The evidence follows as separate message parts, after this instruction:
the CURRENT ENTITY FILE, the CURRENT LOG TAIL (newest at the bottom — do
NOT repeat these entries), and the NEW SOURCE SUMMARIES since the last
build. Read the parts, not just this message.

New source summaries:

{src_list}

Merge the new sources into the page: new facts, numbers, dates, corrected
spellings, new relations — with wikilink citations to the source summaries.
Keep whatever still holds; never drop a fact that still has a source; never
invent facts (mark anything unverified as such). Record metadata, the file
itself, and provenance are built by code — your body keeps the existing
section structure (`# {name}`, the relation-to-this-wiki's-subject section, …).

Also append exactly ONE new log entry covering this update: dated today,
linking the new source(s), 1–4 bullets on what changed on the page.
{_fields_spec_block(kind, prefill or {})}{_origin_section_block(raw_rels or [])}
Return EXACTLY the three fenced blocks below as your LAST message — no
explanations, write NO files, and output NOTHING after them (a separate code
pass reads your last message and stores all three parts; it cannot see anything
else you write):

```{ENTITY_FIELDS_FENCE}
emails: []
phones: []
relations:
  - type: <relation>
    target: "[[<existing-vault-page>]]"
```

```{ENTITY_BODY_FENCE}
# {name}

<full revised body: existing sections kept, new facts merged, wikilink citations>
```

```{ENTITY_LOG_FENCE}
## YYYY-MM-DD HH:MM — [[<new-source-rel>]]

- <what changed on the page in this update>
```
"""


def _build_new_entity_brief(kind: str, name: str, entity_rel: str, log_rel: str,
                             source_rels: list[str], prefill: dict | None = None,
                             raw_rels: list[str] | None = None) -> str:
    """Work order for drafting a brand-new entity page (instruction only).

    The mentioning summaries travel as separate message parts — this string
    only names them. See `_embed_text_parts`.
    """
    src_list = "\n".join(f"- {rel}" for rel in source_rels)
    return f"""Draft a new entity page `{entity_rel}` ({kind}: {name}).

Your working dir is the vault root; all paths below are vault-relative.

This entity has no page yet — everything it is known from is the
MENTIONING SOURCE SUMMARIES attached as separate message parts after this
instruction:

{src_list}

Write the initial page from ONLY these sources: who/what this is, how it
relates to the subject of this wiki (whoever or whatever this wiki
documents — check `index.md`/`rules.md` if unsure), key facts with
wikilink citations. Never invent facts (mark
anything unverified as such). Record metadata, the file itself, and
provenance are built by code.

Also write the genesis log entry: dated today, linking the source(s), 1–4
bullets on what the page was created from.
{_fields_spec_block(kind, prefill or {})}{_origin_section_block(raw_rels or [])}
Return EXACTLY the three fenced blocks below as your LAST message — no
explanations, write NO files, and output NOTHING after them (a separate code
pass reads your last message and stores all three parts; it cannot see anything
else you write):

```{ENTITY_FIELDS_FENCE}
emails: []
phones: []
relations:
  - type: <relation>
    target: "[[<existing-vault-page>]]"
```

```{ENTITY_BODY_FENCE}
# {name}

<initial body: a section on the relation to this wiki's subject plus whatever sections the sources support, wikilink citations>
```

```{ENTITY_LOG_FENCE}
## YYYY-MM-DD HH:MM — [[<source-rel>]]

- <what the page was created from>
```
"""


def _parse_entity_result(text: str | None, expected_name: str, kind: str, root=None) -> tuple[dict | None, str | None, str | None, list[str]]:
    """Split a session's last message into (fields_or_None, body_or_None, log_entry_or_None, hints)."""
    hints: list[str] = []
    if not isinstance(text, str) or not text.strip():
        return None, None, None, ["prose session returned no usable text — nothing was written"]
    fields, field_hints = _parse_entity_fields(text, kind, root=root)
    hints.extend(field_hints)
    body_m = re.search(rf"```{re.escape(ENTITY_BODY_FENCE)}\s*\n(.*?)```", text, re.DOTALL)
    log_m = re.search(rf"```{re.escape(ENTITY_LOG_FENCE)}\s*\n(.*?)```", text, re.DOTALL)
    body = body_m.group(1).strip() if body_m else None
    entry = log_m.group(1).strip() if log_m else None
    if body_m is None:
        hints.append(f"missing ```{ENTITY_BODY_FENCE}``` block — body not written")
    elif len(body) < 50:
        hints.append("body block is empty or too short (<50 chars) — body not written")
        body = None
    elif body.startswith("---"):
        hints.append("body block starts with frontmatter (it is code-built) — body not written")
        body = None
    elif not body.startswith(f"# {expected_name}"):
        hints.append(f"body should start with exactly `# {expected_name}` — body not written")
        body = None
    if log_m is None:
        hints.append(f"missing ```{ENTITY_LOG_FENCE}``` block — log not appended")
    elif not re.match(r"^## \d{4}-\d{2}-\d{2}( \d{2}:\d{2})?\s+—", entry):
        hints.append("log entry must start with `## YYYY-MM-DD HH:MM — ` — log not appended")
        entry = None
    elif "[[" not in entry:
        hints.append("log entry links no source (`[[…]]`) — log not appended")
        entry = None
    return fields, body, entry, hints


def _build_entity_file(kind: str, name: str, aliases: list[str], fields: dict, body: str,
                       created: str, updated: str,
                       head_hash: str | None, fingerprint: str) -> str:
    """Assemble an entity .md: code-built frontmatter (record + provenance) + session body.

    The frontmatter is the structured record (contact data, typed relations);
    it carries NO `sources:` list — provenance lives in the .log.md. Only
    non-empty fields are emitted, in stable order (common lists, kind
    fields, relations last).
    """
    fm_lines = ["---", "type: entity", f"kind: {kind}", f"name: {name}",
                f"aliases: {_yaml_flow_list(aliases)}", f"date: {created}", f"updated: {updated}"]
    if head_hash is not None:
        fm_lines.append(f"last_checked_at: {head_hash}")
    fm_lines.append(f"sources_fingerprint: {fingerprint}")
    for key in ENTITY_COMMON_FIELDS:
        values = (fields or {}).get(key) or []
        if values:
            fm_lines.append(f"{key}: {_yaml_flow_list([str(v) for v in values])}")
    for key in ENTITY_KIND_FIELDS.get(kind, ()):
        value = (fields or {}).get(key)
        if isinstance(value, list):
            if value:
                fm_lines.append(f"{key}: {_yaml_flow_list([str(v) for v in value])}")
        elif value is not None and (not isinstance(value, str) or value.strip()):
            fm_lines.append(f"{key}: {value}")
    relations = (fields or {}).get("relations") or []
    if relations:
        fm_lines.append("relations:")
        for item in relations:
            fm_lines.append(f"  - type: {item['type']}")
            fm_lines.append(f"    target: \"{item['target']}\"")
    fm_lines.append("---")
    return "\n".join(fm_lines) + "\n\n" + body.strip() + "\n"


def _old_structured_fields(entity_path: Path, kind: str) -> dict:
    """Structured fields already stored in an entity file (for updates that add no new ones)."""
    try:
        fm, _b, _e = _parse_frontmatter(entity_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(fm, dict):
        return {}
    allowed = set(ENTITY_COMMON_FIELDS) | set(ENTITY_KIND_FIELDS.get(kind, ())) | {"relations"}
    out: dict = {}
    for key in allowed:
        value = fm.get(key)
        if key == "relations":
            kept = []
            for item in (value if isinstance(value, list) else []):
                if isinstance(item, dict) and isinstance(item.get("type"), str) and isinstance(item.get("target"), str):
                    kept.append({"type": item["type"], "target": item["target"]})
            if kept:
                out[key] = kept
        elif key in ENTITY_COMMON_FIELDS:
            items = [str(v).strip() for v in value] if isinstance(value, list) else ([str(value).strip()] if value else [])
            if items:
                out[key] = items
        elif value is not None and (not isinstance(value, str) or value.strip()):
            out[key] = value
    return out


def _spawn_entity_session(_session, tag: str, brief: str, extra_parts: list | None = None):
    """Spawn the prose session for one entity; returns (ok, session_pk_or_None, body_ref_or_error).

    *extra_parts* (label/content evidence parts) are delivered after the
    instruction brief, exactly like the timeline's multi-part messages.
    """
    from time import time
    ok, _, session_pk, ref = _spawn_baseagent(
        _session,
        name=f"p{_session.model.pk}:entity:{re.sub(r'[^a-zA-Z0-9]+', '_', tag)[:40]}:{int(time())}",
        description=f"Entity {tag}",
        brief=brief,
        extra_parts=extra_parts,
    )
    if not ok:
        return False, None, ref
    return True, session_pk, ref


def _legacy_fm_sources(entity_path: Path) -> list[str]:
    """Timeline rels from a legacy frontmatter `sources:` list (pre-write read)."""
    try:
        fm, _b, _e = _parse_frontmatter(entity_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(fm, dict):
        return []
    out: list[str] = []
    for s in _fm_list_values(fm, "sources"):
        link_m = re.search(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", s)
        cand = (link_m.group(1) if link_m else s).strip().strip("\"'")
        if cand.startswith("timeline/") and cand.endswith(".md") and cand not in out:
            out.append(cand)
    return out


def write_entity(_session, entity_rel, kind=None, name=None, body_result=None, session_pk=None, sources=None, aliases=None, head_hash=None, collect_hints=None, move_from_rel=None):
    """Merge structured fields + prose body + log entry into an entity .md / .log.md.

    ``body_result``/``session_pk`` resolve exactly like write_day_index (ref,
    then explicit final_result args, then last assistant message). The text
    must hold the three fenced blocks from the session brief (fields, body,
    log); all are validated before anything is written. Frontmatter is the
    structured record — code-owned identity/provenance (type/kind/name/
    aliases/date/updated/fingerprint) plus validated session fields — and
    carries NO `sources:` list: provenance lives in the .log.md, and the
    log entry is appended verbatim (old entries are never touched). Legacy
    frontmatter `sources:` are absorbed into the log via a code-written
    import entry on first rewrite. When ``move_from_rel`` names a same-named
    file under another kind folder, it is relocated first (kind correction);
    a genuine both-exist conflict aborts instead of clobbering.
    Returns (True, {status, entity, log, ...}).
    """
    sources = list(sources or [])
    aliases = list(aliases or [])
    collect_hints = list(collect_hints or [])
    root = _workspace_root(_session)
    if root is None:
        return False, {"status": "error", "entity": entity_rel, "message": "write_entity: cannot resolve workspace root"}
    entity_path = (root / entity_rel) if not Path(entity_rel).is_absolute() else Path(entity_rel)
    try:
        kind_folder = entity_path.relative_to(root / "entities").parts[0]
    except Exception:
        return False, {"status": "error", "entity": entity_rel, "message": f"write_entity: not under entities/: {entity_rel}"}
    if kind is None:
        kind = kind_folder
    if name is None:
        name = entity_path.stem
    if kind not in ENTITY_KINDS:
        return False, {"status": "error", "entity": entity_rel, "message": f"write_entity: unknown kind folder: {kind}"}

    fr_text, hist_text = _read_child_session_texts(session_pk)
    text, text_source = _pick_body([
        ("ref", _extract_result_text(body_result)),
        ("final_result", fr_text),
        ("last_message", hist_text),
    ])
    if text is None:
        return False, {
            "status": "error", "entity": entity_rel,
            "lint_results": collect_hints + [f"prose session returned no usable text ({text_source}) — nothing was written"],
            "message": "write_entity: no session text, files could not be written",
        }
    fields, body, entry, parse_hints = _parse_entity_result(text, name, kind, root=root)
    lint_results = collect_hints + parse_hints
    if fields is None and body is None and entry is None:
        return False, {
            "status": "error", "entity": entity_rel,
            "lint_results": lint_results,
            "message": "write_entity: neither fields nor body nor log entry usable — nothing was written",
        }

    if move_from_rel:
        moved, move_hints = _apply_kind_move(root, move_from_rel, entity_rel)
        lint_results.extend(move_hints)
        if not moved and any("both exist" in h for h in move_hints):
            return False, {
                "status": "error", "entity": entity_rel,
                "lint_results": lint_results,
                "message": f"write_entity: kind conflict — {move_from_rel} and {entity_rel} both exist, human merge needed",
            }
        # A vanished twin just means "create fresh"; anything written below
        # merges aliases/creation-date from the relocated file when present.

    today_str = datetime.datetime.now().date().isoformat()
    now_stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    # Legacy fm sources (pre-write read): absorbed into the log on rewrite.
    legacy_here = _legacy_fm_sources(entity_path) if entity_path.exists() else []
    wrote, appended = False, False
    if body is not None:
        # Preserve identity and previously structured data when updating.
        created = today_str
        merged_aliases = list(aliases)
        if entity_path.exists():
            try:
                old_fm, _b, _e = _parse_frontmatter(entity_path.read_text(encoding="utf-8"))
                if isinstance(old_fm, dict):
                    if isinstance(old_fm.get("date"), str) and old_fm["date"].strip():
                        created = old_fm["date"].strip()
                    merged_aliases = list(dict.fromkeys([*_fm_list_values(old_fm, "aliases"), *aliases]))
            except Exception:
                pass
        old_fields = _old_structured_fields(entity_path, kind) if entity_path.exists() else {}
        # Session fields win per key; omitted keys keep stored values; code
        # regex finds are unioned into the list fields so machine patterns
        # survive LLM inattention.
        merged_fields = dict(old_fields)
        if fields is not None:
            merged_fields.update(fields)
        for key, found in _extract_contact_facts([body]).items():
            if key in ENTITY_COMMON_FIELDS or key == "bank_iban":
                merged_fields[key] = list(dict.fromkeys([*(merged_fields.get(key) or []), *found]))
        # Fingerprint covers the future-logged set: legacy sources (about to
        # be imported) plus whatever the new entry links. Recomputed from
        # disk so parallel runs can't desync it.
        entry_links = _logged_sources(entry) if entry else []
        fingerprint = _fingerprint_sources(root, sorted(set(legacy_here) | set(entry_links)))
        file_text = _build_entity_file(kind, name, merged_aliases, merged_fields, body,
                                       created, today_str, head_hash, fingerprint)
        try:
            entity_path.parent.mkdir(parents=True, exist_ok=True)
            entity_path.write_text(file_text, encoding="utf-8")
            wrote = True
        except Exception as e:
            return False, {"status": "error", "entity": entity_rel, "lint_results": lint_results,
                           "message": f"write_entity: cannot write {entity_rel}: {e}"}
    if entry is not None or (wrote and legacy_here):
        log_path = entity_path.parent / (entity_path.stem + ".log.md")
        try:
            if not log_path.exists():
                log_path.write_text(f"# Log for {name}\n\n", encoding="utf-8")
            if wrote and legacy_here:
                logged_now = _logged_sources(log_path.read_text(encoding="utf-8"))
                import_only = [s for s in legacy_here if s not in logged_now]
                if import_only:
                    with log_path.open("a", encoding="utf-8") as fh:
                        fh.write(_build_sources_import_entry(import_only, now_stamp) + "\n")
            if entry is not None:
                with log_path.open("a", encoding="utf-8") as fh:
                    fh.write(entry + "\n")
                appended = True
        except Exception as e:
            lint_results.append(f"log append failed: {e}")
    return True, {
        "status": "success",
        "entity": entity_rel,
        "log": _vault_rel(_session, entity_path.parent / (entity_path.stem + ".log.md")),
        "wrote_md": wrote,
        "appended_log": appended,
        "lint_results": lint_results,
        "message": f"write_entity: {entity_rel} (md {'written' if wrote else 'skipped'}, log {'appended' if appended else 'skipped'})",
    }


def update_entities(_session: Session, limit: int = 5, entity: str | None = None, kinds: list[str] | None = None):
    """Rebuild stale entity pages (``entities/<Kind>/<Letter>/<Slug>.md`` + ``.log.md``).

    Collects mentions from every timeline summary, resolves aliases/case
    against existing pages, qualifies topic candidates, then dispatches one
    prose session per stale entity (new pages first, then updates sorted by
    path) up to *limit*. A same-named page filed under another kind is
    relocated (timeline field kind wins; both-exist conflicts are flagged,
    never clobbered). An explicit *entity* (vault-rel path) is always
    rebuilt in place. Optional *kinds* narrows the sweep (e.g. ["Persons"]). All refs
    converge in ``write_entity``. Returns (True, {status, results}).
    """
    root = _workspace_root(_session)
    if root is None:
        return False, {"status": "error", "message": "cannot resolve workspace root"}
    if kinds is not None:
        unknown = [k for k in kinds if k not in ENTITY_KINDS]
        if unknown:
            return False, {"status": "error", "message": f"unknown kinds {unknown} — want subset of {list(ENTITY_KINDS)}"}
        wanted = set(kinds)
    else:
        wanted = set(ENTITY_KINDS)
    write_task = _session.get_task("write_entity")
    if write_task is None:
        return False, {"status": "error", "message": "task 'write_entity' is not available"}

    mentions, collect_hints = _collect_entity_mentions(root / "timeline", root)
    existing = _read_existing_entities(root / "entities", root)
    known = _build_known_map(existing)

    # Resolve mentions to canonical (kind, name); drop unqualified topics.
    resolved: dict[tuple[str, str], dict] = {}
    for (kind, name), info in mentions.items():
        if kind not in wanted:
            continue
        if kind == "Topics":
            ok, _reason = _topic_qualifies(name, info["months"], known)
            if not ok:
                continue
        ckind, cname = _resolve_mention(kind, name, known)
        key = (ckind, cname)
        slot = resolved.setdefault(key, {"sources": [], "months": set()})
        for rel in info["sources"]:
            if rel not in slot["sources"]:
                slot["sources"].append(rel)
        slot["months"] |= info["months"]
    for slot in resolved.values():
        slot["sources"].sort()

    if entity is not None:
        entity_rel = entity
        m = re.match(r"^entities/([^/]+)/[^/]+/(.+)\.md$", entity_rel)
        if not m or m.group(1) not in wanted:
            return False, {"status": "error", "message": f"bad entity '{entity}' — want entities/<Kind>/<Letter>/<Slug>.md"}
        kind, slug = m.group(1), m.group(2)
        name = slug.replace("_", " ")
        # Prefer the stored canonical name when the file already exists.
        facts = existing.get(entity_rel)
        if facts is not None:
            name = facts["name"]
        queue = [(kind, name, entity_rel, True)]
    else:
        queue = []
        used_rels: dict[str, tuple[str, str]] = {}
        for (kind, name), info in sorted(resolved.items()):
            if kind not in wanted:
                continue
            rel = _entity_rel(kind, name)
            if rel is None:
                collect_hints.append(f"cannot slugify {kind} name '{name}' — skipped")
                continue
            if rel in used_rels:
                # Two spellings, one slug (e.g. "A B" vs "A_B"): the survivor
                # absorbs the loser as an alias; the write pass merges it.
                other_kind, other_name = used_rels[rel]
                collect_hints.append(
                    f"slug collision: {kind} '{name}' and {other_kind} '{other_name}' share `{rel}`"
                    f" — '{name}' becomes an alias of '{other_name}'")
                slot = resolved[(other_kind, other_name)]
                for r in info["sources"]:
                    if r not in slot["sources"]:
                        slot["sources"].append(r)
                slot["sources"].sort()
                slot.setdefault("absorbed_aliases", []).append(name)
                continue
            used_rels[rel] = (kind, name)
            queue.append((kind, name, rel, False))

    head_hash = _git_head(root)
    results = []
    spawned = 0
    for kind, name, rel, explicit in queue:
        if spawned >= limit and not explicit:
            break
        info = resolved.get((kind, name), {"sources": [], "months": set()})
        facts = existing.get(rel)
        move_from = None
        if not explicit and facts is None:
            # Same name filed under another kind: relocate it (timeline
            # field kind wins) instead of spawning a twin.
            twin = _find_kind_twin(existing, kind, name)
            if twin is not None:
                move_from = twin
                collect_hints.append(
                    f"kind correction: '{name}' is filed under {twin} — relocating to {rel}")
        elif not explicit and facts is not None:
            twin = _find_kind_twin(existing, kind, name)
            if twin is not None and twin != rel:
                # Both kind folders hold the name: genuine cross-kind
                # duplicate — update the filed copy in place, flag for humans.
                collect_hints.append(
                    f"kind conflict: {twin} and {rel} both exist — updating {twin} in place, human merge needed")
                rel = twin
                kind = existing[rel]["kind"]
                name = existing[rel]["name"]
                facts = existing.get(rel)
        current_fp = _fingerprint_sources(root, info["sources"])
        if explicit:
            needs, reason = True, "explicitly requested"
        else:
            exists, fm_type, stored_fp = (True, facts["type"], facts["fingerprint"]) if facts else (False, None, None)
            needs, reason = _decide_entity_stale(exists=exists, fm_type=fm_type, stored_fp=stored_fp, current_fp=current_fp)
        if not needs:
            if explicit:
                results.append({"entity": rel, "status": "skipped", "message": f"up to date ({reason})"})
            continue

        log_rel = _log_rel(rel)
        extra_parts: list = []
        if facts is not None:
            extra_parts.extend(_embed_text_parts(f"CURRENT ENTITY FILE ({rel})", facts["text"]))
            try:
                log_tail = "\n".join((root / log_rel).read_text(encoding="utf-8").split("\n")[-60:])
            except Exception:
                log_tail = ""
            extra_parts.extend(_embed_text_parts(f"CURRENT LOG TAIL ({log_rel})", log_tail))

        def _read_source(rel_path: str) -> tuple[str, str]:
            try:
                return rel_path, (root / rel_path).read_text(encoding="utf-8")
            except Exception:
                return rel_path, "(unreadable — cite from the filename only)"

        def _embed_source(item: tuple[str, str]) -> list:
            return _embed_text_parts(f"SOURCE SUMMARY ({item[0]})", item[1])

        if facts is None:
            # New page: the mentioning summaries ride along as parts (capped).
            brief_sources = [_read_source(r) for r in info["sources"][:8]]
            for item in brief_sources:
                extra_parts.extend(_embed_source(item))
            prefill = _extract_contact_facts([text for _r, text in brief_sources])
            raw_rels = _raw_rels_from_texts([text for _r, text in brief_sources])[:8]
            brief = _build_new_entity_brief(kind, name, rel, log_rel, info["sources"][:8], prefill, raw_rels)
            if len(info["sources"]) > 8:
                collect_hints.append(f"{rel}: {len(info['sources'])} sources, first 8 attached as parts")
        else:
            stored = set(facts["sources"])
            new_rels = [r for r in info["sources"] if r not in stored] or info["sources"]
            brief_sources = [_read_source(r) for r in new_rels[:8]]
            for item in brief_sources:
                extra_parts.extend(_embed_source(item))
            prefill = _extract_contact_facts([text for _r, text in brief_sources])
            raw_rels = _raw_rels_from_texts([text for _r, text in brief_sources])[:8]
            brief = _build_entity_session_brief(kind, name, rel, log_rel, new_rels[:8], prefill, raw_rels)
            if len(new_rels) > 8:
                collect_hints.append(f"{rel}: {len(new_rels)} new sources, first 8 attached as parts")

        ok, session_pk, body_ref = _spawn_entity_session(_session, f"{kind}/{name}", brief, extra_parts)
        if not ok:
            results.append({"entity": rel, "status": "error", "reason": reason, "message": f"prose session not spawned: {body_ref}"})
            continue
        write_ref = write_task.delay(
            entity_rel=rel, kind=kind, name=name, body_result=body_ref, session_pk=session_pk,
            sources=info["sources"], aliases=info.get("absorbed_aliases", []),
            head_hash=head_hash, collect_hints=collect_hints, move_from_rel=move_from,
        )
        results.append({"entity": rel, "status": "dispatched", "session_pk": session_pk, "reason": reason, "write": write_ref})
        spawned += 1
    # The catalog is deterministic code output: rebuild unconditionally so
    # new/relocated pages show up even when the session limit cut the queue.
    indices = rebuild_entity_indices(root)
    return True, {"status": "success", "results": results, "indices": indices}
