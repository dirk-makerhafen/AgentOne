"""Process an ingress.md work queue with wiki subsessions — async edition.

``process_ingress(session, ingress="<folder>/ingress.md", limit=2)`` is a
fast tool: it refreshes the queue, marks up to *limit* pending lines
``active`` in code, spawns one wiki SUBTASK_DELEGATE subsession per item,
and schedules one ``finalize_ingress_item`` task per item — then returns
immediately with what was dispatched. Nothing here waits: the worker is
free while children run on other workers.

Each finalize task carries the child's add_user_message ref as an argument,
so the scheduler delivers it only once that ref resolves (exactly like
``write_day_index``/``write_entity``); it then parses the child's
``ingress-result`` block and flips that one line (``- [x]`` + done-date, or
strips ``active`` on failure) in code. Consumers never edit the queue.

Subsessions run concurrently (up to *limit*), so briefs tell children to
re-read shared index files just before writing. Checkbox flips take an
exclusive file lock — concurrent finalizes cannot clobber each other.
"""

from __future__ import annotations

import datetime
import fcntl
import re
import sys
import time
from pathlib import Path
from uuid import uuid4

from runtime.session.session import Session

sys.path.insert(0, Path(__file__).resolve().parent.as_posix())
from update_ingress import (  # noqa: E402
    _format_queue_line,
    _parse_queue_line,
    refresh_ingress,
)
from update_timeline_daily import (  # noqa: E402
    _read_child_session_texts,
    _workspace_root,
)

ACTIVE_STALE_S = 1800
MAX_TURNS = 30
MAX_ITEM_CHARS = 20000
MAX_AGENTS_MD_CHARS = 12000
MAX_LIMIT = 10
RESULT_FENCE = "ingress-result"


# ---------------------------------------------------------------------------
# Pure helpers (testable without a session)
# ---------------------------------------------------------------------------

def _parse_result_block(text: str | None) -> tuple[str, list[str], str]:
    """(status, files, notes) from the ```ingress-result block.

    Missing/malformed block → ("failed", [], diagnostic). ``status`` is
    "success" only on an explicit `status: success` line.
    """
    if not text:
        return "failed", [], "empty result"
    m = re.search(r"```" + RESULT_FENCE + r"\s*\n(.*?)```", text, re.DOTALL)
    if not m:
        return "failed", [], "no ```ingress-result block in final message"
    body = m.group(1)
    status = "failed"
    files: list[str] = []
    notes = ""
    in_files = False
    note_lines: list[str] = []
    for raw in body.splitlines():
        line = raw.strip()
        if line.lower().startswith("status:"):
            status = "success" if "success" in line.lower() else "failed"
            in_files = False
        elif line.lower().startswith("files:"):
            in_files = True
        elif line.lower().startswith("notes:"):
            in_files = False
            note_lines.append(line.split(":", 1)[1].strip())
        elif in_files and line.startswith("- "):
            files.append(line[2:].strip())
        elif in_files and line:
            in_files = False
    notes = " ".join(n for n in note_lines if n)[:500]
    return status, [f for f in files if f], notes


def _truncate(text: str, max_chars: int) -> str:
    """Cap evidence text, marking truncation like the entity briefs."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[... truncated ...]"


def _build_item_brief(folder_rel: str, item_rel: str, item_text: str | None,
                      item_deleted: bool, agents_md: str | None) -> str:
    """Prompt for the one-item wiki subsession."""
    if agents_md:
        folder_block = f"## Folder instructions ({folder_rel}/AGENTS.md)\n\n{agents_md}\n"
    else:
        folder_block = (f"## Folder instructions\n\nNo AGENTS.md in {folder_rel}/ — do the "
                        f"obvious folder job for the item below and describe what you did.\n")
    if item_text is None:
        item_block = (f"## Your item\n\n- Path: {item_rel} (deleted — the source file is gone)\n\n"
                      f"The source vanished: check whether its entry still stands, then update "
                      f"or cancel that entry. Never silently keep it.\n")
    else:
        item_block = (f"## Your item\n\n- Path: {item_rel}\n\n```\n{item_text}\n```\n")
    return f"""Process ONE item from the {folder_rel}/ work queue.

{folder_block}
{item_block}
## Rules

- Do the folder's job for exactly this item and nothing else.
- You may read any vault files and write output files for this folder. Never
  touch anything under `raw/`, never edit or read `{folder_rel}/ingress.md` itself.
- Sibling items are processed concurrently: re-read any shared index file
  immediately before updating it, so parallel writes cannot clobber it.
- If the item is not actionable (advertising, duplicate, already recorded),
  say so in the notes instead of forcing output. 
- Finish by invoking the final_result tool directly with your result as its content argument containing EXACTLY one fenced block:

```ingress-result
status: success
files:
- <vault-relative path you created/updated, one per line>
notes: <one line: what you did, or why the item failed>
```

`status: failed` (with the reason in notes) when the item could not be
processed — it will be retried on a later pass.
"""


def _read_queue_entries(ingress_file: Path) -> list[tuple[str, bool, bool, dict, str]]:
    """(rel, done, deleted, meta, raw_line) for every queue body line."""
    try:
        text = ingress_file.read_text(encoding="utf-8")
    except Exception:
        return []
    entries = []
    for raw in text.split("---", 2)[-1].splitlines():
        rel, done, deleted, meta = _parse_queue_line(raw)
        if rel is None:
            continue
        entries.append((rel, done, deleted, meta, raw))
    return entries


def _set_line_state(ingress_file: Path, rel: str, done: bool,
                    active_ts: int | None, today: str) -> bool:
    """Rewrite one queue line's state in code; True when the line was found.

    Read-modify-write holds an exclusive lock, so concurrent finalize tasks
    cannot lose each other's flips.
    """
    try:
        with open(ingress_file, "r+", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                text = fh.read()
            except Exception:
                return False
            chunks = text.split("---", 2)
            if len(chunks) < 3:
                return False
            found = False
            out_lines = []
            for raw in chunks[2].splitlines():
                parsed_rel, _done, deleted, meta = _parse_queue_line(raw)
                if parsed_rel == rel and not found:
                    found = True
                    meta = dict(meta)
                    if active_ts is not None:
                        meta["active"] = active_ts
                    else:
                        meta.pop("active", None)
                    out_lines.append(_format_queue_line(rel, done, deleted, meta, today, None))
                else:
                    out_lines.append(raw)
            if not found:
                return False
            fh.seek(0)
            fh.write(chunks[0] + "---" + chunks[1] + "---" + "\n".join(out_lines)
                     + ("\n" if out_lines else ""))
            fh.truncate()
            return True
    except Exception:
        return False


def _now_ts() -> int:
    return int(time.time())


def _is_stale_active(meta: dict, now: int) -> bool:
    ts = meta.get("active")
    return isinstance(ts, int) and (now - ts) > ACTIVE_STALE_S


def finalize_item(root: Path, ingress_rel: str, item: str,
                  result_text: str | None) -> dict:
    """Converge one finished subsession: parse its result, flip its line.

    Pure file + parse operations (no session needed): success records
    `- [x]` with the done-date, anything else strips `active` and leaves
    the line pending for retry. Returns a result dict for the caller.
    """
    today = datetime.datetime.now().date().isoformat()
    ingress_file = root / ingress_rel
    status, files, notes = _parse_result_block(result_text)
    if status == "success":
        recorded = _set_line_state(ingress_file, item, True, None, today)
        return {"item": item, "ok": True, "files": files, "notes": notes,
                "recorded": recorded}
    _set_line_state(ingress_file, item, False, None, today)
    return {"item": item, "ok": False, "files": files,
            "notes": notes or "unparseable result"}


def dispatch_items(root: Path, ingress_rel: str, limit: int,
                   spawn_fn, schedule_fn) -> tuple[bool, dict]:
    """Refresh, mark active, spawn, schedule — all fast, nothing waits.

    ``spawn_fn(brief)`` → (ok, session_pk, ref_or_error);
    ``schedule_fn(ingress_rel, item, session_pk, ref)`` queues the finalize
    task (its ref arg makes the scheduler hold it until the child ends).
    Returns (ok, {spawned, spawn_failed, remaining}).
    """
    ingress_file = root / ingress_rel
    if not ingress_file.is_file():
        return False, {"status": "error", "message": f"ingress file not found: {ingress_rel}"}
    ok, refresh = refresh_ingress(root, ingress_rel)
    if not ok:
        return False, refresh
    try:
        folder_rel = ingress_file.parent.relative_to(root).as_posix()
    except Exception:
        folder_rel = ingress_file.parent.name
    if folder_rel == ".":
        folder_rel = ""
    agents_file = ingress_file.parent / "AGENTS.md"
    try:
        agents_md = agents_file.read_text(encoding="utf-8")
    except Exception:
        agents_md = None
    if agents_md and len(agents_md) > MAX_AGENTS_MD_CHARS:
        agents_md = agents_md[:MAX_AGENTS_MD_CHARS] + "\n\n[... truncated ...]"

    today = datetime.datetime.now().date().isoformat()
    now = _now_ts()
    pending: list[tuple[str, bool]] = []
    for rel, done, deleted, meta, _raw in _read_queue_entries(ingress_file):
        if done:
            continue
        if meta.get("active") is not None and not _is_stale_active(meta, now):
            continue  # owned by a recent pass; never double-process
        pending.append((rel, deleted))
    # Reclaim stale actives up front so the loop sees clean pending lines.
    for rel, _deleted in pending:
        _set_line_state(ingress_file, rel, False, None, today)

    spawned: list[dict] = []
    spawn_failed: list[dict] = []
    for rel, deleted in pending[:max(0, limit)]:
        item_file = root / rel
        if deleted or not item_file.is_file():
            item_text: str | None = None
        else:
            try:
                item_text = _truncate(item_file.read_text(encoding="utf-8"), MAX_ITEM_CHARS)
            except Exception:
                item_text = None
        brief = _build_item_brief(folder_rel or ".", rel, item_text, deleted or item_text is None,
                                  agents_md)
        _set_line_state(ingress_file, rel, False, now, today)
        try:
            sok, session_pk, ref = spawn_fn(brief)
        except Exception as e:
            sok, session_pk, ref = False, None, f"spawn error: {e}"
        if not sok:
            _set_line_state(ingress_file, rel, False, None, today)
            spawn_failed.append({"item": rel, "notes": ref or "spawn failed"})
            continue
        try:
            schedule_fn(ingress_rel, rel, session_pk, ref)
        except Exception as e:
            _set_line_state(ingress_file, rel, False, None, today)
            spawn_failed.append({"item": rel, "notes": f"schedule error: {e}"})
            continue
        spawned.append({"item": rel, "session_pk": session_pk})
    remaining = 0
    for rel, done, _deleted, _meta, _raw in _read_queue_entries(ingress_file):
        if not done:
            remaining += 1
    return True, {"status": "success", "ingress": ingress_rel,
                  "spawned": spawned, "spawn_failed": spawn_failed,
                  "remaining": remaining, "queue_head": refresh.get("head")}


# ---------------------------------------------------------------------------
# Session-bound runner (production wiki subsessions + finalize task)
# ---------------------------------------------------------------------------

def _spawn_wiki_item_session(_session, name: str, brief: str):
    """Spawn a wiki SUBTASK_DELEGATE session; returns (ok, session_pk, ref).

    Mirrors _spawn_baseagent but keeps the wiki envelope (full tools — the
    child writes folder files) with only max_turns capped. The returned ref
    is the add_user_message taskcall, resolvable by the scheduler exactly
    like an llm_query result ref.
    """
    from server.models.agents.agent import AgentModel
    from server.models.enums.message_enums import MessageContentType, MessagePartType
    from server.models.enums.session_enums import SessionType
    from server.models.sessions.session_version import SessionVersionModel

    subagent_version = None
    try:
        subagent_version = _session.get_subagent("wiki")
    except Exception:
        subagent_version = None
    if subagent_version is None:
        model = AgentModel.objects.filter(name="wiki").first()
        if model is None:
            return False, None, "agent 'wiki' not found"
        subagent_version = model.get_runtime().get_version_model()

    parent_sv = _session.get_version_model()
    child_sv = subagent_version.get_or_create_session(
        name=name,
        description="ingress item: " + " ".join(brief.split())[:80],
        workspace=_session.workspace,
        parent_session_version=parent_sv,
        session_type=SessionType.SUBTASK_DELEGATE,
    )
    if parent_sv is not None and parent_sv.session_settings is not None:
        child_settings = subagent_version.clone_settings(
            parent_sv.session_settings, max_turns=MAX_TURNS)
        child_sv.session_settings = child_settings
        SessionVersionModel.objects.filter(pk=child_sv.pk).update(session_settings=child_settings)
    child_session = Session(session_model=child_sv.session, pinned_session_version=child_sv)

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    working_dir = child_session.workspace.path if child_session.workspace else "unknown"
    parts = [
        {"type": MessagePartType.MESSAGE, "content_type": MessageContentType.TEXT,
         "content": "You are running as a subtask for another agent. "
            "When your work is complete, finish by invoking the final_result tool directly with your result as its content argument. "
            "Do not return your result as plain text only. Your task:\n"},
        {"type": MessagePartType.MESSAGE, "content_type": MessageContentType.TEXT, "content": brief},
        {"type": MessagePartType.MESSAGE, "content_type": MessageContentType.TEXT,
         "content": f"It is now {now}, your working dir is '{working_dir}'.\n"},
    ]
    try:
        ref = child_session.add_user_message(parts=parts)
    except Exception as e:
        return False, None, f"spawn failed: {e}"
    return True, child_sv.session.pk, ref


def finalize_ingress_item(_session, ingress, item, session_pk=None, child_result=None):
    """Converge one ingress subsession into its queue line (task, bound).

    ``child_result`` is the child's message ref: the scheduler delivers this
    task only once it resolves (child turn ended), so by the time this runs
    the result is readable. The ref's value is unused — the line is flipped
    from the session's final_result args / last assistant message, which is
    the reliable source. Returns (True, {item, ok, files, notes, recorded}).
    """
    root = _workspace_root(_session)
    if root is None:
        return False, {"status": "error", "item": item, "message": "cannot resolve workspace root"}
    rel = (ingress or "").strip().strip("/")
    if not (root / rel).is_file():
        return False, {"status": "error", "item": item, "message": f"ingress file not found: {ingress}"}
    final_text, hist_text = _read_child_session_texts(session_pk)
    outcome = finalize_item(root, rel, item, final_text or hist_text)
    outcome["status"] = "success" if outcome["ok"] else "retry"
    return True, outcome


def process_ingress(_session: Session, ingress: str, limit: int = 2) -> tuple[bool, dict]:
    """Dispatch an ingress work queue to wiki subsessions — read the module docstring first.

    You call this with a vault-relative queue path (`calendar/ingress.md`)
    and a *limit* (1-10, default 2). It refreshes the queue and immediately
    dispatches up to *limit* pending items: each runs in a fresh wiki
    subsession that receives the folder's `AGENTS.md` (when present) plus the
    one item, does the folder's job, and reports back — a finalize task then
    checks its line off in code. This tool does NOT wait: it returns
    `{spawned, remaining}` at once, freeing the worker while children run.
    Work `remaining` down across runs; items whose subsession failed stay
    queued for retry (see finalize task results for reasons). Never run two
    passes on the same file concurrently.
    """
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return False, {"status": "error", "message": f"bad limit {limit!r} — want 1-{MAX_LIMIT}"}
    if not 1 <= limit <= MAX_LIMIT:
        return False, {"status": "error", "message": f"bad limit {limit} — want 1-{MAX_LIMIT}"}
    root = _workspace_root(_session)
    if root is None:
        return False, {"status": "error", "message": "cannot resolve workspace root"}
    rel = ingress.strip().strip("/")
    candidate = root / rel
    if not candidate.is_file():
        return False, {"status": "error", "message": f"ingress file not found: {ingress}"}
    try:
        rel = candidate.relative_to(root).as_posix()
    except Exception:
        return False, {"status": "error", "message": f"ingress file outside workspace: {ingress}"}
    finalize_task = _session.get_task("finalize_ingress_item")
    if finalize_task is None:
        return False, {"status": "error", "message": "task 'finalize_ingress_item' is not available"}

    def spawn_fn(brief: str):
        name = f"p{_session.model.pk}:ingress:{uuid4().hex[:8]}"
        return _spawn_wiki_item_session(_session, name, brief)

    def schedule_fn(ingress_rel: str, item: str, session_pk, ref):
        return finalize_task.delay(ingress=ingress_rel, item=item,
                                   session_pk=session_pk, child_result=ref)

    return dispatch_items(root, rel, limit, spawn_fn, schedule_fn)
