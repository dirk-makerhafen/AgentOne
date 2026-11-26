"""Task + Tool: call LLM directly without session context.

The task ``call_llm_direct`` is registered in scripts.md as a bound **task**.
It creates an ephemeral SessionModel + SessionVersionModel + SettingsModel,
builds a Query from the provided messages, runs the existing ``call_llm``
pipeline **synchronously**, and returns the Response data.

Called via ``_session.get_task("call_llm_direct").delay(messages=...,
model_name=...)`` from the framework when an agent needs a direct LLM call.

The tool ``llm_query`` is registered in scripts.md as a bound
**tool** (LLM-facing name ``llm_query``). It normalizes input and
dispatches the task asynchronously, returning the task call for auto-await
so the LLM receives the actual result instead of just a task id.

Args (task):
    _session: The active agent session (bound task). Its model is the
        default when ``model_name`` is not given.
    messages: List of OpenAI-format message dicts, e.g.:
        [{"role": "user", "content": "Classify this text."},
         {"role": "user", "content": "Hello world"}]
        No system prompt is injected — the caller must include one if needed.
    model_name: Canonical model name (e.g. "gpt-4o").
        None → caller's model → user's Default Model setting.
    reasoning_effort: One of none/minimal/low/medium/high/xhigh.
        None → caller session's setting → MINIMAL fallback.
    model_id: Exact ``AiModel`` pk.  Used by the UI's "Test" action to probe
        one specific provider row even when it is marked unavailable; its
        stale health status is cleared first.

Returns (task):
    Dict with keys:
        content (str): LLM response text
        model (str): Model name that was used
        prompt_tokens (int)
        completion_tokens (int)
        cached_tokens (int)
        reasoning_tokens (int)
        total_time (float): seconds
        status (str): "SUCCESS" or "FAILURE"
        session_pk (int): ephemeral session id for observability
        query_pk (int)
        response_pk (int)
        error (str, optional): present on failure

Returns (tool):
    The dispatched AgentTaskCall (auto-awaited by the scheduler, resolving
    to the task result dict) on success.
    (False, {"error": str}) on invalid input / dispatch failure.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.utils import timezone

from runtime.rate_limiter import RateLimitError
from server.models.enums.message_enums import MessageContentType, MessageRole
from server.models.enums.session_enums import SessionType
from server.models.queries.query import Query, QueryStatus
from server.models.queries.response import Response, ResponseStatus
from server.models.settings import AgentToolCallSyntax, ReasoningEffort, ResponseTemperature, SettingsModel

if TYPE_CHECKING:
    from server.models.providers.ai_model_offering import AiModelOffering as AiModel
    from runtime.session.session import Session

#: Roles accepted by the direct-call input (INFO is UI-only and must never
#: reach the LLM; "tool" needs a tool_call_id our simple builder cannot make).
_VALID_ROLES = frozenset(
    {MessageRole.SYSTEM.value, MessageRole.USER.value, MessageRole.ASSISTANT.value}
)


def _resolve_aimodel(  # pylint: disable=too-many-return-statements
    model_name: str | None,
    caller_session: "Session | None" = None,
    model_id: int | None = None,
) -> "AiModel | None":
    """Resolve an ``AiModel`` for the direct call.

    Priority:
      1. Explicit ``model_id`` (an exact provider row — used by the UI's
         "Test" button; its stale health status is cleared so the probe is a
         real retry).
      2. Explicit ``model_name`` parameter
      3. The caller's model (``caller_session.aimodel``) — "same model as
         caller" default from the feature request
      4. User's configured Default Model (``runtime.settings.get_default_model_name``)
      5. ``None`` — no usable model found
    """
    from server.models.providers.ai_model_offering import AiModelOffering as AiModel
    from runtime.session.aimodel_picker import pick_aimodel
    from runtime.settings.settings import get_default_model_name

    if model_id is not None:
        model = AiModel.objects.filter(pk=model_id).first()
        if model is None:
            return None
        # Manual probe: clear sticky 404/auth status on the row *and* its
        # provider/key so the call really hits the wire.  Rate-limit cooldowns
        # are deliberately left in place.  A failure is re-recorded
        # immediately.
        model.clear_health()
        provider = model.api_provider
        if provider is not None:
            provider.clear_health()
            for key in provider.api_keys.filter(enabled=True):
                if key.health_blocks_calls():
                    key.clear_health()
        return model

    if model_name:
        try:
            return pick_aimodel(model_name)
        except Exception:
            return None
    if caller_session is not None:
        try:
            caller_model = caller_session.aimodel
        except Exception:
            caller_model = None
        if caller_model is not None:
            return caller_model
    name = get_default_model_name()
    if not name:
        return None
    try:
        return pick_aimodel(name)
    except Exception:
        return None


#: Valid reasoning_effort values (mirrors SettingsModel.ReasoningEffort).
_VALID_EFFORTS = frozenset(
    {e.value for e in ReasoningEffort}
)


def _resolve_effort(
    reasoning_effort: str | None,
    caller_session: "Session | None" = None,
) -> str:
    """Resolve the effort for the ephemeral session.

    Precedence: explicit argument → caller session's setting → MINIMAL.
    Unknown strings fall back to the caller/default instead of writing
    garbage into SettingsModel (which would fail the CharField choices
    validation on some paths).
    """
    if reasoning_effort is not None:
        effort = str(reasoning_effort).lower()
        if effort in _VALID_EFFORTS:
            return effort
    if caller_session is not None:
        try:
            caller_effort = str(caller_session.reasoning_effort or "").lower()
        except Exception:
            caller_effort = ""
        if caller_effort in _VALID_EFFORTS:
            return caller_effort
    return ReasoningEffort.MINIMAL.value


def _resolve_api_key(aimodel: "AiModel", api_key_id: int | None = None):
    """Pick the exact key for a direct/probe call.

    An explicit id wins (and must belong to the offering's provider).  With no
    id, the least-loaded ready key is used; a keyless provider returns None.
    """
    from server.models.providers.api_key import ApiKey

    provider = getattr(aimodel, "api_provider", None)
    if provider is None:
        return None
    if api_key_id is not None:
        key = ApiKey.objects.filter(pk=api_key_id, api_provider=provider).first()
        if key is not None:
            return key
    keys = list(provider.api_keys.filter(enabled=True))
    if not keys:
        return None
    ready = [
        key for key in keys
        if not key.is_rate_limited()[0] and not provider.is_rate_limited(apikey=key)[0]
    ]
    return sorted(ready or keys, key=lambda key: key.pk)[0]


def _build_ephemeral_session(
    aimodel: "AiModel",
    caller_session: "Session | None" = None,
    reasoning_effort: str | None = None,
    *,
    api_key=None,
    strict: bool = True,
) -> tuple:
    """Create a minimal ephemeral session for the LLM call.

    Returns (SessionModel, SessionVersionModel, SettingsModel).
    The session is marked inactive and exists solely to host the
    Query/Response records for observability, isolating the direct call
    from the caller's in-flight turn pipeline (which forbids a second
    WAITING/ACTIVE query on the same session version).

    The caller's agent is reused for the version's agent FK so no
    throwaway AgentModel rows accumulate and task allow-lists resolve;
    when no caller session is available its agent is used as fallback.
    The caller is also recorded as the ephemeral session's ``parent_session``
    (and as the version's creating session) so the dashboard can show which
    chat owns an otherwise anonymous "LLM Direct Call" row.

    Reasoning effort resolution: explicit ``reasoning_effort`` argument
    wins, then the caller session's setting, then MINIMAL.  (Previously
    this was hardcoded to MINIMAL, so the caller's dropdown selection
    never had any effect on direct calls.)
    """
    from server.models.sessions.session import SessionModel
    from server.models.sessions.session_version import SessionVersionModel

    now = timezone.now()

    # Bound tasks receive a runtime Session wrapper, but callers may hand us a
    # bare model (or a stub in tests).  Only real rows may fill the FK fields.
    caller_model = getattr(caller_session, "model", None)
    if not isinstance(caller_model, SessionModel):
        caller_model = caller_session if isinstance(caller_session, SessionModel) else None

    caller_version = None
    if caller_session is not None:
        try:
            caller_version = caller_session.get_version_model()
            agent = caller_version.agent
        except Exception:
            agent = None
    else:
        agent = None
    if not isinstance(caller_version, SessionVersionModel):
        caller_version = None
    if agent is None:
        from server.models.agents.agent import AgentModel

        agent = AgentModel.objects.create(
            # Microseconds: AgentModel.name is globally unique, and two
            # direct calls within the same second must not collide.
            name=f"LLM Direct Call Agent {now.strftime('%H:%M:%S.%f')}",
        )

    # 1. SessionModel (single-use subtask type — "llm_direct" is not a
    # valid SessionType choice).
    session_model = SessionModel.objects.create(
        name=f"LLM Direct Call {now.strftime('%H:%M:%S')}",
        turn_count=0,
        unattended_turn_count=0,
        is_active=False,
        last_active_at=now,
        session_type=SessionType.SUBTASK_DELEGATE,
        parent_session=caller_model,
        is_pinned=False,
        is_archived=False,
    )

    # 2. SettingsModel (bypasses agent resolution; CUSTOM skips tool
    # building in call_llm since a direct call takes no tools).
    #
    # A direct call is a *pin*: the caller asked for this model (often this
    # exact provider row, from the Test button), so it must not silently
    # reroute to a sibling.  ``strict`` additionally pins the API key and sets
    # a zero wait budget; callers that only want "prefer this model" can pass
    # strict=False to keep the normal provider ladder.
    route_fields = {
        "route_target": aimodel.name,
        "preferred_api_key": api_key,
    }
    if strict:
        route_fields.update(
            {
                "route_pin": "offering_key",
                "route_failover": "none",
                "route_wait_seconds": 0,
            }
        )
    settings = SettingsModel.objects.create(
        aimodel=aimodel,
        tool_call_syntax=AgentToolCallSyntax.CUSTOM,
        reasoning_effort=_resolve_effort(reasoning_effort, caller_session),
        precision=ResponseTemperature.PRECISE.value,
        **route_fields,
    )

    # 3. SessionVersionModel (links session to agent + settings) and pin
    # it as the session's latest version so Session(model) resolves.
    session_version = SessionVersionModel.objects.create(
        session=session_model,
        agent=agent,
        version_number=1,
        description="Direct LLM call",
        session_settings=settings,
        parent_session=caller_model,
        parent_session_version=caller_version,
    )
    session_model.latest_session_version = session_version
    session_model.save()

    return session_model, session_version, settings


def call_llm_direct(
    _session: "Session",
    messages: list[dict],
    model_name: str | None = None,
    reasoning_effort: str | None = None,
    model_id: int | None = None,
    api_key_id: int | None = None,
    strict: bool = True,
) -> dict:
    """Execute a raw LLM query via the existing call_llm pipeline.

    Creates an ephemeral session, builds a Query with the provided messages,
    runs ``call_llm`` synchronously on the ephemeral session, and returns
    the Response data.

    Args:
        _session: The active agent session (bound task). Supplies the
            default model when ``model_name`` is None, and the default
            reasoning effort when ``reasoning_effort`` is None.
        messages: List of OpenAI-format message dicts.
        model_name: Canonical model name (e.g. "gpt-4o").
        reasoning_effort: One of none/minimal/low/medium/high/xhigh.
            None → inherit the caller session's setting.

    Returns:
        Response dict with content, tokens, timing, and status.
    """
    # ── 1. Resolve model ───────────────────────────────────────────────
    aimodel = _resolve_aimodel(model_name, caller_session=_session, model_id=model_id)
    if not aimodel:
        return {
            "status": "FAILURE",
            "error": "No AI model available. Check that a Default Model is configured or pass model_name.",
        }
    # A direct call is still bound by the caller's scope policy.  Prefer a
    # local provider for the same canonical name, and refuse the call outright
    # when no local route exists.
    try:
        # Require a literal boolean: test doubles often expose truthy MagicMock
        # attributes for unconfigured properties.
        local_only = getattr(_session, "local_only", False) is True
    except Exception:  # pylint: disable=broad-exception-caught
        local_only = False
    if local_only and getattr(aimodel, "is_cloud", True) is True:
        from runtime.session.aimodel_picker import pick_aimodel

        alternative = pick_aimodel(aimodel.name, stable=True, local_only=True)
        if alternative is None:
            return {
                "status": "FAILURE",
                "error": (
                    f"Local-only scope: {aimodel.name} has no local provider. "
                    "Choose a model served by a local provider."
                ),
            }
        aimodel = alternative

    # ── 2. Create ephemeral session ────────────────────────────────────
    try:
        direct_key = _resolve_api_key(aimodel, api_key_id)
        session_model, session_version, settings = _build_ephemeral_session(
            aimodel,
            caller_session=_session,
            reasoning_effort=reasoning_effort,
            api_key=direct_key,
            strict=strict,
        )
    except Exception as exc:
        return {
            "status": "FAILURE",
            "error": f"Failed to create ephemeral session: {exc}",
        }

    # ── 3. Build Query with messages ───────────────────────────────────
    try:
        query = Query.objects.create(
            session=session_model,
            session_version=session_version,
            status=QueryStatus.WAITING,
        )
        for msg in messages:
            query.add_message(
                role=msg["role"],
                content_type=MessageContentType.TEMPLATE if msg.get("template_data", None) else MessageContentType.TEXT,
                content=msg["content"],
                template_data=msg.get("template_data", None)
            )
        query.save()
    except Exception as exc:
        return {
            "status": "FAILURE",
            "error": f"Failed to build query: {exc}",
        }

    # ── 4. Call LLM via existing pipeline (synchronous) ───────────────
    # NOTE: not via .delay() — delay() returns an AgentTaskCall promise,
    # not a Response, and the bound-task argument serializer cannot carry
    # a Session object (session is auto-injected by the framework).
    try:
        from runtime.session.session import Session as RuntimeSession

        ephemeral = RuntimeSession(
            session_model, pinned_session_version=session_version
        )
        call_llm_task = ephemeral.get_task("call_llm")
        if call_llm_task is not None:
            response: Response = call_llm_task.call(query=query)
        else:
            # Caller agent disallows call_llm (should not happen with the
            # reused agent) — load the sibling pipeline module directly
            # (relative imports don't work in versioned runtime copies).
            import importlib.util
            from pathlib import Path as _Path

            _spec = importlib.util.spec_from_file_location(
                "_call_llm_fallback",
                _Path(__file__).with_name("call_llm.py"),
            )
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            response = _mod.call_llm(ephemeral, query)

        result = {
            "content": response.content or "",
            "model": response.model_name,
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "cached_tokens": response.cached_tokens,
            "reasoning_tokens": response.reasoning_tokens,
            "total_time": round(response.total_time or 0, 3),
            "status": response.status,
            "error_type": getattr(response, "error_type", "") or "",
            "session_pk": session_model.pk,
            "query_pk": query.pk,
            "response_pk": response.pk,
        }
        if response.status != ResponseStatus.SUCCESS:
            # call_llm can return (not raise) a FAILURE response, e.g. an
            # empty stream — surface why, or the caller sees status-only.
            result["error"] = (
                getattr(response, "error_message", "")
                or response.finish_reason
                or "LLM returned an empty response."
            )
        return result

    except RateLimitError:
        # Must propagate: AgentTaskRun.apply() parks the run as
        # RATE_LIMITED with auto-resume. Swallowing it here would turn a
        # cooldown into a permanent FAILURE.
        raise
    except Exception as exc:
        # The call_llm pipeline may have left a FAILURE response — read it
        try:
            resp = Response.objects.filter(query=query).order_by("-pk").first()
            content = resp.content if resp and resp.content else ""
            model_name_out = resp.model_name if resp else ""
            pt = resp.prompt_tokens if resp else 0
            ct = resp.completion_tokens if resp else 0
            error_type = getattr(resp, "error_type", "") if resp else ""
        except Exception:
            content, model_name_out, pt, ct, error_type = "", "", 0, 0, ""

        return {
            "content": content,
            "model": model_name_out,
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "total_time": 0,
            "status": "FAILURE",
            "error_type": error_type,
            "session_pk": session_model.pk,
            "query_pk": query.pk,
            "error": str(exc),
        }


def llm_query(
    _session: Any | None = None,
    messages: str | list[str] | list[dict] | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> tuple[bool, dict]:
    """Tool: call LLM directly without session context.

    Dispatches the ``call_llm_direct`` task and returns its call so the
    scheduler auto-awaits it — the LLM receives the actual content,
    not just a task id.

    Args:
        _session: Bound session (required for dispatch).
        messages: Input as str (single user message), list[str] (multiple
            user messages), or list[dict] with
            {"role": "system"/"user"/"assistant", "content": "..."}.
            The "message" key is accepted as an alias for "content".
            Required — omitting it is a schema error before this runs.
        model: Model name (e.g. "gpt-4o"). None = caller's model, then
            Default Model.
        reasoning_effort: One of none/minimal/low/medium/high/xhigh.
            None = inherit the caller session's setting.

    Returns:
        The dispatched AgentTaskCall on success (resolves to the task
        result dict via auto-await).
        (False, {"error": str}) on invalid input or dispatch failure.
    """
    if messages is None:
        return (False, {"error": "messages is required. Pass a string, list of strings, or list of message dicts."})
    if _session is None:
        return (False, {"error": "No session available for dispatch."})
    if reasoning_effort is not None and str(reasoning_effort).lower() not in _VALID_EFFORTS:
        return (False, {"error": f"Invalid reasoning_effort {reasoning_effort!r}. Use one of: {sorted(_VALID_EFFORTS)}."})

    # Normalize input to OpenAI-format list[dict]
    try:
        parsed = _normalize_input(messages)
    except ValueError as exc:
        return (False, {"error": str(exc)})

    # Dispatch async via the bound task — do NOT call the module-level
    # function (it has no .delay); the task is auto-injected with session.
    try:
        task = _session.get_task("call_llm_direct")
        if task is None:
            return (False, {"error": "Task 'call_llm_direct' is not available for this session."})
        kwargs: dict[str, Any] = {"messages": parsed, "model_name": model}
        if reasoning_effort is not None:
            kwargs["reasoning_effort"] = str(reasoning_effort).lower()
        return task.delay(**kwargs)
    except Exception as exc:
        return (False, {"error": f"Failed to dispatch direct LLM call: {exc}"})


def _normalize_input(messages: str | list[str] | list[dict]) -> list[dict]:
    """Normalize various input formats to OpenAI-format message list."""
    if isinstance(messages, str):
        if not messages.strip():
            raise ValueError("Empty string provided. Pass a non-empty string, list of strings, or list of message dicts.")
        return [{"role": "user", "content": messages}]

    if isinstance(messages, list) and len(messages) > 0:
        if all(isinstance(m, str) for m in messages):
            if not any(m.strip() for m in messages):
                raise ValueError("Empty strings provided. Pass non-empty text.")
            return [{"role": "user", "content": m} for m in messages]
        if all(isinstance(m, dict) for m in messages):
            normalized: list[dict] = []
            for msg in messages:
                role = msg.get("role")
                # Accept "message" as an alias for "content" (per request).
                content = msg.get("content", msg.get("message"))
                if role not in _VALID_ROLES:
                    raise ValueError(
                        f"Invalid role {role!r}. Use one of 'system', 'user', 'assistant'. "
                        f"Got: {msg}"
                    )
                if not isinstance(content, str) or not content.strip():
                    raise ValueError(
                        "Each message content must be a non-empty string. "
                        f"Got: {msg}"
                    )
                normalized_data = {"role": role, "content": content}
                
                template_data = msg.get("template_data", None)
                if template_data:
                    normalized_data["template_data"] = template_data

                normalized.append(normalized_data)
            return normalized
        raise ValueError(
            "Mixed list: use either all strings or all message dicts. "
            f"Got: {messages}"
        )

    raise ValueError(
        "Invalid input format. Pass:\n"
        "  str → single user message\n"
        "  list[str] → multiple user messages\n"
        "  list[dict] → OpenAI format [{'role': 'user', 'content': '...'}]"
    )
