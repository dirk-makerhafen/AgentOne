

from __future__ import annotations

import datetime
import re
from pathlib import Path

from runtime.session.session import Session
from server.models.settings import ReasoningEffort
from pathlib import Path
from server.models.enums.message_enums import MessageContentType, MessagePartType
from server.models.enums.session_enums import SessionType



SUMMARY_FORMAT_REFERENCE = '''
## Output Format

The summary **must** use this exact structure: (not including the ```yaml .. ``` part)

```yaml
---
type: summary
title: descriptive title
date: <received date + time, e.g. 2022-10-21 13:48>
updated: <today's date>
tags: [<relevant tags>]
persons: [<all persons mentioned>]
companies: [<all companies mentioned>]
groups: [<all clubs, associations, crews, teams, initiatives mentioned>]
products: [<all products mentioned>]
uids: [<all relevant order IDs, reference numbers, tracking numbers, xref IDs, etc.>]
sources: ["[[raw/path/to/source.md]]"]
author: <sender / originator, if available>
---
# <Title>

<Key claims, important numbers, decisions, quotes, and why this matters.>
```

## Metadata Rules

* `type` MUST be exactly `summary`.
* `title` MUST be a descriptive title in "<What> - <Who>" format. 
* `date` MUST be the date AND time the source material was received, format
  `YYYY-MM-DD HH:MM` (take it from the mail's Date header or equivalent).
  The time matters — many mails arrive per day, and the summary file is
  stored as `timeline/YYYY/MM/DD/YYYYMMDD-HHMM_<Title>.md`, with the prefix
  derived from this field. If the source truly carries no time, date alone
  is accepted.
* `updated` MUST contain today's date (`YYYY-MM-DD`, no time needed).
* `tags` MUST contain relevant, consistent topic tags.
  * Derive tags from the actual subject matter.
  * Prefer existing/common vocabulary where possible.
  * Examples: `buchhaltung`, `mitglieder`, `workshop`, `lieferung`, `rechnung`, `veranstaltung`.
* `persons` MUST contain all relevant persons explicitly mentioned in the source.
* `companies` MUST contain all relevant companies or organizations explicitly mentioned.
* `groups` MUST contain all relevant collectives explicitly mentioned that are
  neither a single person nor a commercial company: clubs, associations
  (Vereine), crews, teams, initiatives, communities, working groups, scenes
  (e.g. Chaos Computer Club, Freifunk, CodeWeek crew, Makerhafen e.V.).
  Rule of thumb: if it sells you something, bills you, or governs you, it
  belongs in `companies` (vendors, platforms, shops, authorities, commercial
  entities of any legal form). If you could become a member or it is a crew
  of people, it belongs in `groups`.
* `products` MUST contain all relevant products, services, or named product lines explicitly mentioned.
  * Exception: for purely promotional mail (see below), leave `products` empty.
* `uids` MUST contain relevant identifiers such as:
  * order IDs
  * invoice numbers
  * reference numbers
  * tracking numbers
  * customer IDs
  * xref IDs
  * other stable external identifiers
* Do not invent metadata. If a field has no applicable values, use an empty list (`[]`), except `author`, which may be omitted or left empty if unavailable.
* `author` should identify the sender, originator, or creator of the source when that information is available.

## Sources

The `sources` field is **always plural** and MUST be a list.
Every source MUST point to the original raw source using a wikilink, for example:

```yaml
sources: ["[[raw/emails/example/message.md]]"]
```

Multiple sources:

```yaml
sources:
  - "[[raw/emails/example/message.md]]"
  - "[[raw/documents/example.md]]"
```

A source may also be a URL when the original source is a web page:

```yaml
sources: ["https://example.com/page"]
```

**Never use `source:`.** The singular field name is invalid and will be flagged by the linter.

Do not link to another summary when the original raw source is available. Always prefer the original raw file.

## Summary Content

The body should capture the information that is useful later without reproducing the source verbatim.

Prioritize:

* important facts and key claims
* decisions and outcomes
* dates and deadlines
* relevant amounts, quantities, and measurements
* commitments and responsibilities
* important changes or status updates
* identifiers and references that matter for future lookup
* short quotes when the exact wording is important
* context explaining **why the information matters**

Use bullet points by default for easy scanning.

Do not add speculation, assumptions, or information that cannot be supported by the source.

## Promotional / marketing mail

In case content to summarize is bulk marketing ("our newest products", newsletters,
sale announcements). They still get a timeline entry, but keep it brief:

* Body: 2–4 bullets max — who sent it, what is being promoted in one line.
* `tags`: include `werbung` (plus the sender topic if useful).
* Leave `persons`, `companies`, `groups`, `products`, and `uids` as empty lists (`[]`)
  unless the mail documents a real interaction (an order, a reply, a support
  case). In particular, do NOT catalog advertised items into `products` —
  that field is for products relevant to our own operations, not for things
  someone is trying to sell us.
* `author` and `sources` follow the normal rules.

## Title

Choose a short, descriptive `<Title>` that identifies the event or topic clearly.
Make the title filesystem-safe and avoid characters that are problematic in filenames, like non acii chars, umlaute, smileys, icons, quotes, pipes, &, <> and so on.

* **No date or time in the title.** The file already lives under
  `timeline/<year>/<month>/<day>/` with a `YYYYMMDD-HHMM` filename prefix,
  so any date or time in the title is redundant and makes same-day
  summaries look identical. Bad: `Anmeldung Familienbasteltag vom 21.10.2022`.
  Good: `Anmeldung Familienbasteltag - Anja Fabier`.

* **Name the person or entity that distinguishes the correspondence.**
  Use the relevant external person, organization, customer, registrant, recipient,
  sender, or other subject — whoever makes this item distinct from other items
  about the same topic.
  Format: `<What> - <Who>`.
  Examples:
  * Received email: `Anmeldung Familienbasteltag - Anja Fabier`
  * Reply to Anja: `Anmeldung Familienbasteltag - Anja Fabier`
  * Invoice clarification: `Rechnungsklaerung - Acme Corp`
  * Marketing mail: `Werbung Somfy - Sonderangebote Oktober`
  * Reply to a company: `Rechnungsklaerung - Acme Corp`
  For a reply, follow-up, or forwarded message, preserve the identity of the
  **other party or original subject** rather than using our own name. The title
  should normally remain consistent across the correspondence thread unless the
  subject or purpose has genuinely changed.
  Only use your our name when it is genuinely the subject of the item.
  For example, `Bewerbung - Peter Miller` is appropriate if we are Peter Miller and the document is specifically
  about our own application. It is not appropriate merely because we sent the email.


## Quality Requirements

* frontmatter `date` carries the correct receive date + time (it becomes the `YYYYMMDD-HHMM` filename prefix)
* the YAML frontmatter is valid
* all required fields are present
* `sources` is plural and contains the original source(s)
* no `source:` field exists
* persons, companies, groups, products, and UIDs are extracted rather than guessed
* tags are relevant and consistent
* the summary is factual and concise
* the title is descriptive and filesystem-safe
* the body explains why the information matters where appropriate
* the file is never renamed (the `YYYYMMDD-HHMM` filename prefix is derived from `date` at creation time)


'''


# ---------------------------------------------------------------------------
# Pure helpers (no session needed — unit-testable)
# ---------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r'\A\s*(?:\ufeff)?---\s*\n(.*?)\n---\s*\n?', re.DOTALL)
REQUIRED_FIELDS = ("type", "date", "updated", "tags", "persons", "companies", "products", "uids", "sources")
# title is required too, but handled with its own filesystem/H1 checks
LIST_FIELDS = ("tags", "persons", "companies", "products", "uids")
DATETIME_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?$')
# Raw mail/imessage archive folders embed the receive time, e.g.
# ``.../20221021-1348__sender__subject/message.md``.
_RAW_TS_RE = re.compile(r'(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})')
_FS_RESERVED = frozenset('\\/:*?"<>|')
_PLACEHOLDER_VALUES = frozenset({"", "n/a", "na", "none", "unknown", "tbd", "...", "-", "_"})


# Cap embedded file contents so a huge raw file cannot blow up the
# double-check session's context. Summaries are small; raw mails can be long.
_MAX_EMBED_CHARS = 50000


_MONTHS_DE = ("januar", "februar", "maerz", "april", "mai", "juni",
               "juli", "august", "september", "oktober", "november", "dezember")
_MONTHS_EN = ("january", "february", "march", "april", "may", "june", "july",
              "august", "september", "october", "november", "december")


def _extract_summary_text(summary_result) -> str | None:
    """Unwrap the llm_query/call_llm_direct result into the raw summary text.

    Handles the shapes this value can take by the time the scheduler
    resolves task references: a plain string, a result dict with
    ``content``, a ``(bool, dict)`` tuple, or a nested ``{"result": ...}``.
    Returns None when no usable text is found.
    """
    seen = 0
    current = summary_result
    def remove_fence(text):
        text = text.strip()
        if text.startswith("```yaml"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()
    
    while seen < 5:
        seen += 1
        if current is None:
            return None
        if isinstance(current, str):
            current = remove_fence(current)
            return current if current.strip() else None
        if isinstance(current, (list, tuple)) and len(current) == 2 and isinstance(current[0], bool):
            current = current[1]
            continue
        if isinstance(current, dict):
            content = current.get("content")
            if isinstance(content, str) and content.strip():
               return remove_fence(content)
            nested = current.get("result", current.get("data"))
            if nested is not None and nested is not current:
                current = nested
                continue
            return None
        return None
    return None


def _parse_frontmatter(summary_text: str):
    """Split summary into (frontmatter_dict, body, fm_raw_text, error)."""
    m = FRONTMATTER_RE.match(summary_text)
    if not m:
        return None, summary_text, None, "missing frontmatter (file must start with --- YAML ---)"
    fm_raw = m.group(1)
    body = summary_text[m.end():]
    try:
        import yaml
        try:
            fm = yaml.safe_load(fm_raw)
        except Exception:
            # safe_load constructs timestamp objects and rejects impossible
            # dates (e.g. month 13) at parse time. Retry without timestamp
            # construction so per-field checks can report precisely.
            fm = yaml.load(fm_raw, Loader=yaml.BaseLoader)
    except Exception as e:
        return None, body, fm_raw, f"frontmatter is not valid YAML: {e}"
    if not isinstance(fm, dict):
        return None, body, fm_raw, "frontmatter must be a YAML mapping"
    return fm, body, fm_raw, None


def _split_datetime_value(value) -> tuple[str | None, str | None]:
    """Split a frontmatter date into (date, time) parts.

    Accepts YAML-parsed date/datetime objects as well as strings:
    ``YYYY-MM-DD``, ``YYYY-MM-DD HH:MM[:SS]`` or ``YYYY-MM-DDTHH:MM[:SS]``.
    Returns (date_str, time_str) with time as ``HH:MM`` or None.
    Returns (None, None) when the value is unusable or out of range —
    use :func:`_check_date_value` for a human-readable reason.
    """
    if isinstance(value, datetime.datetime):
        date_s = value.date().isoformat()
        return (date_s, f"{value.hour:02d}:{value.minute:02d}")
    if isinstance(value, datetime.date):
        return (value.isoformat(), None)
    if not isinstance(value, str):
        return (None, None)
    m = DATETIME_RE.match(value.strip().strip('"').strip("'"))
    if not m:
        return (None, None)
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (2000 <= y <= 2030):
        return (None, None)
    try:
        datetime.date(y, mo, d)
    except ValueError:
        return (None, None)
    if m.group(4) is None:
        return (f"{y:04d}-{mo:02d}-{d:02d}", None)
    hh, mi = int(m.group(4)), int(m.group(5))
    if not (0 <= hh <= 23 and 0 <= mi <= 59):
        return (None, None)
    return (f"{y:04d}-{mo:02d}-{d:02d}", f"{hh:02d}:{mi:02d}")


def _check_date_value(value, field_name: str) -> str | None:
    if isinstance(value, (datetime.datetime, datetime.date)):
        raw = value.isoformat()
    elif isinstance(value, str):
        raw = value.strip().strip('"').strip("'")
    else:
        return f"`{field_name}` must be a YYYY-MM-DD string, got {type(value).__name__}"
    m = DATETIME_RE.match(raw)
    if not m:
        return f"`{field_name}` '{value}' is not YYYY-MM-DD (time as `YYYY-MM-DD HH:MM` is allowed and wanted for `date`)"
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (2000 <= y <= 2030):
        return f"`{field_name}` year {y} out of range 2000-2030"
    try:
        datetime.date(y, mo, d)
    except ValueError:
        return f"`{field_name}` '{value}' is not a real calendar date"
    if m.group(4) is not None:
        hh, mi = int(m.group(4)), int(m.group(5))
        if not (0 <= hh <= 23 and 0 <= mi <= 59):
            return f"`{field_name}` time '{m.group(4)}:{m.group(5)}' is not a real time (HH 00-23, MM 00-59)"
    return None


def _umu(s: str) -> str:
    """Transliterate German umlauts so 'März' matches 'maerz'."""
    return s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


def _date_strings_in_title(title_lower: str, date_val: str) -> str | None:
    """Return the redundant date rendering found in *title*, or None.

    The event date already lives in the timeline path, so any full-date
    rendering in the title (numeric, ISO, or written-out German/English
    month) is redundant. A bare year alone does not count.
    """
    try:
        y, mo, d = date_val.split("-")
        dd, mm = str(int(d)), str(int(mo))
    except Exception:
        return None
    title_folded = _umu(title_lower)
    de_month = _MONTHS_DE[int(mo) - 1]
    en_month = _MONTHS_EN[int(mo) - 1]
    candidates = [
        f"{dd}.{mm}.{y}", f"{d}.{mo}.{y}",          # 21.10.2022
        f"{dd}.{mm}.{y[2:]}", f"{d}.{mo}.{y[2:]}",  # 21.10.22
        f"{y}-{mo}-{d}", f"{y}-{mm}-{dd}",          # 2022-10-21
        f"{dd}. {de_month} {y}", f"{d}. {de_month} {y}",
        f"{dd}. {en_month} {y}", f"{d}. {en_month} {y}",
        f"{dd}. {de_month}", f"{d}. {de_month}",   # 21. Oktober
        f"{dd}. {en_month}", f"{d}. {en_month}",
    ]
    for cand in candidates:
        if cand in title_folded:
            return cand
    return None


def _check_title_content(fm: dict, date_part: str | None, time_part: str | None = None) -> list[str]:
    """Title hints that keep same-day summaries distinguishable."""
    hints: list[str] = []
    title = fm.get("title")
    if not isinstance(title, str) or not title.strip():
        return hints
    title_lower = title.strip().lower()
    if date_part is not None:
        found = _date_strings_in_title(title_lower, date_part)
        if found:
            hints.append(f"title contains the event date ('{found}'), which already lives in the timeline path — drop it from the title")
    if time_part is not None:
        hh, mi = time_part.split(":")
        for pat, label in ((rf'(?<!\d){hh}:{mi}(?!\d)', f"{hh}:{mi}"),
                           (rf'(?<!\d){hh}{mi}(?!\d)', f"{hh}{mi}")):
            if re.search(pat, title_lower):
                hints.append(f"title contains the event time ('{label}'), which already lives in the filename — drop it from the title")
                break
    return hints


def _check_title_value(title) -> list[str]:
    problems = []
    if not isinstance(title, str) or not title.strip():
        return ["`title` is missing or empty"]
    t = title.strip()
    for ch in t:
        if ch in _FS_RESERVED or ord(ch) < 32:
            problems.append(f"`title` contains filesystem-unsafe character {ch!r} — keep titles filename-safe")
            break
    if t != t.rstrip(". "):
        problems.append("`title` has a trailing dot or space — not filesystem-safe")
    if len(t) > 150:
        problems.append(f"`title` is {len(t)} chars — keep it under 150 so it fits in a filename")
    return problems


def _check_list_field(fm: dict, field: str) -> list[str]:
    problems = []
    if field not in fm:
        return [f"missing required field `{field}`"]
    value = fm[field]
    if value is None:
        return [f"`{field}` is null — use an empty list `[]` when there is nothing to extract"]
    if isinstance(value, str):
        return [f"`{field}` must be a YAML list, not a string (got '{value}')"]
    if not isinstance(value, list):
        return [f"`{field}` must be a YAML list, got {type(value).__name__}"]
    for entry in value:
        if not isinstance(entry, str) or not entry.strip():
            problems.append(f"`{field}` contains an empty/non-string entry — drop it or use `[]`")
        elif entry.strip().lower() in _PLACEHOLDER_VALUES:
            problems.append(f"`{field}` contains placeholder value '{entry}' — use `[]` instead of inventing metadata")
    return problems


def _normalize_source_target(entry: str) -> str:
    target = entry.strip()
    if target.startswith("[[") and target.endswith("]]"):
        target = target[2:-2]
    # alias [[target|label]] -> target
    target = target.split("|", 1)[0].strip()
    # anchor [[page#section]] / [[page^block]] -> page
    for sep in ("#", "^"):
        if sep in target:
            target = target.split(sep, 1)[0].strip()
    # URL-decode (vault has umlauts, links may be percent-encoded)
    try:
        import urllib.parse
        target = urllib.parse.unquote(target)
    except Exception:
        pass
    return target.strip().strip("./")


def _normalize_raw_ref(raw_path: str) -> str:
    ref = (raw_path or "").strip().replace("\\", "/").strip("./")
    if ref.endswith(".md"):
        return ref
    return ref


def _check_sources(fm: dict, raw_path: str) -> list[str]:
    problems = []
    if "source" in fm and "sources" not in fm:
        return ["singular `source:` field is invalid — rename it to plural `sources:` (list of wikilinks)"]
    if "sources" not in fm:
        return ["missing required field `sources`"]
    sources = fm["sources"]
    if isinstance(sources, str):
        return ["`sources` must be a list, not a string — use `sources: [\"[[...]]\"]`"]
    if not isinstance(sources, list) or not sources:
        return ["`sources` must be a non-empty list pointing at the original raw file"]
    rawnorm = _normalize_raw_ref(raw_path)
    rawbase = raw_path.strip().replace("\\", "/").split("/")[-1]
    if rawbase.endswith(".md"):
        rawbase_noext = rawbase[:-3]
    else:
        rawbase_noext = rawbase
    found_raw = False
    for entry in sources:
        if not isinstance(entry, str) or not entry.strip():
            problems.append("`sources` contains an empty entry")
            continue
        e = entry.strip()
        if e.startswith("http://") or e.startswith("https://"):
            continue
        if not (e.startswith("[[") and e.endswith("]]")):
            problems.append(f"`sources` entry '{e}' is not a wikilink — use `[[{e}]]` or a URL")
            continue
        target = _normalize_source_target(e)
        target_nodot = target[:-3] if target.endswith(".md") else target
        # Compare path and extension-less path; the explicit parens avoid the
        # `A or B if cond else C` precedence trap (which happened to be right
        # here but reads as something else entirely).
        if target == rawnorm or (rawnorm.endswith(".md") and target_nodot == rawnorm[:-3]):
            found_raw = True
        elif target.split("/")[-1] in (rawbase, rawbase_noext):
            found_raw = True
    if not found_raw:
        problems.append(f"`sources` does not reference the original raw file '{rawnorm}' — link the raw source, not another summary")
    return problems


def _contains(haystack_lower: str, needle: str) -> bool:
    return needle.lower() in haystack_lower


def _check_grounding_list(values: list, raw_lower: str, field: str, strict: bool) -> list[str]:
    """Check that extracted metadata actually occurs in the raw source.

    UIDs are matched verbatim (an identifier missing from the source is
    almost certainly invented). Names (persons, companies, groups, products) are
    matched case-insensitively; a partial token-only match is reported as
    a softer hint so the reviewer can verify spelling instead of deleting.
    """
    hints: list[str] = []
    for entry in values:
        if not isinstance(entry, str) or not entry.strip():
            continue
        needle = entry.strip()
        if strict:
            if needle in raw_lower or needle.lower() in raw_lower:
                continue
            hints.append(f"`{field}` entry '{needle}' not found verbatim in the raw file — likely invented, remove or verify")
        else:
            if _contains(raw_lower, needle):
                continue
            tokens = [t for t in re.split(r'[^A-Za-z0-9äöüÄÖÜß]+', needle) if len(t) >= 3]
            if tokens and any(_contains(raw_lower, t) for t in tokens):
                hints.append(f"`{field}` entry '{needle}' not found verbatim in raw (only partial token match) — verify spelling")
            else:
                hints.append(f"`{field}` entry '{needle}' not found in the raw file — double check")
    return hints


def validate_summary(summary_text: str, raw_text: str, raw_path: str, today_str: str | None = None) -> tuple[list[str], dict | None, str]:
    """Run every check that can be done in code (no LLM needed).

    Returns (lint_results, frontmatter_or_None, body). ``lint_results`` is a
    flat list of human-readable hint strings for the double-check reviewer —
    there is no error/warning split; ``process_summary`` only treats an
    unwritable file (no usable title/date) as a failure.
    """
    hints: list[str] = []
    today_str = today_str or datetime.datetime.now().date().isoformat()

    if not summary_text or not summary_text.strip():
        return ["LLM returned empty content — nothing to validate"], None, ""

    text = summary_text.strip()
    if text.startswith("```"):
        hints.append("output is wrapped in code fences — strip the ``` markers and return the raw file content only")
        # try to recover: drop the first/last fence lines for further checks
        lines = text.split("\n")
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    fm, body, _fm_raw, fm_error = _parse_frontmatter(text)
    if fm_error:
        return [fm_error], None, body

    # type
    if fm.get("type") != "summary":
        hints.append(f"`type` must be exactly `summary`, got {fm.get('type')!r}")

    # title
    if "title" not in fm:
        hints.append("missing required field `title`")
    else:
        hints.extend(_check_title_value(fm["title"]))
    date_part, time_part = _split_datetime_value(fm.get("date")) if isinstance(fm, dict) else (None, None)
    if isinstance(fm, dict):
        hints.extend(_check_title_content(fm, date_part, time_part))
        if date_part is not None and time_part is None and _check_date_value(fm.get("date"), "date") is None:
            hints.append("`date` has no receive time — use `YYYY-MM-DD HH:MM` (many mails arrive per day; the time becomes the `YYYYMMDD-HHMM` filename prefix)")

    # dates (`date` may carry a receive time; `updated` stays date-only)
    for field in ("date", "updated"):
        if field not in fm:
            hints.append(f"missing required field `{field}`")
        else:
            problem = _check_date_value(fm[field], field)
            if problem:
                hints.append(problem)
    if "updated" in fm:
        upd_part, _ = _split_datetime_value(fm["updated"])
        if upd_part is not None and upd_part != today_str:
            hints.append(f"`updated` must be today's date ({today_str}), got '{upd_part}'")

    # list fields
    for field in LIST_FIELDS:
        hints.extend(_check_list_field(fm, field))

    # groups: optional (legacy summaries lack it) — type-check only when present
    if "groups" in fm:
        hints.extend(_check_list_field(fm, "groups"))

    # sources (needs raw_path)
    hints.extend(_check_sources(fm, raw_path))

    # author: optional — only type-check when present
    if "author" in fm and fm["author"] is not None and not isinstance(fm["author"], str):
        hints.append(f"`author` must be a string, got {type(fm['author']).__name__}")

    # body substance
    body_stripped = body.strip()
    if len(body_stripped) < 50:
        hints.append("body is empty or too short (<50 chars) — summarize key claims, numbers, and why it matters")
    has_bullets = any(
        line.lstrip().startswith(("- ", "* ", "+ "))
        or re.match(r'^\s*\d+[.)]\s', line)
        for line in body_stripped.split("\n")
    )
    if not has_bullets:
        hints.append("body has no bullet points — use bullets by default for easy scanning")

    # grounding against the raw source
    raw_lower = (raw_text or "").lower()
    if raw_text and raw_text.strip():
        for field, strict in (("uids", True), ("persons", False), ("companies", False), ("groups", False), ("products", False)):
            values = fm.get(field)
            if isinstance(values, list) and values:
                hints.extend(_check_grounding_list(values, raw_lower, field, strict))
        # verbatim-copy guard: the summary must not just reproduce the source
        if body_stripped and body_stripped == raw_text.strip():
            hints.append("body reproduces the raw source verbatim — write a concise summary instead")
        elif len(raw_text.strip()) > 500 and len(body_stripped) > len(raw_text.strip()) * 0.9:
            hints.append("body is nearly as long as the raw source — keep the summary concise")
    else:
        hints.append("raw file is empty or unreadable — grounding checks skipped")

    return hints, fm, body


def sanitize_title_filename(title: str, max_len: int = 120) -> str:
    """Map a summary title to a filesystem-safe ``.md`` stem."""
    name = (title or "").strip()
    name = re.sub(r'[\s_]+', '_', name)
    name = "".join("_" if (ch in _FS_RESERVED or ord(ch) < 32) else ch for ch in name)
    name = re.sub(r'__+', '_', name).strip("._- ")
    if not name:
        name = "untitled"
    if len(name) > max_len:
        name = name[:max_len].rstrip("._- ") or "untitled"
    return name


# ---------------------------------------------------------------------------
# Session-bound helpers
# ---------------------------------------------------------------------------

def _workspace_root(_session) -> Path | None:
    try:
        ws = getattr(_session, "workspace", None)
        if ws is not None and getattr(ws, "path", None):
            return Path(ws.path)
    except Exception:
        pass
    try:
        version = _session.get_version_model()
        ws = getattr(version, "workspace", None)
        if ws is not None and getattr(ws, "path", None):
            return Path(ws.path)
    except Exception:
        pass
    return None


def _read_raw_text(_session, raw_path: str) -> tuple[str | None, str]:
    """Read the raw file, resolving vault-relative paths via the workspace.

    Returns (text_or_None, vault_relative_ref).
    """
    p = Path(raw_path)
    candidates: list[Path] = []
    if p.is_absolute():
        candidates.append(p)
    else:
        root = _workspace_root(_session)
        if root is not None:
            candidates.append(root / p)
        candidates.append(p)
    for cand in candidates:
        try:
            if cand.is_file():
                return cand.read_text(encoding="utf-8"), cand.as_posix()
        except Exception:
            continue
    # last resort: legacy behaviour (cwd-relative open)
    try:
        with open(raw_path, "r", encoding="utf-8") as f:
            return f.read(), raw_path
    except Exception:
        return None, raw_path


def _vault_rel(_session, absolute: Path) -> str:
    root = _workspace_root(_session)
    try:
        if root is not None:
            return absolute.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        pass
    return absolute.as_posix()


def _fallback_receive_hhmm(raw_path: str, raw_abs: str | None) -> str:
    """Best-effort receive time when frontmatter `date` carries no time.

    1. Raw archive folder timestamp (``.../YYYYMMDD-HHMM__sender__...``).
    2. Raw file mtime (export time ≈ receive time for frequent syncs).
    3. ``"0000"``.
    """
    m = _RAW_TS_RE.search(raw_path or "")
    if m:
        hh, mi = m.group(4), m.group(5)
        if 0 <= int(hh) <= 23 and 0 <= int(mi) <= 59:
            return f"{hh}{mi}"
    if raw_abs:
        try:
            return datetime.datetime.fromtimestamp(Path(raw_abs).stat().st_mtime).strftime("%H%M")
        except Exception:
            pass
    return "0000"


def _embed_for_prompt(_session, label: str, path: str) -> list:
    # `path` is vault-relative: resolve it against the workspace root the same
    # way every other file access in this module does. A plain cwd-relative
    # open would miss the file and embed "<unreadable>".
    content, _ = _read_raw_text(_session, path)
    if content is None:
        return [
            {"type": MessagePartType.MESSAGE,  "content_type": MessageContentType.TEXT, "content": f"# {label} ({path}): <unreadable>\n"},
        ]

    if len(content) > _MAX_EMBED_CHARS:
        return [
            {"type": MessagePartType.MESSAGE,  "content_type": MessageContentType.TEXT, "content": f"# {label} ({path}) truncated to {_MAX_EMBED_CHARS} chars:\n"},
            {"type": MessagePartType.MESSAGE,  "content_type": MessageContentType.TEXT, "content": content[:_MAX_EMBED_CHARS]},
            {"type": MessagePartType.MESSAGE,  "content_type": MessageContentType.TEXT, "content": "\n[... truncated ...]\n"},
        ]
    return [
        {"type": MessagePartType.MESSAGE,  "content_type": MessageContentType.TEXT, "content": f"# CONTENT OF {label} ({path}):\n"},
        {"type": MessagePartType.MESSAGE,  "content_type": MessageContentType.TEXT, "content": content},
    ]

 


def update_timeline(_session: Session, limit: int = 1):
    task = _session.get_task("find_unlinked_raw")
    if task is None:
        return False, {"status": "error", "message": "task 'find_unlinked_raw' is not available"}
    success, data = task.call(limit=limit)
    if not success:
        return False, data
    llm_query_tool = _session.get_tool("llm_query")
    if llm_query_tool is None:
        return False, {"status": "error", "message": "tool 'llm_query' is not available"}
    process_task = _session.get_task("process_summary")
    if process_task is None:
        return False, {"status": "error", "message": "task 'process_summary' is not available"}
    results = []
    for item in (data or {}).get("items", []):
        path = item["file"]
        raw_text, _ = _read_raw_text(_session, path)
        if raw_text is None:
            continue
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        summary_result = llm_query_tool.delay(messages=[
            {"role": "user", "content": SUMMARY_FORMAT_REFERENCE},
            {"role": "user", "content": f"It is now {now}.\nYOUR TASK: Create a concise, factual summary of the provided source material.\n"},
            {"role": "user", "content": f"# SOURCE PATH: {path}\n# CONTENT:\n"},
            {"role": "user", "content": raw_text},
        ], reasoning_effort=ReasoningEffort.NONE.value)
        r = process_task.delay(raw_path=path, summary_result=summary_result)

        results.append(r)
    return True, {"status": "success", "results": results}


def process_summary(_session, raw_path, summary_result, write: bool = True):
    """Validate an LLM-generated timeline summary, write it, and queue a double-check.
    Code-checkable rules (no LLM needed) are collected as flat
    ``lint_results`` hint strings: frontmatter presence/validity, required
    fields, ``type == summary``, filesystem-safe title, real event
    ``date`` + receive time (``YYYY-MM-DD HH:MM``) and today's ``updated``,
    list-typed tags/persons/companies/groups/products/uids, plural ``sources``
    referencing *raw_path*, body substance, and grounding — every ``uid``
    verbatim in the raw file, every person/company/product at least mentioned.

    The only failure condition is "the file could not be written": no
    usable summary content, an unreadable raw file, or no usable
    title/date to derive the timeline path from. Anything else is written
    and reported as success together with its lint hints.

    On success the ``double_check_summary`` task is dispatched with
    ``raw_path``, ``summary_path`` and ``lint_results`` so a reviewer
    session can fix the file in place when a hint is valid.

    Returns (False, {status, raw_path, lint_results, message}) when the
    file could not be written; (True, {status, raw_path, summary_path,
    lint_results, message}) after the file is written.
    """
    summary_text = _extract_summary_text(summary_result)
    if summary_text is None:
        return False, {
            "status": "error",
            "raw_path": raw_path,
            "lint_results": ["LLM result contains no usable `content` text — nothing was written"],
            "message": "process_summary: no summary content in llm result, file could not be written",
        }

    raw_text, raw_abs = _read_raw_text(_session, raw_path)
    if raw_text is None:
        return False, {
            "status": "error",
            "raw_path": raw_path,
            "lint_results": [f"raw file not found or unreadable: {raw_path}"],
            "message": "process_summary: raw file unreadable, file could not be written",
        }

    today_str = datetime.datetime.now().date().isoformat()
    lint_results, fm, _body = validate_summary(summary_text, raw_text, raw_path, today_str)

    # The only blockers: without a usable title + event date there is no
    # timeline path to write to. Everything else is a hint for the reviewer.
    blockers: list[str] = []
    title = fm.get("title") if isinstance(fm, dict) else None
    date_part, time_part = _split_datetime_value(fm.get("date")) if isinstance(fm, dict) else (None, None)
    if not isinstance(title, str) or not title.strip():
        blockers.append("no usable `title` in frontmatter")
    if date_part is None:
        blockers.append(f"no usable event `date` in frontmatter (got {fm.get('date')!r})" if isinstance(fm, dict) else "no usable event `date` in frontmatter")
    if blockers:
        return False, {
            "status": "error",
            "raw_path": raw_path,
            "lint_results": lint_results,
            "message": "process_summary: file could not be written — " + "; ".join(blockers),
        }

    if not write:
        return True, {
            "status": "success",
            "raw_path": raw_path,
            "summary_path": None,
            "lint_results": lint_results,
            "message": "process_summary: checks ran (write=False, file not written, no double-check dispatched)",
        }

    # Derive timeline path from the event date + title. The filename carries
    # a YYYYMMDD-HHMM prefix so same-day summaries sort chronologically:
    # timeline/YYYY/MM/DD/YYYYMMDD-HHMM_<Title>.md
    root = _workspace_root(_session)
    if root is None:
        return False, {
            "status": "error",
            "raw_path": raw_path,
            "lint_results": lint_results,
            "message": "process_summary: cannot resolve workspace root, file could not be written",
        }
    y, mo, d = date_part.split("-")
    hhmm = time_part.replace(":", "") if time_part else _fallback_receive_hhmm(raw_path, raw_abs)
    stem = sanitize_title_filename(title)
    prefix = f"{y}{mo}{d}-{hhmm}"
    target_dir = root / "timeline" / y / mo / d
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, {
            "status": "error",
            "raw_path": raw_path,
            "lint_results": lint_results,
            "message": f"process_summary: cannot create timeline dir {target_dir}: {e}",
        }
    target = target_dir / f"{prefix}_{stem}.md"
    counter = 1
    while target.exists():
        try:
            if target.read_text(encoding="utf-8") == summary_text:
                break
        except Exception:
            pass
        counter += 1
        target = target_dir / f"{prefix}_{stem}_{counter}.md"
    try:
        text_out = summary_text if summary_text.endswith("\n") else summary_text + "\n"
        target.write_text(text_out, encoding="utf-8")
    except Exception as e:
        return False, {
            "status": "error",
            "raw_path": raw_path,
            "lint_results": lint_results,
            "message": f"process_summary: cannot write summary file {target}: {e}",
        }

    summary_path = _vault_rel(_session, target)
    double_check = "not dispatched"
    check_task = _session.get_task("double_check_summary") if hasattr(_session, "get_task") else None
    check_task_result = None
    if check_task is not None:
        check_task_result = check_task.delay(raw_path=raw_path, summary_path=summary_path, lint_results=lint_results)
        double_check = "dispatched"

    return True, {
        "status": "success",
        "raw_path": raw_path,
        "summary_path": summary_path,
        "lint_results": lint_results,
        "double_check_result": check_task_result,
        "message": f"process_summary: wrote {summary_path} ({len(lint_results)} lint hints, double-check {double_check})",
    }



def double_check_summary(_session, raw_path, summary_path, lint_results=None):
    """Spawn a baseagent reviewer session for a written summary.

    Starts a fresh ``baseagent`` session (which carries filesystem-read /
    filesystem-write tools) on the same workspace, preloads it with the raw
    source content, the summary content and the code-lint hints — so it
    needs no read tool calls to understand the task — and asks it to fix
    the summary file in place wherever a hint (or anything else it spots)
    is valid.

    ``baseagent`` has ``visibility: internal``, so it is not resolvable via
    the subagent allowlist — it is looked up directly by name, the same way
    runtime code instantiates the ``approval_decider`` agent. Inherited
    narrowing session settings (disallowed lists, call allowlist) are reset
    so the child gets the full baseagent envelope.

    Returns (True, {status, session_pk, summary_path, message}) once the
    reviewer session is started. The reviewer works asynchronously; the
    file fix itself is the delivery, no result is waited for here.
    """
    from time import time

    from server.models.agents.agent import AgentModel

    from server.models.sessions.session_version import SessionVersionModel

    lint_results = list(lint_results or [])

    raw_text, _ = _read_raw_text(_session, raw_path)
    if raw_text is None:
        return False, {
            "status": "error",
            "raw_path": raw_path,
            "summary_path": summary_path,
            "message": f"double_check_summary: raw file unreadable: {raw_path}",
        }
    summary_text, _ = _read_raw_text(_session, summary_path)
    if summary_text is None:
        return False, {
            "status": "error",
            "raw_path": raw_path,
            "summary_path": summary_path,
            "message": f"double_check_summary: summary file unreadable: {summary_path}",
        }

    subagent_version = None
    try:
        subagent_version = _session.get_subagent("baseagent")
    except Exception:
        subagent_version = None
    if subagent_version is None:
        # baseagent is visibility: internal → excluded from the subagent
        # allowlist by design; resolve directly like approval_decider.
        model = AgentModel.objects.filter(name="baseagent").first()
        if model is None:
            return False, {
                "status": "error",
                "raw_path": raw_path,
                "summary_path": summary_path,
                "message": "double_check_summary: agent 'baseagent' not found",
            }
        subagent_version = model.get_runtime().get_version_model()

    parent_sv = _session.get_version_model()
    child_sv = subagent_version.get_or_create_session(
        name=f"p{_session.model.pk}:baseagent:{int(time())}",
        description=f"Double-check {summary_path} against {raw_path}",
        workspace=_session.workspace,
        parent_session_version=parent_sv,
        session_type=SessionType.SUBTASK_DELEGATE,
    )
    # Reset narrowing overlays inherited from the parent session so the
    # child gets the full baseagent envelope (model/key prefs are kept).
    if parent_sv is not None and parent_sv.session_settings is not None:
        child_settings = subagent_version.clone_settings(
            parent_sv.session_settings,
            disallowedToolNames=[],
            disallowedTaskNames=[],
            disallowedCommandNames=[],
            tool_call_allowlist=None,
            reasoning_effort=ReasoningEffort.MEDIUM,
            max_turns=10,
        )
        child_sv.session_settings = child_settings
        SessionVersionModel.objects.filter(pk=child_sv.pk).update(session_settings=child_settings)
    child_session = Session(session_model=child_sv.session, pinned_session_version=child_sv)

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    working_dir = child_session.workspace.path if child_session.workspace else "unknown"

    parts = [
        {
            "type": MessagePartType.MESSAGE,
            "content_type": MessageContentType.TEXT,
            "content": SUMMARY_FORMAT_REFERENCE,
        },
        {
            "type": MessagePartType.MESSAGE,
            "content_type": MessageContentType.TEXT,
            "content": (
                f"You are running as a subtask for another agent. "
                f"When your work is complete, finish by invoking the final_result tool with a one sentence summary of your work as its content argument. "
                f"Do not return your result as plain text. Do not output explanation or results as normal text for users, you are run as a subagent, nobody will read that.\n" 
                f"Your working dir is the vault root; paths below are vault-relative. Never modify anything under `raw/`.\n"
                f"It is now {now}, your working dir is '{working_dir}'.\n"
                f"Your task: Double-check summary against its raw source.\n"
                f"Fix the summary file in place if you spot wrong dates, invented facts, missing key claims, "
                f"broken wikilinks, invalid or missing frontmatter, or other quality problems in the summary. Use multiedit to do multiple edits at once to save on roundtrips. Rename the file if necessary.\n"
            ),
        },
    ]
    if lint_results:
        parts.append(        {
            "type": MessagePartType.MESSAGE, "content_type": MessageContentType.TEXT,
            "content": "A linter did run static checks on the summary, here are the results:\n",
        })
        parts.append(        {
            "type": MessagePartType.MESSAGE, "content_type": MessageContentType.TEXT,
            "content": "\n".join(f"- {hint}" for hint in lint_results),
        })

   
    parts.extend(_embed_for_prompt(_session, "RAW SOURCE FILE", raw_path))
    parts.extend(_embed_for_prompt(_session, "SUMMARY FILE", summary_path))
        
    summary_check_result = child_session.add_user_message(parts=parts)

    return True, {
        "status": "success",
        "raw_path": raw_path,
        "summary_path": summary_path,
        "message": summary_check_result,
    }

