"""Session-private ad-hoc tools — database-backed, wrapper-dispatched.

Each session's *current* tool is a ``SessionAdhocTool`` link row
``(session, name, version)``; every save mints a new immutable
``AdhocToolVersion`` row pointing at content-addressed ``GenericContent``
(no session FK — identical code dedupes across sessions) and moves only
the writer's link.  Forks inherit the parent's links (see
:func:`inherit_adhoc_tools`); deletes remove the link row only, leaving
version rows as the audit trail (author, timestamp, source).

The tool source is scanned once at write time (same Python guardrails as
the ``execution.python`` tool).  Reads never re-scan: version rows are
immutable, so nothing can change behind the wrapper's back.

All functions take the bound session wrapper (duck-typed: ``.model.pk``,
``.workspace``, ``.agent``) except
:func:`inherit_adhoc_tools`, which takes raw session pks.  All return
``(bool, dict)`` for the ``adhoc_*`` tools in
``.agentone/scripts/adhoc/adhoc.py``.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from django.db import IntegrityError, transaction

#: Cap on live tools per session — bounds DB rows and LLM list context.
MAX_ADHOC_TOOLS = 20

#: Cap on one tool's source bytes.
MAX_SOURCE_BYTES = 65536

#: Shorter than the 300s permanent-tool default — ad-hoc helpers are small.
CALL_TIMEOUT_SECONDS = 60

#: Mirrors ``config/settings.py`` TERMINAL_MAX_OUTPUT_CHARS.
MAX_OUTPUT_CHARS = 20000

#: Same strictness as ``execution/python.py`` — ``ask`` means block here
#: (there is no approval card in the ad-hoc flow; rejection carries reason).
ASK_THRESHOLD = 90

_TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,40}$")

#: Best-effort literal cross-session reference detector.  Static path-target
#: analysis (``check_python_paths``) is the real gate; this catches the
#: obvious ``sessions/<other_pk>`` string before it gets that far.
_SESSIONS_REF_RE = re.compile(r"sessions[/\\](\d+)")


# ---------------------------------------------------------------------------
# Session introspection (duck-typed: works with the runtime Session wrapper
# and with the light stub sessions used in tests)
# ---------------------------------------------------------------------------

def _session_pk(session: Any) -> int | None:
    model = getattr(session, "model", None)
    if model is not None:
        pk = getattr(model, "pk", None)
        if isinstance(pk, int):
            return pk
    for attr in ("pk", "session_pk"):
        pk = getattr(session, attr, None)
        if isinstance(pk, int):
            return pk
    return None


def _workspace_cwd(session: Any, fallback: str = "") -> str:
    workspace = getattr(session, "workspace", None)
    path = getattr(workspace, "path", None) if workspace is not None else None
    if path:
        try:
            resolved = Path(path).resolve()
            if resolved.is_dir():
                return str(resolved)
        except OSError:
            pass
    return fallback or os.getcwd()


def _policy(session: Any) -> Any:
    from runtime.workspace_access import resolve_policy

    try:
        return resolve_policy(session)
    except Exception:  # pylint: disable=broad-exception-caught
        return None


# ---------------------------------------------------------------------------
# Validation / scanning (unchanged from the filesystem era — all operate on
# source text before it is stored)
# ---------------------------------------------------------------------------

def validate_tool_name(name: Any) -> str | None:
    """Return an error message when *name* is not a legal tool name."""
    if not isinstance(name, str) or not _TOOL_NAME_RE.match(name):
        return (
            "Invalid tool name. Use 3-41 chars: lowercase letter first, "
            "then lowercase letters, digits, or underscore "
            "(use underscores, not hyphens)."
        )
    return None


def _coerce_dict_arg(value: Any, arg: str) -> tuple[dict | None, str | None]:
    """Accept a dict or a JSON-encoded dict string (LLMs often stringify).

    Returns ``(coerced_or_None, error)`` — ``None`` value stays ``None``
    (means "absent"); anything else that is not a JSON object is an error.
    """
    if value is None:
        return None, None
    if isinstance(value, dict):
        return value, None
    if isinstance(value, str):
        if not value.strip():
            return None, None
        try:
            parsed = json.loads(value)
        except ValueError as exc:
            return None, (
                f"'{arg}' must be a JSON object. The text you sent is not "
                f"valid JSON: {exc}"
            )
        if not isinstance(parsed, dict):
            if parsed is None:
                return None, None
            return None, f"'{arg}' must be a JSON object."
        return parsed, None
    return None, f"'{arg}' must be a JSON object or null."


def _check_has_run(source: str) -> str | None:
    """Require a top-level ``def run``; return an error or None."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return f"Source has a syntax error: {exc}"
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "run":
            return None
    return "Source must define a top-level `def run(...)` function."


_INFER_ANNOTATION_TYPES = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "dict": "object",
    "list": "array",
}


def _infer_annotation_type(node: ast.expr | None) -> str:
    """Best-effort AST annotation -> params-schema type key.

    The stored schema subset has no unions, so ``Optional[X]`` / ``X | None``
    unwrap to ``X`` and anything else unrecognized falls back to ``string``
    (same fallback as the manifest loader for unannotated params).
    Never executes the source — pure ``ast`` inspection.
    """
    if node is None or isinstance(node, ast.Constant):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return _INFER_ANNOTATION_TYPES.get(node.value, "string")
        return "string"
    if isinstance(node, ast.Name):
        lowered = _INFER_ANNOTATION_TYPES.get(node.id)
        if lowered is not None:
            return lowered
        return _INFER_ANNOTATION_TYPES.get(node.id.lower(), "string")
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        arms = (node.left, node.right)
        non_none = [a for a in arms
                    if not (isinstance(a, ast.Constant) and a.value is None)]
        if len(non_none) == 1:
            return _infer_annotation_type(non_none[0])
        return "string"
    if isinstance(node, ast.Subscript):
        func = node.value
        fname = ""
        if isinstance(func, ast.Name):
            fname = func.id
        elif isinstance(func, ast.Attribute):
            fname = func.attr
        if fname in ("List", "list"):
            return "array"
        if fname in ("Dict", "dict"):
            return "object"
        if fname in ("Optional", "Union"):
            sl = node.slice
            elts = sl.elts if isinstance(sl, ast.Tuple) else [sl]
            non_none = [e for e in elts
                        if not (isinstance(e, ast.Constant) and e.value is None)]
            if len(non_none) == 1:
                return _infer_annotation_type(non_none[0])
        return "string"
    return "string"


def infer_params_schema(source: str) -> dict | None:
    """Derive a params-schema-subset from ``def run``'s signature (AST only).

    Every parameter maps to a property (defaults -> not required);
    ``**kwargs`` maps to ``additionalProperties: true``; ``*args`` is
    ignored since a kwargs dict cannot fill it. Returns ``None`` only
    when there is no ``run`` to inspect or the source does not parse —
    meaning "no validation".
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    func = next(
        (n for n in tree.body
         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "run"),
        None,
    )
    if func is None:
        return None
    pos_all = list(func.args.posonlyargs) + list(func.args.args)
    properties: dict[str, Any] = {}
    required: list[str] = []
    pos_default_from = len(pos_all) - len(func.args.defaults)
    for i, arg in enumerate(pos_all):
        properties[arg.arg] = {"type": _infer_annotation_type(arg.annotation)}
        if i < pos_default_from:
            required.append(arg.arg)
    for arg, default in zip(func.args.kwonlyargs, func.args.kw_defaults):
        properties[arg.arg] = {"type": _infer_annotation_type(arg.annotation)}
        if default is None:  # ast uses None for "no default" (and for =None)
            required.append(arg.arg)
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "required": required,
    }
    if func.args.kwarg is not None:
        schema["additionalProperties"] = True
    return schema


def _scan_source(source: str, policy: Any, own_pk: int | None,
                 label: str = "Ad-hoc tool") -> str | None:
    """Static safety scan.  Returns a block message or None to allow."""
    from runtime.guardrails import check_python_command, check_python_paths

    try:
        verdict = check_python_command(source, ask_threshold=ASK_THRESHOLD)
    except Exception:  # pylint: disable=broad-exception-caught
        verdict = None
    if verdict is not None and verdict.action == "ask":
        return (
            f"{label} blocked by Python safety guardrail.\n"
            f"Reason: {verdict.reason}\n"
            f"Risk: {verdict.level} (score: {verdict.score})"
        )
    if policy is not None:
        try:
            path_verdict = check_python_paths(source, policy)
        except Exception:  # pylint: disable=broad-exception-caught
            path_verdict = None
        if path_verdict is not None and path_verdict.action == "deny":
            return (
                f"{label} blocked by workspace access policy.\n"
                f"Reason: {path_verdict.reason}"
            )
    if own_pk is not None:
        for other in _SESSIONS_REF_RE.findall(source):
            if other != str(own_pk):
                return (
                    f"{label} blocked: it references another session's "
                    f"private storage (sessions/{other}). Session-private "
                    "code may only touch its own session folder."
                )
    return None


def _iter_param_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_param_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_param_strings(item)


def _looks_like_abs_path(value: str) -> bool:
    return value.startswith(("/", "~", "$HOME", "${HOME}"))


def _check_param_paths(params: Any, policy: Any) -> str | None:
    """Deny absolute-looking param strings the workspace policy denies."""
    if policy is None or not isinstance(params, (dict, list)):
        return None
    from runtime.workspace_access import evaluate

    for candidate in _iter_param_strings(params):
        if not _looks_like_abs_path(candidate):
            continue
        try:
            verdict = evaluate(policy, candidate, "write")
        except Exception:  # pylint: disable=broad-exception-caught
            continue
        if verdict.action == "deny":
            return (
                "Call blocked by workspace access policy.\n"
                f"Reason: {verdict.reason}\n"
                f"Path: {candidate}"
            )
    return None


_SIMPLE_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
}


def validate_params_schema(schema: Any) -> str | None:
    """Permissive structural check for the stored JSON params schema."""
    if schema is None:
        return None
    if not isinstance(schema, dict):
        return "params_schema must be a JSON object or null."
    if schema.get("type", "object") != "object":
        return "params_schema type must be 'object'."
    props = schema.get("properties", {})
    if not isinstance(props, dict):
        return "params_schema.properties must be an object."
    for prop, spec in props.items():
        if not isinstance(spec, dict) or spec.get("type") not in _SIMPLE_TYPES:
            return (
                f"params_schema.properties.{prop}.type must be one of "
                f"{sorted(_SIMPLE_TYPES)}."
            )
    required = schema.get("required", [])
    if not isinstance(required, list) or any(not isinstance(r, str) for r in required):
        return "params_schema.required must be a list of strings."
    return None


def validate_params_against_schema(params: Any, schema: Any) -> str | None:
    """Minimal JSON-schema-subset enforcement (object/properties/required)."""
    if schema is None:
        return None
    if not isinstance(params, dict):
        return "params must be a JSON object."
    properties = schema.get("properties", {})
    for missing in schema.get("required", []):
        if missing not in params:
            return f"Missing required param: '{missing}'."
    for key, value in params.items():
        spec = properties.get(key)
        if spec is None:
            continue
        expected = _SIMPLE_TYPES[spec["type"]]
        if spec["type"] == "integer" and isinstance(value, bool):
            return f"Param '{key}' must be integer."
        if not isinstance(value, expected):
            return f"Param '{key}' must be {spec['type']}."
    return None


# ---------------------------------------------------------------------------
# CRUD + call
# ---------------------------------------------------------------------------

def _not_found(name: str) -> tuple[bool, dict]:
    return (False, {
        "status": "error",
        "message": (
            f"No ad-hoc tool named '{name}'. Use adhoc_list to see this "
            "session's tools and adhoc_create to make one."
        ),
    })


def _mint_version(session_pk: int, name: str, source: str, description: str,
                  params_schema: dict | None, source_label: str,
                  schema_inferred: bool = False):
    """Store *source* content-addressed and mint an immutable version row."""
    from server.models.adhoc_tool import AdhocToolVersion
    from server.models.content import GenericContent

    content = GenericContent.from_text(source)
    return AdhocToolVersion.objects.create(
        content=content,
        name=name,
        description=description or "",
        params_schema=params_schema,
        created_by_session_id=session_pk,
        source=source_label,
        schema_inferred=schema_inferred,
    )


def create_adhoc_tool(
    session: Any,
    name: str,
    source: str,
    description: str = "",
    params_schema: Any = None,
    source_label: str = "tool",
) -> tuple[bool, dict]:
    """Create one session-private helper (fails if *name* is taken)."""
    from server.models.adhoc_tool import SessionAdhocTool

    err = validate_tool_name(name)
    if err:
        return (False, {"status": "error", "message": err})
    if not isinstance(source, str) or not source.strip():
        return (False, {"status": "error", "message": "source must be non-empty Python code."})
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        return (False, {
            "status": "error",
            "message": f"source exceeds {MAX_SOURCE_BYTES} bytes.",
        })
    params_schema, schema_err = _coerce_dict_arg(params_schema, "params_schema")
    if schema_err:
        return (False, {"status": "error", "message": schema_err})
    schema_err = validate_params_schema(params_schema)
    if schema_err:
        return (False, {"status": "error", "message": schema_err})
    explicit_schema = params_schema is not None
    if not explicit_schema:
        # Like any other tool, the signature declares the params: infer
        # the schema from `def run` so callers are validated without the
        # author writing params_schema by hand.
        params_schema = infer_params_schema(source)
    own_pk = _session_pk(session)
    if own_pk is None:
        return (False, {"status": "error", "message": "Cannot determine owning session."})

    has_run_err = _check_has_run(source)
    if has_run_err:
        return (False, {"status": "error", "message": has_run_err})
    block = _scan_source(source, _policy(session), own_pk)
    if block:
        return (False, {"status": "error", "message": block})

    if SessionAdhocTool.objects.filter(session_id=own_pk, name=name).exists():
        return (False, {
            "status": "error",
            "message": f"Ad-hoc tool '{name}' already exists. Use adhoc_update to change it.",
        })
    if SessionAdhocTool.objects.filter(session_id=own_pk).count() >= MAX_ADHOC_TOOLS:
        return (False, {
            "status": "error",
            "message": f"Tool limit reached ({MAX_ADHOC_TOOLS} per session). Delete one first.",
        })

    try:
        with transaction.atomic():
            version = _mint_version(own_pk, name, source, description or "",
                                    params_schema, source_label,
                                    schema_inferred=not explicit_schema)
            SessionAdhocTool.objects.create(
                session_id=own_pk, name=name, version=version
            )
    except IntegrityError:
        # Lost a race with another create of the same name.
        return (False, {
            "status": "error",
            "message": f"Ad-hoc tool '{name}' already exists. Use adhoc_update to change it.",
        })
    result: dict[str, Any] = {"status": "success", "name": name, "version": version.pk}
    if not explicit_schema and params_schema is not None:
        result["schema_inferred"] = True
    return (True, result)


def list_adhoc_tools(session: Any) -> tuple[bool, dict]:
    """List this session's ad-hoc tools (metadata only, no source)."""
    from server.models.adhoc_tool import SessionAdhocTool

    own_pk = _session_pk(session)
    if own_pk is None:
        return (False, {"status": "error", "message": "Cannot determine owning session."})
    links = (
        SessionAdhocTool.objects.filter(session_id=own_pk)
        .select_related("version")
        .order_by("name")
    )
    return (True, {"status": "success", "tools": [
        {
            "name": link.name,
            "description": link.version.description,
            "version": link.version.pk,
            "updated_at": link.updated_at.isoformat(),
        }
        for link in links
    ]})


def read_adhoc_tool(session: Any, name: str) -> tuple[bool, dict]:
    """Return one tool's source plus metadata (for debug/iterate)."""
    from server.models.adhoc_tool import SessionAdhocTool

    err = validate_tool_name(name)
    if err:
        return (False, {"status": "error", "message": err})
    own_pk = _session_pk(session)
    if own_pk is None:
        return (False, {"status": "error", "message": "Cannot determine owning session."})
    try:
        link = (
            SessionAdhocTool.objects.select_related("version__content").get(
                session_id=own_pk, name=name
            )
        )
    except SessionAdhocTool.DoesNotExist:
        return _not_found(name)
    version = link.version
    return (True, {
        "status": "success",
        "name": name,
        "source": version.content.get(),
        "meta": {
            "description": version.description,
            "params_schema": version.params_schema,
            "version": version.pk,
            "created_at": version.created_at.isoformat(),
            "updated_at": link.updated_at.isoformat(),
        },
    })


def update_adhoc_tool(
    session: Any,
    name: str,
    source: str | None = None,
    description: str | None = None,
    params_schema: Any = None,
    _clear_schema: bool = False,
    source_label: str = "tool",
) -> tuple[bool, dict]:
    """Update source and/or metadata (mints a new version, moves this link).

    Saving content identical to the current version is a no-op (no new
    version row).  Only the writer's link moves — siblings and forks keep
    theirs.
    """
    from server.models.adhoc_tool import SessionAdhocTool

    err = validate_tool_name(name)
    if err:
        return (False, {"status": "error", "message": err})
    own_pk = _session_pk(session)
    if own_pk is None:
        return (False, {"status": "error", "message": "Cannot determine owning session."})

    if source is not None:
        if not isinstance(source, str) or not source.strip():
            return (False, {"status": "error", "message": "source must be non-empty Python code."})
        if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
            return (False, {
                "status": "error",
                "message": f"source exceeds {MAX_SOURCE_BYTES} bytes.",
            })
        has_run_err = _check_has_run(source)
        if has_run_err:
            return (False, {"status": "error", "message": has_run_err})
        block = _scan_source(source, _policy(session), own_pk)
        if block:
            return (False, {"status": "error", "message": block})
    new_schema: Any = None
    schema_mode = "auto"
    if _clear_schema:
        schema_mode = "clear"
    elif params_schema is not None:
        new_schema, schema_err = _coerce_dict_arg(params_schema, "params_schema")
        if schema_err:
            return (False, {"status": "error", "message": schema_err})
        schema_err = validate_params_schema(new_schema)
        if schema_err:
            return (False, {"status": "error", "message": schema_err})
        schema_mode = "explicit"
    inferred_now = False

    try:
        with transaction.atomic():
            try:
                link = (
                    SessionAdhocTool.objects.select_for_update()
                    .select_related("version__content")
                    .get(session_id=own_pk, name=name)
                )
            except SessionAdhocTool.DoesNotExist:
                return (False, {
                    "status": "error",
                    "message": f"No ad-hoc tool named '{name}'. Use adhoc_create first.",
                })
            current = link.version
            eff_source = source if source is not None else current.content.get()
            eff_description = description if description is not None else current.description
            eff_inferred = current.schema_inferred
            if schema_mode == "auto":
                if source is not None and (current.schema_inferred
                                           or current.params_schema is None):
                    # Stored schema was inferred (or absent): refresh it from
                    # the new signature. An explicit schema is never
                    # clobbered by a source-only update.
                    new_schema = infer_params_schema(eff_source)
                    eff_inferred = True
                    inferred_now = new_schema is not None
                else:
                    new_schema = "KEEP"  # sentinel: leave stored schema alone
            elif schema_mode == "clear":
                eff_inferred = False
            else:  # explicit
                eff_inferred = False
            eff_schema = current.params_schema if new_schema == "KEEP" else new_schema
            from server.models.content import GenericContent

            if (GenericContent.from_text(eff_source).pk == current.content_id
                    and eff_description == current.description
                    and eff_schema == current.params_schema
                    and eff_inferred == current.schema_inferred):
                return (True, {"status": "success", "name": name,
                               "version": current.pk, "unchanged": True})
            version = _mint_version(own_pk, name, eff_source, eff_description,
                                    eff_schema, source_label,
                                    schema_inferred=eff_inferred)
            link.version = version
            link.save(update_fields=["version"])
    except IntegrityError as exc:
        return (False, {"status": "error", "message": f"Could not update tool: {exc}"})
    result = {"status": "success", "name": name, "version": version.pk}
    if inferred_now:
        result["schema_inferred"] = True
    return (True, result)


def delete_adhoc_tool(session: Any, name: str) -> tuple[bool, dict]:
    """Delete one session ad-hoc tool (removes the link row only).

    Version rows stay as the audit trail; no new session version is
    created — tool state is working state, not session configuration.
    """
    from server.models.adhoc_tool import SessionAdhocTool

    err = validate_tool_name(name)
    if err:
        return (False, {"status": "error", "message": err})
    own_pk = _session_pk(session)
    if own_pk is None:
        return (False, {"status": "error", "message": "Cannot determine owning session."})
    deleted, _ = SessionAdhocTool.objects.filter(
        session_id=own_pk, name=name
    ).delete()
    if not deleted:
        return _not_found(name)
    return (True, {"status": "success", "name": name})


def inherit_adhoc_tools(parent_session_pk: int | str, child_session_pk: int | str) -> int:
    """Copy a parent session's ad-hoc tool links to a fork (copy-on-write).

    Called from ``AgentVersionModel.get_or_create_session`` for newly
    created sessions only — no version rows are minted, so parent and fork
    share history until the fork first saves.  Returns the link count.
    """
    from server.models.adhoc_tool import SessionAdhocTool

    rows = list(
        SessionAdhocTool.objects.filter(session_id=parent_session_pk).values_list(
            "name", "version_id"
        )
    )
    if not rows:
        return 0
    SessionAdhocTool.objects.bulk_create(
        [
            SessionAdhocTool(
                session_id=child_session_pk, name=name, version_id=version_id
            )
            for name, version_id in rows
        ],
        ignore_conflicts=True,
    )
    return len(rows)


# ---------------------------------------------------------------------------
# Subprocess runner (embedded source — the tool source lives in the DB now,
# so it is materialized to a temp file per call; crashing ad-hoc code can
# never take down the Celery worker)
# ---------------------------------------------------------------------------

_RUNNER_SOURCE = '''\
import importlib.util
import json
import sys
import traceback

def _load(tool_path):
    spec = importlib.util.spec_from_file_location("_adhoc_tool", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def main():
    tool_path = sys.argv[1]
    payload = json.loads(sys.stdin.read() or "{}")
    params = payload.get("params", {})
    try:
        module = _load(tool_path)
    except Exception:
        print(json.dumps({"ok": False, "error": traceback.format_exc()}))
        return 1
    func = getattr(module, "run", None)
    if func is None:
        print(json.dumps({"ok": False, "error": "No top-level run() defined."}))
        return 1
    try:
        if not isinstance(params, dict):
            raise TypeError(
                "Tool params must be a JSON object, "
                f"got {type(params).__name__}."
            )
        # Normal-tool style: run(**params). A TypeError here is a genuine
        # signature mismatch and surfaces as-is — there is no legacy
        # whole-dict fallback.
        result = func(**params)
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], bool):
            ok, data = result
            print(json.dumps({"ok": bool(ok), "result": data}))
        else:
            print(json.dumps({"ok": True, "result": result}))
        return 0
    except Exception:
        print(json.dumps({"ok": False, "error": traceback.format_exc()}))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
'''


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) > limit:
        return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"
    return text


def _execute_isolated_source(source: str, params: Any, cwd: str) -> tuple[bool, dict]:
    """Run *source* in an isolated subprocess and return ``(ok, payload)``.

    Shared by ad-hoc tool calls and workflow inline-function steps: the
    source is materialized to a temp file next to the runner, executed
    with ``params`` on stdin, and the ``{"ok", "result"/"error"}``
    envelope is converted to a namespaced payload —
    ``{status, return_code, result}`` on success — so tool output never
    collides with the envelope keys.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as src_file:
        src_file.write(source)
        tool_path = src_file.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as runner_file:
        runner_file.write(_RUNNER_SOURCE)
        runner_path = runner_file.name
    try:
        proc = subprocess.run(
            [sys.executable, runner_path, tool_path],
            input=json.dumps({"params": params}),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=CALL_TIMEOUT_SECONDS,
            env={**os.environ},
        )
    except subprocess.TimeoutExpired:
        return (False, {
            "status": "error",
            "stdout": "",
            "stderr": f"Tool timed out after {CALL_TIMEOUT_SECONDS} seconds.",
            "return_code": -1,
        })
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return (False, {
            "status": "error",
            "stdout": "",
            "stderr": f"Tool failed to start: {exc}",
            "return_code": -1,
        })
    finally:
        for tmp in (tool_path, runner_path):
            try:
                os.unlink(tmp)
            except OSError:
                pass

    stdout, stderr = _truncate(proc.stdout or ""), _truncate(proc.stderr or "")
    try:
        envelope = json.loads(stdout) if stdout.strip() else {}
    except ValueError:
        return (False, {
            "status": "error",
            "stdout": stdout,
            "stderr": stderr or "Tool printed non-JSON output.",
            "return_code": proc.returncode,
        })
    if not envelope.get("ok"):
        detail = envelope.get("error", envelope.get("result", "Tool failed."))
        payload: dict[str, Any] = {
            "status": "error",
            "stdout": "",
            "stderr": _truncate(str(detail)),
            "return_code": proc.returncode or -1,
        }
        if "result" in envelope:
            payload["result"] = envelope["result"]
        return (False, payload)
    success: dict[str, Any] = {
        "status": "success",
        "return_code": proc.returncode,
        "result": envelope.get("result"),
    }
    if stderr:
        success["stderr"] = stderr
    return (True, success)


def build_inline_module(body: str, arg_names: list) -> str:
    """Wrap a workflow inline-function *body* as an executable module.

    The body is a function body (bare ``return`` allowed): argument names
    arrive as variables, e.g. body ``"foo = content + 'bar'\\nreturn foo"``
    with ``arg_names=["content"]`` becomes ``def run(content): ...``.
    Raises :class:`ValueError` when the body is empty, an argument name
    is not a valid parameter name, or the wrapped module does not parse.
    """
    import keyword
    import textwrap

    if not isinstance(body, str) or not body.strip():
        raise ValueError("Inline function body must be non-empty Python code.")
    clean: list[str] = []
    for name in arg_names:
        if not isinstance(name, str) or not name.isidentifier() \
                or keyword.iskeyword(name):
            raise ValueError(
                f"Inline function argument {name!r} is not a valid Python "
                "parameter name (args become run()'s parameter names)."
            )
        clean.append(name)
    module = f"def run({', '.join(clean)}):\n{textwrap.indent(body, '    ')}\n"
    try:
        tree = ast.parse(module)
    except SyntaxError as exc:
        raise ValueError(f"Inline function has a syntax error: {exc}") from exc
    if not any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.name == "run" for n in tree.body):
        raise ValueError("Inline function body did not wrap cleanly.")
    return module


def run_inline_function(session: Any, body: str, params: Any = None) -> tuple[bool, dict]:
    """Execute one ephemeral workflow inline-function body.

    Same isolation as ad-hoc tools (subprocess, 60s timeout): the body is
    wrapped via :func:`build_inline_module` with the params-dict keys as
    parameter names, then run through the shared executor. Returns the
    namespaced ``(ok, {status, return_code, result})`` payload, so inline
    steps behave exactly like tool calls downstream (``path``, ``when``,
    fail-fast).
    """
    params, params_err = _coerce_dict_arg(params, "params")
    if params_err:
        return (False, {"status": "error", "message": params_err})
    if params is None:
        params = {}
    path_block = _check_param_paths(params, _policy(session))
    if path_block:
        return (False, {"status": "error", "message": path_block})
    try:
        module = build_inline_module(body, sorted(params.keys()))
    except ValueError as exc:
        return (False, {"status": "error", "message": str(exc)})
    return _execute_isolated_source(module, params, _workspace_cwd(session))


def call_adhoc_tool(session: Any, name: str, params: Any = None) -> tuple[bool, dict]:
    """Execute one ad-hoc tool in a subprocess.

    The versioned source is immutable, so — unlike the filesystem era —
    no re-scan is needed: every write was scanned before it was stored.
    ``params`` are validated against the stored schema (if any) and
    absolute-looking path strings are checked against the workspace policy.
    """
    from server.models.adhoc_tool import SessionAdhocTool

    err = validate_tool_name(name)
    if err:
        return (False, {"status": "error", "message": err})
    own_pk = _session_pk(session)
    if own_pk is None:
        return (False, {"status": "error", "message": "Cannot determine owning session."})
    params, params_err = _coerce_dict_arg(params, "params")
    if params_err:
        return (False, {"status": "error", "message": params_err})
    if params is None:
        params = {}

    try:
        link = (
            SessionAdhocTool.objects.select_related("version__content").get(
                session_id=own_pk, name=name
            )
        )
    except SessionAdhocTool.DoesNotExist:
        return _not_found(name)
    version = link.version
    source = version.content.get()
    if not isinstance(source, str) or _check_has_run(source):
        return (False, {
            "status": "error",
            "message": "Stored tool source is invalid. Delete and re-create it.",
        })

    schema_err = validate_params_against_schema(params, version.params_schema)
    if schema_err:
        return (False, {"status": "error", "message": schema_err})
    path_block = _check_param_paths(params, _policy(session))
    if path_block:
        return (False, {"status": "error", "message": path_block})

    cwd = _workspace_cwd(session)
    return _execute_isolated_source(source, params, cwd)
