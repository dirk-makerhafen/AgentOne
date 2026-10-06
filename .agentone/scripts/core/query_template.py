"""Tools: store and execute reusable query (prompt) templates.

Templates live in the session-private folder at
``<SESSIONS_BASE>/<session_pk>/templates/<name>.md`` — each file has a
frontmatter head (``name``, ``description``, ``variables``) and a Jinja2
body.  See ``runtime/query_templates.py`` for the file format and coercion
rules.

Tools (all bound, ``_session`` first):

- ``template_list`` — list this session's templates (name/description/vars).
- ``template_get`` — fetch one template (schema + body).
- ``template_save`` — create or overwrite a template (validates first).
- ``template_delete`` — delete a template.
- ``template_render`` — render a template with variables, no LLM call
  (preview / internal harness use).
- ``template_execute`` — render then run via the ``call_llm_direct``
  ephemeral pipeline (same as ``llm_query``); auto-awaited so the LLM
  receives the actual result content.
"""

from __future__ import annotations

from typing import Any

from runtime.query_templates import (
    TemplateError,
    delete_template,
    get_template,
    list_templates,
    render_template_by_name,
    save_template,
)


def _session_pk(_session: Any) -> Any:
    return _session.model.pk


def template_list(_session: Any) -> tuple[bool, dict]:
    """List this session's query templates.

    Returns:
        ``(True, {"status": "success", "templates": [...]})`` where each
        entry has ``name``, ``description``, and ``variables``.
    """
    try:
        templates = list_templates(_session_pk(_session))
    except Exception as exc:
        return False, {"status": "error", "message": str(exc)}
    return True, {"status": "success", "templates": templates}


def template_get(_session: Any, name: str | None = None) -> tuple[bool, dict]:
    """Fetch one template with its body.

    Args:
        name: Template name (file slug).

    Returns:
        ``(True, {"status": "success", "template": {...}})`` including the
        Jinja ``body``, or ``(False, ...)`` when missing/invalid.
    """
    if not name or not str(name).strip():
        return False, {"status": "error", "message": "name is required."}
    try:
        template = get_template(_session_pk(_session), str(name).strip())
    except TemplateError as exc:
        return False, {"status": "error", "message": str(exc)}
    except Exception as exc:
        return False, {"status": "error", "message": str(exc)}
    return True, {"status": "success", "template": template.to_dict(include_body=True)}


def template_save(
    _session: Any,
    name: str | None = None,
    body: str | None = None,
    description: str = "",
    variables: list[dict[str, Any]] | None = None,
) -> tuple[bool, dict]:
    """Create or overwrite a query template (validates before writing).

    Args:
        name: Template name (lowercase letters, digits, '-'/'_').
        body: Jinja2 template body, e.g. ``"Summarize: {{ text }}"``.
        description: Human-readable description.
        variables: List of variable specs, each a mapping with ``name``
            plus optional ``type`` (string/integer/number/boolean),
            ``required``, ``default``, ``description`` — e.g.
            ``[{"name": "question"}]``.  A JSON/YAML string encoding such
            a list is also accepted.  NEVER pass a bare variable name
            string: ``"question"`` is not a valid value (use
            ``[{"name": "question"}]``).

    Returns:
        ``(True, {"status": "success", "template": {...}})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    if not name or not str(name).strip():
        return False, {"status": "error", "message": "name is required."}
    if body is None or not str(body).strip():
        return False, {"status": "error", "message": "body is required and must not be empty."}
    try:
        template = save_template(
            _session_pk(_session),
            str(name).strip(),
            str(body),
            description=description or "",
            # Pass through untouched: the engine normalizes lists as well
            # as JSON/YAML strings (list("...") here would split one
            # variable name into per-character specs).
            variables=variables,
        )
    except TemplateError as exc:
        return False, {"status": "error", "message": str(exc)}
    except Exception as exc:
        return False, {"status": "error", "message": str(exc)}
    return True, {"status": "success", "template": template.to_dict(include_body=True)}


def template_delete(_session: Any, name: str | None = None) -> tuple[bool, dict]:
    """Delete a query template.

    Args:
        name: Template name.

    Returns:
        ``(True, {"status": "success", ...})`` or ``(False, ...)``.
    """
    if not name or not str(name).strip():
        return False, {"status": "error", "message": "name is required."}
    try:
        delete_template(_session_pk(_session), str(name).strip())
    except TemplateError as exc:
        return False, {"status": "error", "message": str(exc)}
    except Exception as exc:
        return False, {"status": "error", "message": str(exc)}
    return True, {"status": "success", "name": str(name).strip()}


def template_render(
    _session: Any,
    name: str | None = None,
    variables: dict[str, Any] | None = None,
) -> tuple[bool, dict]:
    """Render a template with variables without calling the LLM (preview).

    Args:
        name: Template name.
        variables: Object mapping variable names to values, e.g.
            ``{"question": "..."}`` (defaults apply, numbers/bools
            coerced — ``"5"`` → ``5`` for integer/number types).

    Returns:
        ``(True, {"status": "success", "rendered": ..., "template": ...}})``
        or ``(False, {"status": "error", "message": ...})`` listing missing
        variables or type errors.
    """
    if not name or not str(name).strip():
        return False, {"status": "error", "message": "name is required."}
    try:
        # Pass through untouched — see template_execute for why.
        template, rendered = render_template_by_name(
            _session_pk(_session), str(name).strip(), variables
        )
    except TemplateError as exc:
        return False, {"status": "error", "message": str(exc)}
    except Exception as exc:
        return False, {"status": "error", "message": str(exc)}
    return True, {
        "status": "success",
        "rendered": rendered,
        "template": template.to_dict(include_body=False),
    }


def template_execute(
    _session: Any | None = None,
    name: str | None = None,
    variables: dict[str, Any] | None = None,
    model: str | None = None,
) -> Any:
    """Execute a template: render with variables, run via ``call_llm_direct``.

    The template is validated and rendered synchronously (missing variables
    or type errors fail fast with ``(False, {"error": ...})``).  The
    rendered prompt is dispatched as a single user message through the
    ``call_llm_direct`` ephemeral-session pipeline — the returned task call
    is auto-awaited by the scheduler, so the LLM receives the actual result
    content rather than just a task id.

    Args:
        _session: Bound session (required for dispatch).
        name: Template name.
        variables: Object mapping variable names to values, e.g.
            ``{"question": "..."}``.
        model: Model name (e.g. "gpt-4o"). None = caller's model, then
            Default Model.

    Returns:
        The dispatched AgentTaskCall on success (resolves to the
        ``call_llm_direct`` result dict via auto-await).
        ``(False, {"error": str})`` on invalid input or dispatch failure.
    """
    if _session is None:
        return (False, {"error": "No session available for dispatch."})
    if not name or not str(name).strip():
        return (False, {"error": "name is required."})
    try:
        # render_template_by_name normalizes variables (dict, or a JSON/YAML
        # string encoding one) — never pre-convert here, dict("...") would
        # raise a confusing error on string input.
        template, rendered = render_template_by_name(
            _session_pk(_session), str(name).strip(), variables
        )
    except TemplateError as exc:
        return (False, {"error": str(exc)})
    except Exception as exc:
        return (False, {"error": str(exc)})
    try:
        task = _session.get_task("call_llm_direct")
        if task is None:
            return (False, {"error": "Task 'call_llm_direct' is not available for this session."})
        return task.delay(
            messages=[{"role": "user", "content": rendered}],
            model_name=model,
        )
    except Exception as exc:
        return (False, {"error": f"Failed to dispatch template execution: {exc}"})



