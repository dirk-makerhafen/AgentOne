"""Search your own session history (full message store, not just LLM context).

Your LLM context only holds the most recent turns (capped by
``max_history_messages`` and cut off at the latest compaction boundary). This
tool searches everything still in the database: older turns, compacted-away
turns, hidden/INFO messages (on request), and tool-call payloads — returning
short previews so history is never bulk-injected into context. Use
``inspect_history_item`` to drill into a single hit.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from runtime.session.session import Session
from server.models.enums.message_enums import MessagePartType, MessageRole
from server.models.message import Message

PREVIEW_CHARS = 500
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def _descendant_ids(session: Session) -> set[int]:
    """Own session pk plus all transitive child-session pks (BFS, cycle-safe)."""
    from server.models.sessions.session import SessionModel

    seen = {session.model.pk}
    frontier = [session.model.pk]
    while frontier:
        children = list(
            SessionModel.objects.filter(parent_session_id__in=frontier).values_list("pk", flat=True)
        )
        new = [pk for pk in children if pk not in seen]
        if not new:
            break
        seen.update(new)
        frontier = new
    return seen


def _compaction_cutoffs(session_pks: set[int]) -> dict[int, Any]:
    """Newest COMPACTION-part message timestamp per session (None if never)."""
    cutoffs: dict[int, Any] = {}
    for pk in session_pks:
        cutoffs[pk] = (
            Message.objects.filter(session_id=pk, parts__type=MessagePartType.COMPACTION)
            .order_by("-created_at")
            .values_list("created_at", flat=True)
            .first()
        )
    return cutoffs


def _preview(raw: Any, max_chars: int) -> tuple[str, bool]:
    try:
        text = raw if isinstance(raw, str) else json.dumps(raw, default=str, ensure_ascii=False) if raw is not None else ""
    except Exception:
        text = ""
    if len(text) > max_chars:
        return text[:max_chars] + "…[truncated]", True
    return text, False


def _str(value: Any) -> str:
    """Plain-str rendering of enum members / raw values (JSON-safe)."""
    return str(getattr(value, "value", value))


def _parse_date(value: Any, name: str) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        raise ValueError(f"{name} must be ISO-8601 (got {value!r})")


def search_own_history(
    _session: Session,
    text: str | None = None,
    role: str | None = None,
    part_type: str | None = None,
    tool_call_name: str | None = None,
    task_name: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    include_hidden: bool = False,
    include_compacted: bool = True,
    include_subsessions: bool = False,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    order: str = "newest",
) -> dict[str, Any]:
    """Search your own session history.

    Args:
        text: Full-text substring matched against message part bodies.
        role: Filter by message role: user, assistant, system, tool,
            developer, info.
        part_type: Filter by part type: MESSAGE, REASONING, TOOLCALL,
            COMPACTION.
        tool_call_name: Only messages with a tool-call part for this tool
            (substring match on the task definition name).
        task_name: Alias of tool_call_name (covers non-tool tasks too).
        date_from/date_to: ISO-8601 bounds on message creation time.
        include_hidden: Include messages hidden from LLM context
            (hide_from_context / INFO). Default False.
        include_compacted: Include turns older than the latest compaction
            boundary (flagged beyond_compaction). Default True.
        include_subsessions: Also search transitive child subsessions.
            Default False (own session only).
        limit: Max hits (1-100, default 20). offset: Skip first N hits.
        order: "newest" (default) or "oldest".

    Returns:
        ``{"results": [...], "total_count": int, "has_more": bool,
        "next_offset": int}`` — each hit carries a ~500-char preview, never
        full bodies. On error: ``{"error": ...}``.
    """
    try:
        scope = _descendant_ids(_session) if include_subsessions else {_session.model.pk}
        qs = Message.objects.filter(session_id__in=scope)

        if not include_hidden:
            qs = qs.exclude(hide_from_context=True).exclude(role=MessageRole.INFO)

        if role is not None:
            try:
                qs = qs.filter(role=MessageRole[role.upper()])
            except KeyError:
                return {"error": f"Unknown role {role!r}. Use user/assistant/system/tool/developer/info."}

        part_filter: dict[str, Any] = {}
        if part_type is not None:
            try:
                MessagePartType[part_type.upper()]
            except KeyError:
                return {"error": f"Unknown part_type {part_type!r}. Use MESSAGE/REASONING/TOOLCALL/COMPACTION."}
            part_filter["parts__type"] = MessagePartType[part_type.upper()]

        tool_name = tool_call_name or task_name
        if tool_name:
            part_filter["parts__tool_call__task_definition__name__icontains"] = tool_name

        if text:
            part_filter["parts__content__content__icontains"] = text

        if part_filter:
            qs = qs.filter(**part_filter)

        try:
            dt_from = _parse_date(date_from, "date_from")
            dt_to = _parse_date(date_to, "date_to")
        except ValueError as exc:
            return {"error": str(exc)}
        if dt_from is not None:
            qs = qs.filter(created_at__gte=dt_from)
        if dt_to is not None:
            qs = qs.filter(created_at__lte=dt_to)

        if order == "oldest":
            qs = qs.order_by("created_at", "pk")
        elif order == "newest":
            qs = qs.order_by("-created_at", "-pk")
        else:
            return {"error": f"Unknown order {order!r}. Use newest/oldest."}

        qs = qs.distinct()
        total = qs.count()
        limit = max(1, min(int(limit), MAX_LIMIT))
        offset = max(0, int(offset))
        messages = list(
            qs[offset : offset + limit].prefetch_related(
                "parts__tool_call__task_definition", "parts__content", "parts__template_data"
            )
        )

        cutoffs = _compaction_cutoffs(scope) if include_compacted else {}
        agent_by_session: dict[int, str] = {}
        if include_subsessions:
            from server.models.sessions.session import SessionModel

            for s in SessionModel.objects.filter(pk__in=scope).select_related(
                "latest_session_version__agent"
            ):
                lsv = s.latest_session_version
                agent_by_session[s.pk] = lsv.agent.name if lsv and lsv.agent else "?"

        want_type = part_filter.get("parts__type")
        results = []
        for msg in messages:
            cutoff = cutoffs.get(msg.session_id)
            beyond = bool(include_compacted and cutoff and msg.created_at < cutoff)
            for part in msg.parts.all():
                # Pick the first part satisfying the same criteria the
                # DB-level filter used (DB join matches ANY part; without
                # this we could preview a non-matching part).
                if want_type is not None and part.type != want_type:
                    continue
                try:
                    rendered = part.to_string()
                except Exception as exc:
                    rendered = f"[unrenderable part: {exc}]"
                rendered_str = rendered if isinstance(rendered, str) else _preview(rendered, 10**9)[0]
                if text and text.lower() not in rendered_str.lower():
                    continue
                text_preview, truncated = _preview(rendered, PREVIEW_CHARS)
                hit: dict[str, Any] = {
                    "message_pk": msg.pk,
                    "role": _str(msg.role),
                    "created_at": msg.created_at.isoformat() if msg.created_at else "",
                    "part_type": _str(part.type),
                    "preview": text_preview,
                    "preview_truncated": truncated,
                    "hidden_from_llm": bool(msg.hide_from_context or _str(msg.role) == "info"),
                    "is_compaction_boundary": part.type == MessagePartType.COMPACTION,
                    "beyond_compaction": beyond,
                }
                if include_subsessions:
                    hit["session_pk"] = msg.session_id
                    hit["agent"] = agent_by_session.get(msg.session_id, "?")
                if part.tool_call_id:
                    tc = part.tool_call
                    hit["tool_call_pk"] = tc.pk
                    try:
                        hit["tool_call_name"] = tc.task_definition.name
                    except Exception:
                        hit["tool_call_name"] = ""
                    hit["tool_call_status"] = _str(tc.status)
                results.append(hit)
                break  # first matching part per message keeps payloads small

        end = offset + len(messages)
        return {
            "results": results,
            "total_count": total,
            "has_more": end < total,
            "next_offset": end,
        }
    except Exception as exc:
        return {"error": f"search_own_history failed: {exc}"}
