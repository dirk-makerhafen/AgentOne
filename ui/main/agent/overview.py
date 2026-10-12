"""Agents dashboard — modern overview with rich statistics.

Shows a card grid of all agents with execution metrics, token usage,
and other useful stats at a glance.

Performance strategy:
  1. Batched queries — 6 aggregate queries (one per table) cover ALL agents
     in a single pass, instead of ~20 queries per agent.  Each batch query
     also tracks Max(pk) so we can initialize the incremental cache.
  2. Incremental cache — after the first full compute, we store the results
     plus the max PK seen per table per agent.  On subsequent renders we
     only count items with pk > stored_max and add the delta to the cached
     values.  This keeps the page fast even with large tables.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from django.db.models import Count, Avg, Q, Sum, F, Case, When, IntegerField, Max
from django.db.models.functions import Extract, Coalesce
from django.utils import timezone

from ui.lib.model_view import ModelView
from ui.main.rightpanel.assistant_chat import RightPanelAgentsOverview

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.main_view import MainView


# ─── Incremental cache (module-level, survives across renders) ──────────────
# Key: agent_pk (int)
# Value: {"stats": {field: value, ...}, "max_pks": {table: pk, ...}}
_agent_stats_cache: dict[int, dict] = {}


def invalidate_agent_cache(agent_pk: int | None = None) -> None:
    """Invalidate cached stats.  Pass None to clear all."""
    if agent_pk is None:
        _agent_stats_cache.clear()
    else:
        _agent_stats_cache.pop(agent_pk, None)


# ─── Zeroed stats template ───────────────────────────────────────────────────

def _zeroed_stats() -> dict:
    return {
        "session_count": 0,
        "active_session_count": 0,
        "message_count": 0,
        "user_message_count": 0,
        "assistant_message_count": 0,
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "total_cached_tokens": 0,
        "total_reasoning_tokens": 0,
        "total_tokens": 0,
        "avg_total_time": 0,
        "avg_ttft": 0,
        "call_count": 0,
        "run_count": 0,
        "success_run_count": 0,
        "failure_run_count": 0,
        "avg_run_time": 0,
        "query_count": 0,
        "total_query_tokens": 0,
        "failure_rate": 0,
    }


def _zeroed_max_pks() -> dict:
    return {
        "session": 0,
        "message": 0,
        "response": 0,
        "call": 0,
        "run": 0,
        "query": 0,
    }


# ─── Batched full computation (first access / cache miss) ──────────────────

def _batch_compute_all(agent_pks: list[int]) -> dict[int, dict]:
    """Compute stats for ALL given agents in ~8 aggregate queries.

    Returns {agent_pk: {"stats": {...}, "max_pks": {...}}}.
    Agents with no data get zeroed stats.
    """
    from server.models.sessions.session import SessionModel
    from server.models.message import Message
    from server.models.queries.response import Response
    from server.models.queries.query import Query
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.tasks.agent_task_run import AgentTaskRun
    from server.models.enums.task_enums import TaskRunStatus

    if not agent_pks:
        return {}

    # Initialize all agents with zeros
    results: dict[int, dict] = {
        pk: {"stats": _zeroed_stats(), "max_pks": _zeroed_max_pks()}
        for pk in agent_pks
    }

    agent_filter = Q(latest_session_version__agent__in=agent_pks)
    deep_filter = Q(session_version__session__latest_session_version__agent__in=agent_pks)

    # ── 1. Sessions ──
    try:
        rows = (
            SessionModel.objects.filter(agent_filter)
            .values("agent_pk=F('latest_session_version__agent')")
            .annotate(
                session_count=Count("pk"),
                active_session_count=Count("pk", filter=Q(latest_session_version__is_active=True)),
                max_pk=Max("pk"),
            )
        )
        for row in rows:
            pk = row["agent_pk"]
            if pk in results:
                results[pk]["stats"]["session_count"] = row["session_count"]
                results[pk]["stats"]["active_session_count"] = row["active_session_count"]
                results[pk]["max_pks"]["session"] = row["max_pk"] or 0
    except Exception:
        pass

    # ── 2. Messages ──
    try:
        rows = (
            Message.objects.filter(deep_filter)
            .values("agent_pk=F('session_version__session__latest_session_version__agent')")
            .annotate(
                message_count=Count("pk"),
                user_message_count=Count("pk", filter=Q(role="user")),
                assistant_message_count=Count("pk", filter=Q(role="assistant")),
                max_pk=Max("pk"),
            )
        )
        for row in rows:
            pk = row["agent_pk"]
            if pk in results:
                results[pk]["stats"]["message_count"] = row["message_count"]
                results[pk]["stats"]["user_message_count"] = row["user_message_count"]
                results[pk]["stats"]["assistant_message_count"] = row["assistant_message_count"]
                results[pk]["max_pks"]["message"] = row["max_pk"] or 0
    except Exception:
        pass

    # ── 3. Responses (tokens) ──
    try:
        rows = (
            Response.objects.filter(deep_filter)
            .values("agent_pk=F('session_version__session__latest_session_version__agent')")
            .annotate(
                total_prompt_tokens=Coalesce(Sum("prompt_tokens"), 0),
                total_completion_tokens=Coalesce(Sum("completion_tokens"), 0),
                total_cached_tokens=Coalesce(Sum("cached_tokens"), 0),
                total_reasoning_tokens=Coalesce(Sum("reasoning_tokens"), 0),
                max_pk=Max("pk"),
            )
        )
        for row in rows:
            pk = row["agent_pk"]
            if pk in results:
                results[pk]["stats"]["total_prompt_tokens"] = row["total_prompt_tokens"]
                results[pk]["stats"]["total_completion_tokens"] = row["total_completion_tokens"]
                results[pk]["stats"]["total_cached_tokens"] = row["total_cached_tokens"]
                results[pk]["stats"]["total_reasoning_tokens"] = row["total_reasoning_tokens"]
                results[pk]["stats"]["total_tokens"] = (
                    row["total_prompt_tokens"] + row["total_completion_tokens"]
                )
                results[pk]["max_pks"]["response"] = row["max_pk"] or 0
    except Exception:
        pass

    # ── 3b. Responses (avg times for successful) ──
    try:
        rows = (
            Response.objects.filter(deep_filter, status="SUCCESS")
            .values("agent_pk=F('session_version__session__latest_session_version__agent')")
            .annotate(
                avg_total_time=Avg("total_time"),
                avg_ttft=Avg("time_to_first_token"),
            )
        )
        for row in rows:
            pk = row["agent_pk"]
            if pk in results:
                results[pk]["stats"]["avg_total_time"] = (
                    round(float(row["avg_total_time"]), 2) if row["avg_total_time"] else 0
                )
                results[pk]["stats"]["avg_ttft"] = (
                    round(float(row["avg_ttft"]), 2) if row["avg_ttft"] else 0
                )
    except Exception:
        pass

    # ── 4. Task calls ──
    try:
        rows = (
            AgentTaskCall.objects.filter(deep_filter)
            .values("agent_pk=F('session_version__session__latest_session_version__agent')")
            .annotate(
                call_count=Count("pk"),
                max_pk=Max("pk"),
            )
        )
        for row in rows:
            pk = row["agent_pk"]
            if pk in results:
                results[pk]["stats"]["call_count"] = row["call_count"]
                results[pk]["max_pks"]["call"] = row["max_pk"] or 0
    except Exception:
        pass

    # ── 5. Task runs ──
    try:
        rows = (
            AgentTaskRun.objects.filter(deep_filter)
            .values("agent_pk=F('session_version__session__latest_session_version__agent')")
            .annotate(
                run_count=Count("pk"),
                success_run_count=Count("pk", filter=Q(status=TaskRunStatus.SUCCESS)),
                failure_run_count=Count("pk", filter=Q(status=TaskRunStatus.FAILURE)),
                max_pk=Max("pk"),
            )
        )
        for row in rows:
            pk = row["agent_pk"]
            if pk in results:
                results[pk]["stats"]["run_count"] = row["run_count"]
                results[pk]["stats"]["success_run_count"] = row["success_run_count"]
                results[pk]["stats"]["failure_run_count"] = row["failure_run_count"]
                results[pk]["max_pks"]["run"] = row["max_pk"] or 0
    except Exception:
        pass

    # ── 5b. Task runs (avg duration) ──
    try:
        rows = (
            AgentTaskRun.objects.filter(
                deep_filter,
                created_at__isnull=False,
                ended_at__isnull=False,
            )
            .values("agent_pk=F('session_version__session__latest_session_version__agent')")
            .annotate(
                avg_duration=Avg(Extract(F("ended_at") - F("created_at"), "epoch")),
            )
        )
        for row in rows:
            pk = row["agent_pk"]
            if pk in results:
                results[pk]["stats"]["avg_run_time"] = (
                    round(float(row["avg_duration"]), 2) if row["avg_duration"] else 0
                )
    except Exception:
        pass

    # ── 6. Queries (LLM) ──
    try:
        rows = (
            Query.objects.filter(deep_filter)
            .values("agent_pk=F('session_version__session__latest_session_version__agent')")
            .annotate(
                query_count=Count("pk"),
                total_query_tokens=Coalesce(Sum("tokens"), 0),
                max_pk=Max("pk"),
            )
        )
        for row in rows:
            pk = row["agent_pk"]
            if pk in results:
                results[pk]["stats"]["query_count"] = row["query_count"]
                results[pk]["stats"]["total_query_tokens"] = row["total_query_tokens"]
                results[pk]["max_pks"]["query"] = row["max_pk"] or 0
    except Exception:
        pass

    # Compute failure rate
    for pk, entry in results.items():
        stats = entry["stats"]
        run_count = stats["run_count"]
        stats["failure_rate"] = (
            round((stats["failure_run_count"] / run_count) * 100, 1) if run_count > 0 else 0
        )

    return results


# ─── Incremental update (subsequent renders) ─────────────────────────────────

def _incremental_update(agent_pk: int, cached: dict) -> dict:
    """Only count new items (pk > max_pk) and add deltas to cached stats.

    Much faster than a full recompute when tables are large and only a few
    new rows have been added since the last render.
    """
    from server.models.sessions.session import SessionModel
    from server.models.message import Message
    from server.models.queries.response import Response
    from server.models.queries.query import Query
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.tasks.agent_task_run import AgentTaskRun
    from server.models.enums.task_enums import TaskRunStatus

    stats = dict(cached["stats"])  # shallow copy
    max_pks = dict(cached["max_pks"])

    agent_filter = Q(latest_session_version__agent=agent_pk)
    deep_filter = Q(session_version__session__latest_session_version__agent=agent_pk)

    # ── Sessions ──
    try:
        last_pk = max_pks.get("session", 0)
        new_qs = SessionModel.objects.filter(agent_filter, pk__gt=last_pk)
        if new_qs.exists():
            delta = new_qs.aggregate(
                n=Count("pk"),
                active=Count("pk", filter=Q(latest_session_version__is_active=True)),
            )
            stats["session_count"] += delta["n"] or 0
            stats["active_session_count"] += delta["active"] or 0
            max_pks["session"] = new_qs.order_by("-pk").first().pk
    except Exception:
        pass

    # ── Messages ──
    try:
        last_pk = max_pks.get("message", 0)
        new_qs = Message.objects.filter(deep_filter, pk__gt=last_pk)
        if new_qs.exists():
            delta = new_qs.aggregate(
                n=Count("pk"),
                user_n=Count("pk", filter=Q(role="user")),
                asst_n=Count("pk", filter=Q(role="assistant")),
            )
            stats["message_count"] += delta["n"] or 0
            stats["user_message_count"] += delta["user_n"] or 0
            stats["assistant_message_count"] += delta["asst_n"] or 0
            max_pks["message"] = new_qs.order_by("-pk").first().pk
    except Exception:
        pass

    # ── Responses ──
    try:
        last_pk = max_pks.get("response", 0)
        new_qs = Response.objects.filter(deep_filter, pk__gt=last_pk)
        if new_qs.exists():
            delta = new_qs.aggregate(
                prompt=Coalesce(Sum("prompt_tokens"), 0),
                completion=Coalesce(Sum("completion_tokens"), 0),
                cached_t=Coalesce(Sum("cached_tokens"), 0),
                reasoning=Coalesce(Sum("reasoning_tokens"), 0),
            )
            stats["total_prompt_tokens"] += delta["prompt"] or 0
            stats["total_completion_tokens"] += delta["completion"] or 0
            stats["total_cached_tokens"] += delta["cached_t"] or 0
            stats["total_reasoning_tokens"] += delta["reasoning"] or 0
            stats["total_tokens"] = stats["total_prompt_tokens"] + stats["total_completion_tokens"]
            max_pks["response"] = new_qs.order_by("-pk").first().pk
    except Exception:
        pass

    # ── Task calls ──
    try:
        last_pk = max_pks.get("call", 0)
        new_qs = AgentTaskCall.objects.filter(deep_filter, pk__gt=last_pk)
        if new_qs.exists():
            stats["call_count"] += new_qs.count()
            max_pks["call"] = new_qs.order_by("-pk").first().pk
    except Exception:
        pass

    # ── Task runs ──
    try:
        last_pk = max_pks.get("run", 0)
        new_qs = AgentTaskRun.objects.filter(deep_filter, pk__gt=last_pk)
        if new_qs.exists():
            delta = new_qs.aggregate(
                n=Count("pk"),
                success=Count("pk", filter=Q(status=TaskRunStatus.SUCCESS)),
                failure=Count("pk", filter=Q(status=TaskRunStatus.FAILURE)),
            )
            stats["run_count"] += delta["n"] or 0
            stats["success_run_count"] += delta["success"] or 0
            stats["failure_run_count"] += delta["failure"] or 0
            max_pks["run"] = new_qs.order_by("-pk").first().pk
    except Exception:
        pass

    # ── Queries ──
    try:
        last_pk = max_pks.get("query", 0)
        new_qs = Query.objects.filter(deep_filter, pk__gt=last_pk)
        if new_qs.exists():
            delta = new_qs.aggregate(
                n=Count("pk"),
                tokens=Coalesce(Sum("tokens"), 0),
            )
            stats["query_count"] += delta["n"] or 0
            stats["total_query_tokens"] += delta["tokens"] or 0
            max_pks["query"] = new_qs.order_by("-pk").first().pk
    except Exception:
        pass

    # Recompute derived values
    run_count = stats["run_count"]
    stats["failure_rate"] = (
        round((stats["failure_run_count"] / run_count) * 100, 1) if run_count > 0 else 0
    )

    # Store updated cache
    _agent_stats_cache[agent_pk] = {"stats": stats, "max_pks": max_pks}
    return stats


# ─── Public card-data function (backward compatible) ────────────────────────

def agent_card_data(agent) -> dict:
    """Card info dict for an agent (no raise).

    Uses the incremental cache: first call does a full compute,
    subsequent calls only count new rows.
    """
    agent_pk = agent.pk

    cached = _agent_stats_cache.get(agent_pk)
    if cached is not None:
        stats = _incremental_update(agent_pk, cached)
    else:
        batch = _batch_compute_all([agent_pk])
        entry = batch.get(agent_pk)
        if entry:
            _agent_stats_cache[agent_pk] = entry
            stats = entry["stats"]
        else:
            stats = _zeroed_stats()

    # Build the display dict
    try:
        lav = agent.latest_agent_version
        description = getattr(lav, "description", "") or ""
    except Exception:
        description = ""

    try:
        from runtime.agents.agent import Agent

        runtime = Agent(agent)
        model_name = runtime.aimodel.name if runtime.aimodel else "No model"
        skill_count = len(runtime.allowedSkills)
        tool_count = len(runtime.allowedTools)
        task_count = len(runtime.allowedTasks)
        command_count = len(runtime.allowedCommands)
    except Exception:
        model_name = ""
        skill_count = tool_count = task_count = command_count = 0

    return {
        "pk": agent_pk,
        "name": getattr(agent, "name", "") or f"Agent {agent_pk}",
        "description": description or "No description yet.",
        "model_name": model_name,
        "skill_count": skill_count,
        "tool_count": tool_count,
        "task_count": task_count,
        "command_count": command_count,
        **stats,
    }


def format_tokens(n: int) -> str:
    """Format token count with K/M suffix."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def format_time(seconds: float) -> str:
    """Format duration in seconds to human-readable."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"


class AgentsOverview(ModelView):
    RIGHTPANEL_VIEW = RightPanelAgentsOverview
    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''
        <div class="ws-ov-topbar">
            <div class="ws-ov-breadcrumb">
                <span class="ws-ov-crumb">Agents</span>
            </div>
            <div class="ws-ov-search">
                <svg class="ws-ov-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
                <input id="agentsOvSearch" placeholder="Search agents..." oninput="agentsOvFilter()" autocomplete="off">
            </div>
            <button class="ws-ov-primary" onclick="pyview.openCreate()">+ New agent</button>
        </div>
        <div class="main-view-body">
            <div class="main-view-content ws-ov-content">
                <div class="ws-ov-heading-row">
                    <div>
                        <h1 class="ws-ov-title">Agents</h1>
                        <div class="ws-ov-subtitle">{{ pyview.agents|length }} agent(s)</div>
                    </div>
                    <div class="ws-ov-summary-strip">
                        <div class="ws-ov-stat-item">
                            <span class="ws-ov-stat-value">{{ pyview.total_sessions }}</span>
                            <span class="ws-ov-stat-label">Sessions</span>
                        </div>
                        <div class="ws-ov-stat-item">
                            <span class="ws-ov-stat-value">{{ pyview.total_messages }}</span>
                            <span class="ws-ov-stat-label">Messages</span>
                        </div>
                        <div class="ws-ov-stat-item">
                            <span class="ws-ov-stat-value">{{ pyview.total_tokens_display }}</span>
                            <span class="ws-ov-stat-label">Tokens</span>
                        </div>
                        <div class="ws-ov-stat-item">
                            <span class="ws-ov-stat-value">{{ pyview.total_runs }}</span>
                            <span class="ws-ov-stat-label">Task Runs</span>
                        </div>
                    </div>
                </div>
                <div class="ws-ov-grid" id="agentsOvGrid">
                    {% for agent in pyview.agents %}
                    <div class="ws-ov-card ws-ov-card--agent" data-name="{{ agent.name|lower }}" onclick="pyview.openAgent({{ agent.pk }})">
                        <div class="ws-ov-card-top">
                            <div class="ws-ov-icon ws-ov-icon--agent">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                            </div>
                            <h3>{{ agent.name }}</h3>
                            {% if agent.active_session_count %}
                            <span class="ws-ov-dot ws-ov-dot--active" title="{{ agent.active_session_count }} active session(s)"></span>
                            {% endif %}
                        </div>
                        <div class="ws-ov-card-info">
                            <div class="ws-ov-path" title="{{ agent.model_name }}">{{ agent.model_name }}</div>
                            <div class="ws-ov-desc">{{ agent.description }}</div>
                        </div>
                        <div class="ws-ov-card-capabilities">
                            <span class="ws-ov-cap">{{ agent.tool_count }} tools</span>
                            <span class="ws-ov-cap">{{ agent.task_count }} tasks</span>
                            <span class="ws-ov-cap">{{ agent.command_count }} cmds</span>
                            <span class="ws-ov-cap">{{ agent.skill_count }} skills</span>
                        </div>
                        <div class="ws-ov-card-stats">
                            <div class="ws-ov-stat-row">
                                <span class="ws-ov-stat-cell">
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                                    {{ agent.session_count }} sessions
                                </span>
                                <span class="ws-ov-stat-cell">
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 7 4 4 20 4 20 7"/><line x1="9" y1="20" x2="15" y2="20"/><line x1="12" y1="4" x2="12" y2="20"/></svg>
                                    {{ agent.run_count }} runs
                                </span>
                                <span class="ws-ov-stat-cell">
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                                    {{ agent.message_count }} msgs
                                </span>
                            </div>
                            <div class="ws-ov-stat-row">
                                <span class="ws-ov-stat-cell ws-ov-stat-cell--tokens">
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 6h5a3.5 3.5 0 0 1 0 6H6"/></svg>
                                    {{ agent.tokens_display }} tokens
                                </span>
                                {% if agent.failure_rate > 0 %}
                                <span class="ws-ov-stat-cell ws-ov-stat-cell--error">
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                                    {{ agent.failure_rate }}% fail rate
                                </span>
                                {% else %}
                                <span class="ws-ov-stat-cell ws-ov-stat-cell--ok">
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                                    healthy
                                </span>
                                {% endif %}
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                <div class="ws-ov-empty" id="agentsOvEmpty" style="display:{% if pyview.agents %}none{% else %}block{% endif %}">
                    <div class="ws-ov-empty-icon">⏵</div>
                    <h2>No agents found</h2>
                    <div>Try another search or create a new agent.</div>
                </div>
            </div>
        </div>
        <script>
            function agentsOvFilter() {
                var q = document.getElementById("agentsOvSearch").value.toLowerCase();
                var cards = document.querySelectorAll("#agentsOvGrid .ws-ov-card");
                var visible = 0;
                for (var i = 0; i < cards.length; i++) {
                    var match = cards[i].dataset.name.toLowerCase().indexOf(q) !== -1;
                    cards[i].style.display = match ? "" : "none";
                    if (match) visible++;
                }
                document.getElementById("agentsOvEmpty").style.display = visible ? "none" : "block";
            }
        </script>
    '''

    def __init__(self, subject: UiApp, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def agents(self) -> list[dict]:
        from server.models.agents.agent import AgentModel

        try:
            all_agents = list(AgentModel.objects.all().order_by("name"))
        except Exception:
            return []

        if not all_agents:
            return []

        agent_pks = [a.pk for a in all_agents]

        # Determine which agents need a full compute vs. incremental update
        uncached_pks = [pk for pk in agent_pks if pk not in _agent_stats_cache]

        # Full batch compute for uncached agents (8 queries total)
        if uncached_pks:
            batch_results = _batch_compute_all(uncached_pks)
            for pk, entry in batch_results.items():
                _agent_stats_cache[pk] = entry

        # Incremental update for all agents (fast: only counts new rows)
        for pk in agent_pks:
            cached = _agent_stats_cache.get(pk)
            if cached is not None:
                _incremental_update(pk, cached)

        # Build result dicts
        result = []
        for a in all_agents:
            cached = _agent_stats_cache.get(a.pk, {})
            stats = cached.get("stats", _zeroed_stats())

            data = {
                "pk": a.pk,
                "name": getattr(a, "name", "") or f"Agent {a.pk}",
                "description": "",
                "model_name": "",
                "skill_count": 0,
                "tool_count": 0,
                "task_count": 0,
                "command_count": 0,
                **stats,
            }
            data["tokens_display"] = format_tokens(data.get("total_tokens", 0))

            # Enrich with agent metadata (cheap — no heavy DB joins)
            try:
                lav = a.latest_agent_version
                data["description"] = getattr(lav, "description", "") or "No description yet."
            except Exception:
                data["description"] = "No description yet."
            try:
                from runtime.agents.agent import Agent

                runtime = Agent(a)
                data["model_name"] = runtime.aimodel.name if runtime.aimodel else "No model"
                data["skill_count"] = len(runtime.allowedSkills)
                data["tool_count"] = len(runtime.allowedTools)
                data["task_count"] = len(runtime.allowedTasks)
                data["command_count"] = len(runtime.allowedCommands)
            except Exception:
                pass

            result.append(data)
        return result

    @property
    def total_sessions(self) -> str:
        try:
            from server.models.sessions.session import SessionModel
            total = SessionModel.objects.count()
        except Exception:
            total = 0
        return str(total)

    @property
    def total_messages(self) -> str:
        try:
            from server.models.message import Message
            total = Message.objects.count()
        except Exception:
            total = 0
        return format_tokens(total)

    @property
    def total_tokens_display(self) -> str:
        try:
            from server.models.queries.response import Response
            total = Response.objects.aggregate(
                t=Sum("prompt_tokens") + Sum("completion_tokens")
            )["t"] or 0
        except Exception:
            total = 0
        return format_tokens(int(total))

    @property
    def total_runs(self) -> str:
        try:
            from server.models.tasks.agent_task_run import AgentTaskRun
            total = AgentTaskRun.objects.count()
        except Exception:
            total = 0
        return str(total)

    def openAgent(self, pk: int) -> None:
        from server.models.agents.agent import AgentModel
        from ui.main.agent.agent_view import AgentView

        try:
            agent = AgentModel.objects.get(pk=int(pk))
        except (AgentModel.DoesNotExist, ValueError, TypeError):
            return
        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(AgentView, agent)

    def openCreate(self) -> None:
        from ui.main.agent.create import AgentCreateView

        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(AgentCreateView, self.subject)

    def _find_main_view(self):
        parent = self.parent
        while parent and not hasattr(parent, "create_and_open_tab"):
            parent = parent.parent
        return parent