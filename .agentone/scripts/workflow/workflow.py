"""Session-private dynamic workflows — thin bound wrappers.

Workflows are ordered tool-call recipes that live only for this session:
linear steps plus parallel ``group``s, ``map`` fan-outs, and ``when``
conditionals.  They are NOT registered tools: the only way to run one is
``workflow_run``.  Typical loop: ``workflow_create`` once, then
``workflow_run`` as often as needed; ``workflow_get`` to debug/iterate.

Rules:
- Names: 3-41 chars, lowercase letter first, then lowercase/digits/_ .
- Each step has an ``id`` plus exactly one of ``tool`` (single call),
  ``function`` (inline Python body — a step-local helper, no adhoc tool
  needed), ``group`` (2+ parallel branches), or ``map`` (fan-out over a
  list), plus an optional ``when`` predicate over prior steps.
  Group branches, map consumers, and map producers accept ``tool`` or
  ``function`` leaves anywhere a call goes.
- Templates use ``{{ inputs.* }}``, ``{{ steps.<id>.output }}``,
  ``{{ item }}``/``{{ index }}`` (map consumers only).  Unknown names and
  forward references are rejected at save time.
- Runs are chained and non-blocking: ``workflow_run`` pins the current
  version and returns immediately with the final result auto-awaited, so
  the turn receives the whole workflow's output.  A failed step fails
  the workflow (``when``-skipped steps resolve to null instead).
- Max 20 workflows per session, 64KB each, 32 steps, map fan-out 8
  per wave (hard 32) over at most 32 items, nesting 3 levels deep.
- Archive is a visibility state, not a freeze: workflows keep working
  on archived sessions, like messages, files, and templates.

All real logic lives in ``runtime/session_workflows.py`` so it is
unit-testable without the loader; these functions only forward the bound
session.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from runtime.session.session import Session


def _pk(_session: Session) -> int:
    return _session.model.pk


def _policy(_session: Session):
    """Best-effort workspace policy for save-time path scans (None-safe)."""
    try:
        from runtime.workspace_access import resolve_policy

        return resolve_policy(_session)
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def _err(exc: Exception) -> tuple[bool, dict]:
    from runtime.session_workflows import WorkflowError

    if isinstance(exc, WorkflowError):
        return (False, {"status": "error", "message": str(exc)})
    import traceback

    return (False, {"status": "exception",
                    "message": f"{exc}\n{traceback.format_exc()}"})


def workflow_create(
    _session: Session,
    name: str,
    steps: List[Dict[str, Any]],
    description: str = "",
    inputs_schema: Optional[Dict[str, Any]] = None,
) -> tuple[bool, dict]:
    """Create one session-private workflow for reuse this session.

    Use this when you need the same multi-tool recipe several times and
    re-issuing every call each time would be wasteful or error-prone
    (triage-then-file, fan-out summarization, conditional escalation).

    Do NOT use this for one-shot sequences — just call the tools directly.
    Do NOT use this for anything that must outlive the session (work items,
    project files, manifests).

    Args:
        name: Workflow name (3-41 chars, lowercase letter first).
        steps: Ordered step list. Each step is ``{"id": ..., ...}`` with
            exactly one action: ``"tool"`` + ``"args"?`` (single call),
            ``"function"`` + ``"args"?`` (inline Python body — see below),
            ``"group": [...]`` (2+ parallel branches, each a tool call,
            a function, or one nested group), or ``"map": {"producer",
            "consumer", "max_parallel"?}`` where the producer is
            ``{"step": "<prior_id>", "path"?}`` (must resolve to a list),
            an inline tool call, or an inline function, and the consumer
            is one tool call, one function (or one group) applied per
            element with ``{{ item }}`` / ``{{ index }}`` bound. Optional
            ``"when"`` predicate over prior steps (grammar below).
            Referencing prior output: every finished step is a record
            with ``output`` (the tool's result payload), ``count``
            (number of call results: 1 for single steps, N for maps;
            0 when skipped — NOT the length of your data, use
            ``|length`` for that), and ``succeeded`` (bool) — e.g.
            ``{{ steps.fetch.output }}``, ``{{ steps.items.count }}``.
            Payload shapes (navigate INTO ``output``, never feed it
            whole): a ``python`` step's payload is ``{stdout, stderr,
            return_code}`` — ``{{ steps.p.output }}`` is that dict,
            ``{{ steps.p.output.stdout }}`` is the printed text (parse
            it with ``json.loads`` inside the next body if it encodes
            JSON); a ``function``/adhoc step's payload is
            ``{return_code, result}`` — ``{{ steps.f.output.result }}``
            is the native returned value. Iterating ``output`` itself
            iterates the payload's keys, not your data. A value that
            is exactly one ``{{ ... }}`` keeps its type exactly:
            natives stay native (typed tools receive real values) and
            strings stay strings — even when a string looks like JSON
            or a number, it is never auto-parsed. Text mixed with
            literal characters renders to a string. String values
            interpolate directly: ``print('Item: {{ item }}')`` renders
            to ``print('Item: apple')`` — no json round-trip needed for
            strings, and dicts render as Python literals; use ``|tojson``
            only when embedding into JSON/JS. Never mix Jinja ``{{ }}``
            with Python f-string ``{}`` placeholders for the same value
            (Jinja renders first, leaving broken braces) — use plain
            strings with ``{{ }}`` instead. A step's
            ``output`` is the tool payload with the ``(ok, ...)``
            envelope removed — check the tool's own docstring for its
            shape before writing ``path`` or ``.output.<key>`` paths.
            Mapping over ``python`` output: ``stdout`` is always text
            (a script runner returns text and an exit code — a
            JSON-encoded list string there is parsed automatically).
            Reshaping data between steps? Write it inline:
            ``{"id": "pick", "function": "return ...",
            "args": {"content": "{{ steps.fetch.output.result }}"}}``
            — the body is a function body (bare ``return`` allowed),
            argument names arrive as variables, and whatever it returns
            flows on natively (reach it via ``path: "result.<key>"``). In map
            consumers ``item``/``index`` arrive as variables with no
            explicit arg needed. Bodies are scanned and syntax-checked
            at save time, run isolated like adhoc tools. Reach for
            ``adhoc_create`` only when the same helper is needed across
            steps or workflows; reserve ``python`` for scripts whose
            printed text is the point.
            ``when`` grammar: ``steps.<id> succeeded|failed``;
            ``steps.<id>[.output...] == != > >= < <= <literal>``;
            ``contains`` / ``not contains``; ``is empty`` /
            ``is not empty``; clauses joined with ``and``/``or`` (no
            parens, no bare ``{{ }}`` needed). A false ``when`` skips
            the step (its output is null).
        description: One line on what it does (shown by ``workflow_list``).
        inputs_schema: Optional JSON-schema-subset dict, e.g.
            ``{"type": "object", "properties": {"topic": {"type": "string"}},
            "required": ["topic"]}``. Run inputs are validated against it.

    Returns:
        (True, {status, name, version, steps}) on success, else
        (False, {status, message}).
    """
    from runtime import session_workflows as _wf

    try:
        result = _wf.create_workflow(_pk(_session), name, steps, description,
                                     inputs_schema, policy=_policy(_session))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return _err(exc)
    return (True, {"status": "success", **result})


def workflow_update(
    _session: Session,
    name: str,
    steps: Optional[List[Dict[str, Any]]] = None,
    description: Optional[str] = None,
    inputs_schema: Optional[Dict[str, Any]] = None,
) -> tuple[bool, dict]:
    """Update one workflow's steps and/or metadata (mints a new version).

    Only this session's link moves — siblings and forks keep theirs.
    Saving identical content is a no-op (``unchanged: True``, no new
    version).  Running executions pin their version, so updating mid-run
    cannot change the running execution.

    Args:
        name: Existing workflow name.
        steps: New full step list (re-validated). Omit to keep current.
        description: New description. Omit to keep.
        inputs_schema: New schema. Omit to keep.

    Returns:
        (True, {status, name, version, steps?, unchanged?}) or
        (False, {status, message}).
    """
    from runtime import session_workflows as _wf

    try:
        result = _wf.update_workflow(_pk(_session), name, steps, description,
                                     inputs_schema, policy=_policy(_session))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return _err(exc)
    return (True, {"status": "success", **result})


def workflow_list(_session: Session) -> tuple[bool, dict]:
    """List this session's workflows (metadata only, no step bodies).

    Call this before ``workflow_run`` when you are unsure what exists.
    Returns (True, {status, workflows: [{name, description, version,
    steps, updated_at}]}).
    """
    from runtime import session_workflows as _wf

    try:
        workflows = _wf.list_workflows(_pk(_session))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return _err(exc)
    return (True, {"status": "success", "workflows": workflows})


def workflow_get(_session: Session, name: str) -> tuple[bool, dict]:
    """Fetch one workflow's full definition (for debug/iterate).

    Args:
        name: Workflow name from ``workflow_list``.

    Returns:
        (True, {status, name, definition, meta}) or (False, {status,
        message}).
    """
    from runtime import session_workflows as _wf

    try:
        result = _wf.get_workflow(_pk(_session), name)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return _err(exc)
    return (True, {"status": "success", **result})


def workflow_delete(_session: Session, name: str) -> tuple[bool, dict]:
    """Delete one session workflow (removes the link only).

    Version rows stay as the audit trail.  Running executions pin their
    version directly, so deleting mid-run is safe.

    Args:
        name: Workflow name from ``workflow_list``.
    """
    from runtime import session_workflows as _wf

    try:
        result = _wf.delete_workflow(_pk(_session), name)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return _err(exc)
    return (True, {"status": "success", **result})


def workflow_validate(
    _session: Session,
    steps: List[Dict[str, Any]],
    name: str = "validate_only",
    description: str = "",
    inputs_schema: Optional[Dict[str, Any]] = None,
) -> tuple[bool, dict]:
    """Dry-run validation of a workflow definition (writes nothing).

    Args:
        steps: Step list in ``workflow_create`` format.
        name: Name to validate against (default valid placeholder).
        description: Description to validate.
        inputs_schema: Schema to validate.

    Returns:
        (True, {status, steps}) when valid, else (False, {status,
        message}).
    """
    from runtime import session_workflows as _wf

    try:
        canonical = _wf.validate_workflow(name, steps, description,
                                          inputs_schema,
                                          session_pk=_pk(_session),
                                          policy=_policy(_session))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return _err(exc)
    return (True, {"status": "success", "name": canonical["name"],
                   "steps": len(canonical["steps"])})


def workflow_run(
    _session: Session,
    name: str,
    inputs: Optional[Dict[str, Any]] = None,
    _visited: Optional[List[str]] = None,
) -> Any:
    """Run a session workflow by name (auto-awaited, non-blocking).

    Pins the current version, validates ``inputs`` against the stored
    schema, then executes steps in order — tool calls, parallel groups,
    map fan-outs, and ``when`` conditionals — without occupying a worker
    between steps.  The turn receives the final envelope directly:
    ``{status, workflow, version, outputs: {step_id: output}, skipped}``.

    Each step's tool goes through its normal dispatch, so approvals,
    workspace-policy checks, and rate limits apply per sub-call
    unchanged (inline ``function`` bodies were scanned at save time and
    run as internal steps — no approval hop).  A failed sub-call fails the whole workflow, and the
    error names the step and carries the tool's own error output —
    when a run fails, inspect the failed step's tool output first
    (a map complaining about its producer usually means the producer
    step itself errored).  An approval-ask parks the sub-call until
    decided.

    Args:
        name: Workflow name from ``workflow_list``.
        inputs: JSON object for ``{{ inputs.* }}`` (validated when the
            workflow declares ``inputs_schema``).

    Returns:
        The dispatched continuation call (auto-awaited to the final
        envelope), or (False, {status, message}) when the run cannot
        start (unknown workflow, bad inputs, unavailable engine).
    """
    from runtime import session_workflows as _wf

    try:
        return _wf.run_workflow(_session, name, inputs, _visited=_visited)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        import traceback

        return (False, {"status": "exception",
                        "message": f"{exc}\n{traceback.format_exc()}"})
