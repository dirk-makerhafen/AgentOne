"""Session-private dynamic workflows — database-backed, wrapper-dispatched.

Each session's *current* workflow is a ``SessionWorkflow`` link row
``(session, name, version)``; every save mints a new immutable
``WorkflowVersion`` row pointing at content-addressed ``GenericContent``
(no session FK — identical definitions dedupe across sessions) and moves
only the writer's link.  Forks inherit the parent's links (see
:func:`inherit_workflows`); deletes remove the link row only, leaving
version rows as the audit trail (author, timestamp, source).

A workflow is an ordered list of steps.  Each step has an ``id``, exactly
one action (a single tool call, a ``group`` of parallel tool calls, or a
``map`` fan-out over a list), and an optional ``when`` conditional.  See
``docs/workflows.md`` for the DSL, the execution design, and the
explicit V1 exclusions.

Definitions are validated once at write time (:func:`validate_workflow`
raises :class:`WorkflowError` on any problem).  Reads never re-validate:
version rows are immutable, so nothing can change behind the runner.

Execution is non-blocking and chained (no worker ever blocks on
``get_result``): ``run_workflow`` pins the version pk and dispatches the
``workflow_step`` task; each step dispatches its tool call(s) plus a
continuation task (``workflow_advance`` / ``workflow_join`` /
``workflow_fanout`` / ``workflow_mapjoin``) that takes the dispatched
call(s) as arguments, so the scheduler parks it in ``WAITING_DEPENDENCY``
until they end.  Continuations return the next continuation call, which
the framework flattens (same re-pointing as tail-recursive chains), so a
run keeps a constant wait depth.  Run state travels in ``run_ctx`` (plain
JSON: version pk, inputs, visited stack, recorded call pks) — there is no
run table in V1.  A failed step fails the workflow by propagation: the
waiting continuation is cancelled and the error surfaces through the
normal failure path.

All CRUD functions take raw session pks and raise :class:`WorkflowError`;
the thin bound wrappers in ``.agentone/scripts/workflow/`` convert to
``(bool, dict)``.  Execution functions take the bound session
(duck-typed: ``.get_tool`` / ``.get_task``) and return either the next
``AgentTaskCall`` (continue, auto-awaited) or a plain result envelope.
"""

from __future__ import annotations

import json
import re
from typing import Any

from django.db import IntegrityError, transaction
from jinja2 import BaseLoader, Environment, StrictUndefined, Undefined
from jinja2.nativetypes import NativeEnvironment

_JINJA_ENV = Environment(loader=BaseLoader(), undefined=StrictUndefined)

#: Deterministic native rendering for step args: a value that is exactly
#: one ``{{ ... }}`` expression evaluates to the expression's value with
#: its type preserved exactly (natives stay native, strings stay strings
#: — unlike ``NativeEnvironment``, no ``literal_eval`` guessing); mixed
#: text still renders to a string. ``StrictUndefined`` either way — typos
#: fail loudly.
_NATIVE_ENV = NativeEnvironment(loader=BaseLoader(), undefined=StrictUndefined)

#: Cap on live workflows per session — bounds DB rows and LLM list context.
MAX_WORKFLOWS = 20

#: Cap on one canonical definition's JSON bytes.
MAX_WORKFLOW_BYTES = 65536

#: Cap on steps per workflow.
MAX_STEPS = 32

#: One nested group level inside group branches / map consumers (no
#: map-in-map: nested fan-out would need recursive continuation waves).
MAX_NESTING = 2

#: Cap on a `when` predicate's characters.
MAX_WHEN_CHARS = 200

#: Default items per map wave; overflow loops through further waves.
MAX_PARALLEL_DEFAULT = 8

#: Hard cap on items per map wave.
MAX_PARALLEL_HARD = 32

#: Hard cap on total map items (bounds dispatched calls per step).
MAX_ITEMS = 32

#: Cap on one rendered argument string (guards the call-arguments JSON).
MAX_ARG_CHARS = 10240

#: Max nested-workflow composition depth (visited stack, cycle-guarded).
MAX_DEPTH = 3

#: Cap on one inline function body's bytes (the whole definition is still
#: bounded by MAX_WORKFLOW_BYTES; this keeps one step from eating it all).
MAX_FUNCTION_BYTES = 32768

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,40}$")
_STEP_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_STEP_REF_RE = re.compile(r"steps\.([A-Za-z_][A-Za-z0-9_]*)")

#: Best-effort literal cross-session reference detector, mirroring
#: ``runtime/adhoc_tools.py``.  The writer's own session pk is allowed
#: (scratch paths may name it); anything else is rejected at save time.
_SESSIONS_REF_RE = re.compile(r"sessions[/\\](\d+)")


class WorkflowError(ValueError):
    """Raised when a workflow definition, schema, or reference is invalid."""


# ---------------------------------------------------------------------------
# Name / shape validation (pure — no DB)
# ---------------------------------------------------------------------------

def validate_workflow_name(name: Any) -> str:
    """Return the canonical *name* or raise :class:`WorkflowError`."""
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise WorkflowError(
            "Invalid workflow name. Use 3-41 chars: lowercase letter first, "
            "then lowercase letters, digits, or underscore "
            f"(got {name!r})."
        )
    return name


def _coerce_dict_arg(value: Any, arg: str) -> dict:
    """Accept a dict or a JSON-encoded dict string (LLMs often stringify)."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        if not value.strip():
            return {}
        try:
            parsed = json.loads(value)
        except ValueError as exc:
            raise WorkflowError(
                f"'{arg}' must be a JSON object. The text you sent is not "
                f"valid JSON: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise WorkflowError(f"'{arg}' must be a JSON object.")
        return parsed
    raise WorkflowError(f"'{arg}' must be a JSON object or null.")


def _coerce_steps(steps: Any) -> list:
    """Accept a step list or a JSON string encoding one."""
    if isinstance(steps, str):
        try:
            steps = json.loads(steps)
        except ValueError as exc:
            raise WorkflowError(f"'steps' is not valid JSON: {exc}") from exc
    if not isinstance(steps, list):
        raise WorkflowError("'steps' must be a list of step mappings.")
    return steps


def _check_sessions_refs(value: Any, session_pk: int | None) -> None:
    """Reject literal ``sessions/<other_pk>`` references in static text."""
    if isinstance(value, str):
        for other in _SESSIONS_REF_RE.findall(value):
            if session_pk is None or other != str(session_pk):
                raise WorkflowError(
                    "Workflow blocked: it references another session's "
                    f"private storage (sessions/{other}). Workflows are "
                    "session-private and may only touch their own session "
                    "folder — pass paths via tool results instead."
                )
    elif isinstance(value, dict):
        for item in value.values():
            _check_sessions_refs(item, session_pk)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _check_sessions_refs(item, session_pk)


# ---------------------------------------------------------------------------
# `when` predicates (pure)
# ---------------------------------------------------------------------------

_WHEN_BINOPS = ("==", "!=", ">=", "<=", ">", "<", "contains", "not contains")
_WHEN_UNARY = ("succeeded", "failed", "is empty", "is not empty")


def _split_when(predicate: str) -> tuple[list[str], list[str]]:
    """Split ``a and b or c`` into ([a, b, c], ['and', 'or']). No parens.

    Quote-aware: ``and``/``or`` inside quoted literals does not split.
    """
    if "(" in predicate or ")" in predicate:
        raise WorkflowError(
            f"Invalid 'when' {predicate!r}: parentheses are not supported. "
            "Write one flat predicate with 'and'/'or'."
        )
    clauses, joins, buf = [], [], []
    token_re = re.compile(r"'[^']*'|\"[^\"]*\"|\s+(and|or)\s+|.")
    for match in token_re.finditer(predicate.strip()):
        word = match.group(1)
        if word is None:
            buf.append(match.group(0))  # quoted literal or plain char
            continue
        clauses.append("".join(buf).strip())
        joins.append(word)
        buf = []
    clauses.append("".join(buf).strip())
    if any(not c for c in clauses):
        raise WorkflowError(
            f"Invalid 'when' {predicate!r}: empty clause around 'and'/'or'."
        )
    return clauses, joins


def _parse_when_literal(token: str) -> Any:
    """Parse a predicate literal (quoted string, number, bool, null, []/{}).

    A bare word (e.g. ``high_priority`` in ``contains high_priority``) is
    treated as a string — quoting it is equivalent.
    """
    token = token.strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
        return token[1:-1]
    low = token.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in ("null", "none"):
        return None
    if token in ("[]", "{}"):
        return [] if token == "[]" else {}
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.\-]*", token):
        return token
    raise WorkflowError(
        f"Invalid 'when' literal {token!r}: use a quoted string, number, "
        "boolean, null, [] or {} (or a bare word)."
    )


def _parse_when_clause(clause: str) -> dict:
    """Parse one ``<operand> <operator> [<literal>]`` clause structurally."""
    for unary in ("is not empty", "is empty", "succeeded", "failed"):
        if clause == unary or clause.endswith(" " + unary):
            operand = clause[: -len(unary)].strip() if clause != unary else ""
            if unary in ("succeeded", "failed") and not operand:
                raise WorkflowError(
                    f"Invalid 'when' clause {clause!r}: "
                    "'succeeded'/'failed' need a step, e.g. 'steps.fetch succeeded'."
                )
            return {"operand": operand, "op": unary, "literal": None}
    for op in ("not contains", "contains", "==", "!=", ">=", "<=", ">", "<"):
        pattern = r"^(.*?)\s+" + re.escape(op) + r"\s+(.+)$"
        match = re.match(pattern, clause)
        if match:
            operand, raw_literal = match.group(1).strip(), match.group(2).strip()
            if not operand:
                raise WorkflowError(f"Invalid 'when' clause {clause!r}: missing operand.")
            return {"operand": operand, "op": op, "literal": _parse_when_literal(raw_literal)}
    raise WorkflowError(
        f"Invalid 'when' clause {clause!r}: expected "
        "'<operand> <==, !=, >, >=, <, <=, contains, not contains> <literal>' "
        "or '<operand> <succeeded, failed, is empty, is not empty>'."
    )


def _validate_when_operand(operand: str, prior_ids: list[str], step_id: str) -> None:
    """Check a `when` operand names a prior step (static part only)."""
    if not operand:
        raise WorkflowError(
            f"Invalid 'when' on step {step_id!r}: missing operand."
        )
    match = re.fullmatch(r"steps\.([A-Za-z_][A-Za-z0-9_]*)(?:\..+)?", operand)
    if not match:
        raise WorkflowError(
            f"Invalid 'when' on step {step_id!r}: operand {operand!r} must "
            "look like 'steps.<id>' or 'steps.<id>.output...'."
        )
    ref = match.group(1)
    if ref not in prior_ids:
        known = ", ".join(prior_ids) if prior_ids else "(no prior steps)"
        raise WorkflowError(
            f"Invalid 'when' on step {step_id!r}: unknown or forward step "
            f"reference 'steps.{ref}'. Prior steps: {known}."
        )


def validate_when(predicate: Any, prior_ids: list[str], step_id: str) -> str:
    """Validate a `when` predicate; return the stripped string."""
    if not isinstance(predicate, str) or not predicate.strip():
        raise WorkflowError(f"Invalid 'when' on step {step_id!r}: must be a non-empty string.")
    predicate = predicate.strip()
    if len(predicate) > MAX_WHEN_CHARS:
        raise WorkflowError(
            f"Invalid 'when' on step {step_id!r}: exceeds {MAX_WHEN_CHARS} chars."
        )
    clauses, _joins = _split_when(predicate)
    for clause in clauses:
        parsed = _parse_when_clause(clause)
        _validate_when_operand(parsed["operand"], prior_ids, step_id)
    return predicate


def _resolve_operand_path(record: Any, dotted: str) -> Any:
    """Resolve ``output.status`` style paths inside a step record.

    Records look like ``{"output": ..., "count": N, "succeeded": bool}``.
    A trailing ``.count`` on a list resolves to its length.
    """
    current = record
    segments = dotted.split(".") if dotted else []
    for i, segment in enumerate(segments):
        if segment == "count" and i == len(segments) - 1 and isinstance(current, list):
            return len(current)
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        elif isinstance(current, list) and segment.isdigit() and int(segment) < len(current):
            current = current[int(segment)]
        else:
            return None
    return current


def _clause_is_true(parsed: dict, records: dict[str, dict]) -> bool:
    """Evaluate one parsed clause against step records (runtime)."""
    operand = parsed["operand"]
    match = re.fullmatch(r"steps\.([A-Za-z_][A-Za-z0-9_]*)(?:\.(.+))?", operand)
    if not match:
        return False
    record = records.get(match.group(1))
    if record is None:
        return False
    op = parsed["op"]
    if op == "succeeded":
        return bool(record.get("succeeded"))
    if op == "failed":
        return False  # failure cancels the chain before any `when` runs
    value = _resolve_operand_path(record, match.group(2) or "")
    if op == "is empty":
        return value is None or value == "" or value == [] or value == {}
    if op == "is not empty":
        return not (value is None or value == "" or value == [] or value == {})
    literal = parsed["literal"]
    try:
        if op == "==":
            return value == literal
        if op == "!=":
            return value != literal
        if op in (">", ">=", "<", "<="):
            if isinstance(value, bool) or isinstance(literal, bool):
                return False
            if isinstance(value, (int, float)) and isinstance(literal, (int, float)):
                return {
                    ">": value > literal,
                    ">=": value >= literal,
                    "<": value < literal,
                    "<=": value <= literal,
                }[op]
            if isinstance(value, str) and isinstance(literal, str):
                return {
                    ">": value > literal,
                    ">=": value >= literal,
                    "<": value < literal,
                    "<=": value <= literal,
                }[op]
            return False
        if op == "contains":
            if isinstance(value, str):
                return str(literal) in value
            if isinstance(value, (list, tuple)):
                return literal in value
            if isinstance(value, dict):
                return literal in value
            return False
        if op == "not contains":
            if isinstance(value, str):
                return str(literal) not in value
            if isinstance(value, (list, tuple)):
                return literal not in value
            if isinstance(value, dict):
                return literal not in value
            return True
    except Exception:  # pylint: disable=broad-exception-caught
        return False
    return False


def evaluate_when(predicate: str, records: dict[str, dict]) -> bool:
    """Evaluate a validated `when` predicate (left-to-right, no precedence)."""
    clauses, joins = _split_when(predicate)
    result = _clause_is_true(_parse_when_clause(clauses[0]), records)
    for join, clause in zip(joins, clauses[1:]):
        rhs = _clause_is_true(_parse_when_clause(clause), records)
        result = (result and rhs) if join == "and" else (result or rhs)
    return result


# ---------------------------------------------------------------------------
# Step / definition validation (pure)
# ---------------------------------------------------------------------------

def _check_template_refs(args: Any, prior_ids: list[str], step_id: str,
                         allow_item: bool) -> None:
    """Statically check ``{{ steps.* }}`` / ``{{ item }}`` references."""
    from jinja2 import meta as _jinja_meta

    def _check_string(text: str) -> None:
        try:
            tree = _JINJA_ENV.parse(text)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            raise WorkflowError(
                f"Invalid template on step {step_id!r}: {exc}"
            ) from exc
        declared = _jinja_meta.find_undeclared_variables(tree)
        unknown = declared - {"inputs", "steps", "item", "index"}
        if unknown:
            raise WorkflowError(
                f"Invalid template on step {step_id!r}: unknown variable(s) "
                f"{sorted(unknown)}. Use {{{{ inputs.* }}}}, "
                f"{{{{ steps.<id>.output }}}}"
                + (", {{ item }}/{{ index }}" if allow_item else "")
                + "."
            )
        if ("item" in declared or "index" in declared) and not allow_item:
            raise WorkflowError(
                f"Invalid template on step {step_id!r}: {{{{ item }}}}/"
                "{{ index }} are only available inside a map consumer."
            )
        for ref in _STEP_REF_RE.findall(text):
            if ref not in prior_ids:
                known = ", ".join(prior_ids) if prior_ids else "(no prior steps)"
                raise WorkflowError(
                    f"Invalid template on step {step_id!r}: unknown or "
                    f"forward step reference 'steps.{ref}'. "
                    f"Prior steps: {known}."
                )

    def _walk(value: Any) -> None:
        if isinstance(value, str):
            if "{{" in value:
                _check_string(value)
        elif isinstance(value, dict):
            for item in value.values():
                _walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                _walk(item)

    _walk(args)


def _validate_tool_call(spec: Any, prior_ids: list[str], where: str,
                        allow_item: bool, session_pk: int | None) -> dict:
    """Validate one ``{"tool": ..., "args"?: ...}`` invocation spec."""
    if not isinstance(spec, dict):
        raise WorkflowError(f"Invalid {where}: must be a mapping with 'tool'.")
    tool = spec.get("tool")
    if not isinstance(tool, str) or not tool.strip():
        raise WorkflowError(f"Invalid {where}: 'tool' must be a non-empty tool name.")
    args = spec.get("args", {})
    try:
        args = _coerce_dict_arg(args, f"{where}.args")
    except WorkflowError as exc:
        raise WorkflowError(f"Invalid {where}: {exc}") from exc
    _check_sessions_refs(args, session_pk)
    _check_template_refs(args, prior_ids, where, allow_item)
    return {"tool": tool.strip(), "args": args}


def _validate_function_call(spec: Any, prior_ids: list[str], where: str,
                            allow_item: bool, session_pk: int | None,
                            policy: Any = None) -> dict:
    """Validate one ``{"function": <body>, "args"?: ...}`` inline step.

    The body is a Python function *body* (bare ``return`` allowed): its
    ``args`` keys become the parameter names, so keys must be valid
    identifiers (step-arg keys are never templated — only values render).
    The body is guardrail-scanned and syntax-checked here, so bad code
    fails at save time, not mid-run.
    """
    from runtime.adhoc_tools import build_inline_module, _scan_source

    if not isinstance(spec, dict):
        raise WorkflowError(f"Invalid {where}: must be a mapping with 'function'.")
    body = spec.get("function")
    if not isinstance(body, str) or not body.strip():
        raise WorkflowError(f"Invalid {where}: 'function' must be non-empty Python code.")
    if len(body.encode("utf-8")) > MAX_FUNCTION_BYTES:
        raise WorkflowError(
            f"Invalid {where}: 'function' body exceeds {MAX_FUNCTION_BYTES} bytes."
        )
    args = spec.get("args", {})
    try:
        args = _coerce_dict_arg(args, f"{where}.args")
    except WorkflowError as exc:
        raise WorkflowError(f"Invalid {where}: {exc}") from exc
    import keyword

    for key in args:
        if not isinstance(key, str) or not key.isidentifier() \
                or keyword.iskeyword(key):
            raise WorkflowError(
                f"Invalid {where}: args key {key!r} is not a valid Python "
                "parameter name (inline function args become run()'s "
                "parameter names)."
            )
    _check_sessions_refs(body, session_pk)
    block = _scan_source(body, policy, session_pk,
                         label="Workflow inline function")
    if block:
        raise WorkflowError(block)
    _check_sessions_refs(args, session_pk)
    _check_template_refs(args, prior_ids, where, allow_item)
    try:
        build_inline_module(body, sorted(args.keys()))
    except ValueError as exc:
        raise WorkflowError(f"Invalid {where}: {exc}") from exc
    return {"function": body, "args": args}


def _validate_action(action: dict, prior_ids: list[str], where: str,
                     depth: int, allow_item: bool,
                     session_pk: int | None, policy: Any = None) -> dict:
    """Validate a group branch or map consumer action (tool/function/group)."""
    if not isinstance(action, dict):
        raise WorkflowError(f"Invalid {where}: must be a mapping.")
    if "map" in action:
        raise WorkflowError(
            f"Invalid {where}: nested 'map' is not supported in V1. "
            "Compose named sub-workflows via 'workflow_run' steps instead."
        )
    kinds = [k for k in ("tool", "function", "group") if k in action]
    if len(kinds) != 1:
        raise WorkflowError(
            f"Invalid {where}: use exactly one of 'tool'/'function'/'group'."
        )
    if "group" in action:
        if depth >= MAX_NESTING:
            raise WorkflowError(
                f"Invalid {where}: composite nesting exceeds {MAX_NESTING} levels."
            )
        branches = action["group"]
        if not isinstance(branches, list) or len(branches) < 2:
            raise WorkflowError(f"Invalid {where}: nested 'group' needs 2+ branches.")
        return {"group": [
            _validate_action(b, prior_ids, f"{where}.group[{i}]", depth + 1,
                             allow_item, session_pk, policy)
            for i, b in enumerate(branches)
        ]}
    if "function" in action:
        return _validate_function_call(action, prior_ids, where, allow_item,
                                        session_pk, policy)
    return _validate_tool_call(action, prior_ids, where, allow_item, session_pk)


def _validate_step(step: Any, index: int, prior_ids: list[str],
                   session_pk: int | None, policy: Any = None) -> dict:
    """Validate one top-level step; return its canonical form."""
    where = f"steps[{index}]"
    if not isinstance(step, dict):
        raise WorkflowError(f"Invalid {where}: must be a mapping.")
    step_id = step.get("id")
    if not isinstance(step_id, str) or not _STEP_ID_RE.match(step_id):
        raise WorkflowError(
            f"Invalid {where}: 'id' must be an identifier "
            f"(letters/digits/_, not starting with a digit), got {step_id!r}."
        )
    if step_id in prior_ids:
        raise WorkflowError(f"Invalid {where}: duplicate step id {step_id!r}.")
    actions = [k for k in ("tool", "function", "group", "map") if k in step]
    if len(actions) != 1:
        raise WorkflowError(
            f"Invalid step {step_id!r}: use exactly one of "
            "'tool', 'function', 'group' or 'map'."
        )
    canonical: dict[str, Any] = {"id": step_id}
    if "when" in step and step["when"] is not None:
        canonical["when"] = validate_when(step["when"], prior_ids, step_id)
    kind = actions[0]
    if kind == "tool":
        canonical.update(_validate_tool_call(
            {"tool": step["tool"], "args": step.get("args", {})},
            prior_ids, f"step {step_id!r}", False, session_pk,
        ))
    elif kind == "function":
        canonical.update(_validate_function_call(
            {"function": step["function"], "args": step.get("args", {})},
            prior_ids, f"step {step_id!r}", False, session_pk, policy,
        ))
    elif kind == "group":
        branches = step["group"]
        if not isinstance(branches, list) or len(branches) < 2:
            raise WorkflowError(
                f"Invalid step {step_id!r}: 'group' needs a list of 2+ branches."
            )
        canonical["group"] = [
            _validate_action(b, prior_ids, f"step {step_id!r}.group[{i}]",
                             1, False, session_pk, policy)
            for i, b in enumerate(branches)
        ]
    else:  # map
        spec = step["map"]
        if not isinstance(spec, dict):
            raise WorkflowError(f"Invalid step {step_id!r}: 'map' must be a mapping.")
        producer = spec.get("producer")
        if isinstance(producer, dict) and "step" in producer and "tool" not in producer:
            ref = producer["step"]
            if ref not in prior_ids:
                known = ", ".join(prior_ids) if prior_ids else "(no prior steps)"
                raise WorkflowError(
                    f"Invalid step {step_id!r}: map producer references unknown "
                    f"or forward step {ref!r}. Prior steps: {known}."
                )
            path = producer.get("path", "")
            if not isinstance(path, str):
                raise WorkflowError(
                    f"Invalid step {step_id!r}: map producer 'path' must be a string."
                )
            canonical_producer: dict[str, Any] = {"step": ref}
            if path:
                canonical_producer["path"] = path
        elif isinstance(producer, dict) and "tool" in producer:
            canonical_producer = {"call": _validate_tool_call(
                producer, prior_ids, f"step {step_id!r}.map.producer",
                False, session_pk,
            )}
        elif isinstance(producer, dict) and "function" in producer:
            canonical_producer = {"function": _validate_function_call(
                producer, prior_ids, f"step {step_id!r}.map.producer",
                False, session_pk, policy,
            )}
        else:
            raise WorkflowError(
                f"Invalid step {step_id!r}: map 'producer' must be "
                "{'step': '<prior_id>'} or an inline {'tool': ..., 'args'?} "
                "call or {'function': ..., 'args'?}."
            )
        consumer = spec.get("consumer")
        if not isinstance(consumer, dict):
            raise WorkflowError(
                f"Invalid step {step_id!r}: map 'consumer' must be a mapping."
            )
        canonical_consumer = _validate_action(
            consumer, prior_ids, f"step {step_id!r}.map.consumer",
            1, True, session_pk, policy,
        )
        max_parallel = spec.get("max_parallel", MAX_PARALLEL_DEFAULT)
        if not isinstance(max_parallel, int) or isinstance(max_parallel, bool):
            raise WorkflowError(
                f"Invalid step {step_id!r}: map 'max_parallel' must be an integer."
            )
        max_parallel = min(max(max_parallel, 1), MAX_PARALLEL_HARD)
        item_var = spec.get("item_var", "item")
        if item_var != "item":
            raise WorkflowError(
                f"Invalid step {step_id!r}: custom 'item_var' is not supported "
                "in V1 — use {{ item }} and {{ index }}."
            )
        canonical["map"] = {
            "producer": canonical_producer,
            "consumer": canonical_consumer,
            "max_parallel": max_parallel,
        }
    return canonical


def validate_workflow(name: Any, steps: Any, description: Any = "",
                      inputs_schema: Any = None,
                      session_pk: int | None = None,
                      policy: Any = None) -> dict:
    """Validate a workflow definition; return its canonical dict.

    Raises :class:`WorkflowError` on any problem.  Pass *session_pk* to
    enable the literal cross-session path check (the writer's own pk is
    allowed, other pks are rejected); pass *policy* for the workspace
    path check on inline function bodies.
    """
    validate_workflow_name(name)
    if description is None:
        description = ""
    if not isinstance(description, str):
        raise WorkflowError("'description' must be a string.")
    schema = _coerce_dict_arg(inputs_schema, "inputs_schema")
    if schema:
        from runtime.adhoc_tools import validate_params_schema

        schema_err = validate_params_schema(schema)
        if schema_err:
            raise WorkflowError(f"Invalid inputs_schema: {schema_err}")
    step_list = _coerce_steps(steps)
    if not step_list:
        raise WorkflowError("'steps' must be a non-empty list.")
    if len(step_list) > MAX_STEPS:
        raise WorkflowError(f"'steps' exceeds the {MAX_STEPS}-step cap.")
    canonical_steps = []
    prior_ids: list[str] = []
    for i, raw in enumerate(step_list):
        canonical = _validate_step(raw, i, prior_ids, session_pk, policy)
        canonical_steps.append(canonical)
        prior_ids.append(canonical["id"])
    canonical = {
        "name": name,
        "description": description,
        "inputs_schema": schema,
        "steps": canonical_steps,
    }
    size = len(json.dumps(canonical, sort_keys=True).encode("utf-8"))
    if size > MAX_WORKFLOW_BYTES:
        raise WorkflowError(
            f"Workflow definition exceeds {MAX_WORKFLOW_BYTES} bytes ({size})."
        )
    return canonical


# ---------------------------------------------------------------------------
# Rendering (runtime)
# ---------------------------------------------------------------------------

#: Matches a template that is exactly one ``{{ expr }}`` and nothing
#: else. The inner expression may not contain ``}}`` (a literal ``}}``
#: inside a string constant falls back to plain string rendering).
_SINGLE_EXPR_RE = re.compile(r"\{\{\s*((?:(?!\}\}).)+?)\s*\}\}", re.DOTALL)


def _render_string(template: str, context: dict) -> Any:
    """Render one template string; Jinja errors become WorkflowError.

    Deterministic native rendering: a value that is exactly one
    ``{{ ... }}`` expression evaluates to the expression's value with
    its type preserved exactly (natives stay native, strings stay
    strings); anything mixed with literal text renders to a string.

    Note this deliberately does NOT use ``NativeEnvironment``: its
    ``native_concat`` runs ``ast.literal_eval`` over single-string
    results, so a string that merely *looks like* a literal (a JSON
    stdout, ``"42"``) would silently convert to a list/int. Type must
    never depend on string content.
    """
    single = _SINGLE_EXPR_RE.fullmatch(template)
    try:
        if single is not None:
            rendered = _NATIVE_ENV.compile_expression(
                single.group(1),
                # Keep StrictUndefined loud: the default converts
                # undefined to None, which would let typos slip through.
                undefined_to_none=False,
            )(**context)
        else:
            rendered = _JINJA_ENV.from_string(template).render(context)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        raise WorkflowError(f"Template error in {template!r}: {exc}") from exc
    if isinstance(rendered, Undefined):
        # A diatomic Undefined can survive without raising (e.g. inside a
        # filter chain) — fail loudly here so typos never slip through.
        raise WorkflowError(
            f"Template error in {template!r}: "
            f"'{rendered._undefined_name}' is undefined."
        )
    if isinstance(rendered, str) and len(rendered) > MAX_ARG_CHARS:
        raise WorkflowError(
            f"Rendered argument exceeds {MAX_ARG_CHARS} chars "
            f"(template {template[:80]!r}...)."
        )
    return rendered


def _render_value(value: Any, context: dict) -> Any:
    """Recursively render template strings inside an args structure."""
    if isinstance(value, str):
        return _render_string(value, context) if "{{" in value else value
    if isinstance(value, dict):
        return {k: _render_value(v, context) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_render_value(v, context) for v in value]
    return value


def render_args(args: dict, context: dict) -> dict:
    """Render an args mapping against *context* (raises WorkflowError)."""
    rendered = _render_value(args, context)
    if not isinstance(rendered, dict):
        raise WorkflowError("Rendered step args must be a mapping.")
    return rendered


# ---------------------------------------------------------------------------
# CRUD (raw session pks; raise WorkflowError — wrappers convert)
# ---------------------------------------------------------------------------

def _not_found(name: str) -> WorkflowError:
    return WorkflowError(
        f"No workflow named '{name}'. Use workflow_list to see this "
        "session's workflows and workflow_create to make one."
    )


def _mint_version(session_pk: int, canonical: dict, source: str):
    """Store *canonical* content-addressed and mint an immutable version."""
    from server.models.content import GenericContent
    from server.models.workflow import WorkflowVersion

    content = GenericContent.from_data(canonical)
    return WorkflowVersion.objects.create(
        content=content,
        name=canonical["name"],
        description=canonical.get("description") or "",
        created_by_session_id=session_pk,
        source=source,
    )


def create_workflow(session_pk: int, name: str, steps: Any,
                    description: str = "", inputs_schema: Any = None,
                    source: str = "tool", policy: Any = None) -> dict:
    """Create one session-private workflow (fails if *name* is taken)."""
    from server.models.workflow import SessionWorkflow

    canonical = validate_workflow(name, steps, description, inputs_schema,
                                  session_pk=session_pk, policy=policy)
    if SessionWorkflow.objects.filter(session_id=session_pk, name=name).exists():
        raise WorkflowError(
            f"Workflow '{name}' already exists. Use workflow_update to change it."
        )
    if SessionWorkflow.objects.filter(session_id=session_pk).count() >= MAX_WORKFLOWS:
        raise WorkflowError(
            f"Workflow limit reached ({MAX_WORKFLOWS} per session). "
            "Delete one first."
        )
    try:
        with transaction.atomic():
            version = _mint_version(session_pk, canonical, source)
            SessionWorkflow.objects.create(
                session_id=session_pk, name=name, version=version
            )
    except IntegrityError as exc:
        raise WorkflowError(
            f"Workflow '{name}' already exists. Use workflow_update to change it."
        ) from exc
    return {"name": name, "version": version.pk,
            "steps": len(canonical["steps"])}


def update_workflow(session_pk: int, name: str, steps: Any = None,
                    description: str | None = None,
                    inputs_schema: Any = None,
                    _clear_schema: bool = False,
                    source: str = "tool", policy: Any = None) -> dict:
    """Update a workflow (mints a new version, moves only the writer's link).

    Saving content identical to the current version is a no-op (no new
    version row, ``unchanged: True``).  Only the writer's link moves —
    siblings and forks keep theirs.
    """
    from server.models.workflow import SessionWorkflow

    validate_workflow_name(name)
    try:
        with transaction.atomic():
            try:
                link = (
                    SessionWorkflow.objects.select_for_update()
                    .select_related("version__content")
                    .get(session_id=session_pk, name=name)
                )
            except SessionWorkflow.DoesNotExist:
                raise _not_found(name) from None
            current = link.version.content.get()
            eff_steps = steps if steps is not None else current["steps"]
            eff_description = (description if description is not None
                               else current.get("description", ""))
            if _clear_schema:
                eff_schema: Any = {}
            elif inputs_schema is not None:
                eff_schema = inputs_schema
            else:
                eff_schema = current.get("inputs_schema") or {}
            canonical = validate_workflow(name, eff_steps, eff_description,
                                          eff_schema, session_pk=session_pk,
                                          policy=policy)
            from server.models.content import GenericContent

            if GenericContent.from_data(canonical).pk == link.version.content_id:
                return {"name": name, "version": link.version.pk,
                        "unchanged": True}
            version = _mint_version(session_pk, canonical, source)
            link.version = version
            link.save(update_fields=["version"])
    except IntegrityError as exc:
        raise WorkflowError(f"Could not update workflow: {exc}") from exc
    return {"name": name, "version": version.pk,
            "steps": len(canonical["steps"])}


def list_workflows(session_pk: int) -> list[dict]:
    """List this session's workflows (metadata only, no step bodies)."""
    from server.models.workflow import SessionWorkflow

    links = (
        SessionWorkflow.objects.filter(session_id=session_pk)
        .select_related("version__content")
        .order_by("name")
    )
    return [
        {
            "name": link.name,
            "description": link.version.description,
            "version": link.version.pk,
            "steps": len(link.version.content.get().get("steps", [])),
            "updated_at": link.updated_at.isoformat(),
        }
        for link in links
    ]


def get_workflow(session_pk: int, name: str) -> dict:
    """Return one workflow's canonical definition plus metadata."""
    from server.models.workflow import SessionWorkflow

    validate_workflow_name(name)
    try:
        link = (
            SessionWorkflow.objects.select_related("version__content").get(
                session_id=session_pk, name=name
            )
        )
    except SessionWorkflow.DoesNotExist:
        raise _not_found(name) from None
    version = link.version
    canonical = version.content.get()
    return {
        "name": name,
        "definition": canonical,
        "meta": {
            "description": version.description,
            "version": version.pk,
            "steps": len(canonical.get("steps", [])),
            "created_at": version.created_at.isoformat(),
            "updated_at": link.updated_at.isoformat(),
        },
    }


def delete_workflow(session_pk: int, name: str) -> dict:
    """Delete one session workflow (removes the link row only).

    Version rows stay as the audit trail.  Runs pin version pks directly,
    so deleting mid-run cannot break a running execution.
    """
    from server.models.workflow import SessionWorkflow

    validate_workflow_name(name)
    deleted, _ = SessionWorkflow.objects.filter(
        session_id=session_pk, name=name
    ).delete()
    if not deleted:
        raise _not_found(name)
    return {"name": name}


def inherit_workflows(parent_session_pk: int | str,
                      child_session_pk: int | str) -> int:
    """Copy a parent session's workflow links to a fork (copy-on-write).

    Called from ``AgentVersionModel.get_or_create_session`` for newly
    created sessions only — no version rows are minted, so parent and fork
    share history until the fork first saves.  Returns the link count.
    """
    from server.models.workflow import SessionWorkflow

    rows = list(
        SessionWorkflow.objects.filter(session_id=parent_session_pk).values_list(
            "name", "version_id"
        )
    )
    if not rows:
        return 0
    SessionWorkflow.objects.bulk_create(
        [
            SessionWorkflow(
                session_id=child_session_pk, name=name, version_id=version_id
            )
            for name, version_id in rows
        ],
        ignore_conflicts=True,
    )
    return len(rows)


# ---------------------------------------------------------------------------
# Execution (bound session; chained continuations — never block)
# ---------------------------------------------------------------------------

def _load_pinned_definition(version_pk: int) -> tuple[str, dict]:
    """Load the immutable definition pinned by a run (raises WorkflowError)."""
    from server.models.workflow import WorkflowVersion

    try:
        version = WorkflowVersion.objects.select_related("content").get(pk=version_pk)
    except WorkflowVersion.DoesNotExist:
        raise WorkflowError(
            f"Workflow version {version_pk} no longer exists."
        ) from None
    canonical = version.content.get()
    return version.name, canonical


def _unwrap_call_output(value: Any) -> Any:
    """Unwrap a tool-call envelope ``(True, payload)`` to its payload.

    Tool functions return ``(bool, dict)`` tuples, serialized as 2-lists;
    the payload itself may be any JSON value (a map producer's list, a
    group payload, ...).  Anything else passes through untouched.
    Use :func:`_raise_for_failure_envelope` first: a ``(False, ...)``
    envelope is a failure, not data.
    """
    if isinstance(value, list) and len(value) == 2 and value[0] is True:
        return value[1]
    return value


def _raise_for_failure_envelope(value: Any, where: str) -> Any:
    """Fail fast on a ``(False, payload)`` tool envelope.

    A tool that returns ``(False, ...)`` ends its call "successfully" at
    the framework level, so waiting continuations still run — without
    this check the failure payload would flow on as step data and blow
    up later with a misleading message far from the cause (e.g. a map
    complaining about a missing path when the producer tool actually
    errored).  *where* names the origin, e.g. ``"tool 'python' (call
    12)"``.  Returns *value* unchanged when it is not a failure.
    """
    if isinstance(value, list) and len(value) == 2 and value[0] is False:
        payload = value[1]
        detail: str | None = None
        if isinstance(payload, dict):
            for key in ("message", "error", "stderr"):
                if payload.get(key):
                    detail = str(payload[key])
                    break
        if detail is None:
            try:
                detail = json.dumps(payload)
            except (ValueError, TypeError):
                detail = str(payload)
        raise WorkflowError(f"{where} reported failure: {detail[:800]}")
    return value


def _call_output(session: Any, call_pk: int) -> Any:
    """Resolve one recorded call pk to its unwrapped output (timeout=0)."""
    from server.models.tasks.agent_task_call import AgentTaskCall

    try:
        call = AgentTaskCall.objects.get(pk=call_pk)
    except AgentTaskCall.DoesNotExist:
        raise WorkflowError(
            f"Workflow lost its recorded call {call_pk}."
        ) from None
    try:
        tool_name = call.task_definition.name if call.task_definition else "?"
    except Exception:  # pylint: disable=broad-exception-caught
        tool_name = "?"
    try:
        resolved = call.get_result(timeout=0)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        raise WorkflowError(
            f"Could not resolve output of call {call_pk}: {exc}"
        ) from exc
    _raise_for_failure_envelope(resolved, f"Step tool '{tool_name}' (call {call_pk})")
    return _unwrap_call_output(resolved)


def _step_records(definition: dict, run_ctx: dict, session: Any,
                  upto: int | None = None) -> dict[str, dict]:
    """Build ``{step_id: {output, count, succeeded}}`` for completed steps."""
    records: dict[str, dict] = {}
    calls = run_ctx.get("calls", {})
    steps = definition["steps"][:upto] if upto is not None else definition["steps"]
    for step in steps:
        step_id = step["id"]
        leaves = calls.get(step_id, "MISSING")
        if leaves == "MISSING":
            raise WorkflowError(f"Workflow lost state for step {step_id!r}.")
        if leaves is None:
            records[step_id] = {"output": None, "count": 0,
                                "succeeded": False, "skipped": True}
            continue
        values = [_call_output(session, pk) for pk in leaves]
        output = _regroup_output(step, values)
        records[step_id] = {
            "output": output,
            "count": len(output) if isinstance(output, list)
            else (0 if output is None else 1),
            "succeeded": True,
        }
    return records


def _regroup_output(step: dict, values: list) -> Any:
    """Reassemble flat leaf outputs into a step's structured output."""
    if "tool" in step or "function" in step:
        return values[0] if values else None
    if "group" in step:
        out, pos = [], 0
        for branch in step["group"]:
            if "group" in branch:
                width = _leaf_count(branch)
                out.append(values[pos:pos + width])
                pos += width
            else:
                out.append(values[pos])
                pos += 1
        return out
    if "map" in step:
        width = _leaf_count(step["map"]["consumer"])
        return [values[i:i + width] if width > 1 else values[i]
                for i in range(0, len(values), width)]
    return values[0] if values else None


def _leaf_count(action: dict) -> int:
    """Count tool-call leaves under an action (nested groups flatten)."""
    if "tool" in action:
        return 1
    if "group" in action:
        return sum(_leaf_count(b) for b in action["group"])
    return 1  # map consumers are single calls or one nested group


def _flatten_action(action: dict) -> list[dict]:
    """Flatten an action to its ordered leaf ``{"tool"|"function", "args"}`` specs."""
    if "tool" in action:
        return [{"tool": action["tool"], "args": action.get("args", {})}]
    if "function" in action:
        return [{"function": action["function"], "args": action.get("args", {})}]
    leaves: list[dict] = []
    for branch in action.get("group", []):
        leaves.extend(_flatten_action(branch))
    return leaves


def _render_context(definition: dict, run_ctx: dict, session: Any,
                    upto: int, item: Any = None, index: Any = None) -> dict:
    """Build the Jinja context for rendering step *upto*'s arguments."""
    records = _step_records(definition, run_ctx, session, upto=upto)
    context: dict[str, Any] = {
        "inputs": run_ctx.get("inputs", {}),
        "steps": records,
    }
    if item is not None or index is not None:
        context["item"] = item
        context["index"] = index
    return context


def _check_inputs_against_schema(inputs: Any, schema: dict) -> None:
    """Validate run inputs (reuses the ad-hoc params-schema subset)."""
    from runtime.adhoc_tools import validate_params_against_schema

    err = validate_params_against_schema(inputs, schema or None)
    if err:
        raise WorkflowError(f"Invalid workflow inputs: {err}")


def _error_envelope(name: str, message: str) -> dict:
    return {"status": "error", "workflow": name, "message": message}


def _final_envelope(definition: dict, run_ctx: dict, session: Any) -> dict:
    """Build the workflow's final result envelope (all steps complete)."""
    records = _step_records(definition, run_ctx, session)
    return {
        "status": "success",
        "workflow": run_ctx.get("name"),
        "version": run_ctx.get("version_pk"),
        "outputs": {step_id: rec["output"] for step_id, rec in records.items()},
        "skipped": sorted(
            step_id for step_id, rec in records.items() if rec.get("skipped")
        ),
    }


def _task_or_error(session: Any, kind: str, name: str):
    """Fetch a bound tool/task; return None when unavailable."""
    getter = session.get_tool if kind == "tool" else session.get_task
    try:
        return getter(name)
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def run_workflow(session: Any, name: str, inputs: Any = None,
                 _visited: list | None = None):
    """Start a workflow run; return the first continuation call (auto-awaited).

    Pins the current version pk — later edits move only the link, so this
    run's semantics cannot change mid-flight.  Returns an ``AgentTaskCall``
    for the ``workflow_step`` task (the framework auto-awaits the chain and
    the LLM turn receives the final envelope), or a ``(False, {...})``
    tuple when the run cannot start.
    """
    try:
        session_pk = session.model.pk
        validate_workflow_name(name)
        visited = list(_visited) if _visited else [name]
        if len(visited) > MAX_DEPTH:
            raise WorkflowError(
                f"Workflow nesting exceeds {MAX_DEPTH} levels "
                f"({' -> '.join(visited)})."
            )
        data = get_workflow(session_pk, name)
        canonical = data["definition"]
        inputs = _coerce_dict_arg(inputs, "inputs")
        _check_inputs_against_schema(inputs, canonical.get("inputs_schema") or {})
        run_ctx = {
            "name": name,
            "version_pk": data["meta"]["version"],
            "inputs": inputs,
            "visited": visited,
            "calls": {},
            "producers": {},
        }
        stepper = _task_or_error(session, "task", "workflow_step")
        if stepper is None:
            raise WorkflowError(
                "Workflow engine task 'workflow_step' is not available to "
                "this session."
            )
        return stepper.delay(run_ctx=run_ctx, index=0)
    except WorkflowError as exc:
        return (False, {"status": "error", "message": str(exc)})


def _advance_or_finish(session: Any, run_ctx: dict, definition: dict,
                       next_index: int):
    """Dispatch the next step, or finish when no steps remain."""
    if next_index >= len(definition["steps"]):
        return _final_envelope(definition, run_ctx, session)
    stepper = session.get_task("workflow_step")
    if stepper is None:
        return _error_envelope(
            run_ctx.get("name", "?"),
            "Workflow engine task 'workflow_step' is not available.",
        )
    return stepper.delay(run_ctx=run_ctx, index=next_index)


def _resolve_path(value: Any, dotted: str) -> Any:
    """Resolve a dotted path inside a producer output (lists index by int)."""
    if not dotted:
        return value
    current = value
    for segment in dotted.split("."):
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        elif isinstance(current, list) and segment.isdigit() \
                and int(segment) < len(current):
            current = current[int(segment)]
        else:
            raise WorkflowError(
                f"Map producer path {dotted!r} not found in producer output."
            )
    return current


def step_workflow(session: Any, run_ctx: dict, index: int):
    """Execute step *index*: dispatch its tool call(s) plus a continuation.

    Skipped (``when``-false) steps loop forward synchronously — no dispatch
    needed.  Returns the continuation call, or a result envelope when the
    workflow is done or cannot proceed.
    """
    try:
        name, definition = _load_pinned_definition(run_ctx["version_pk"])
        run_ctx = dict(run_ctx)
        run_ctx["calls"] = dict(run_ctx.get("calls", {}))
        run_ctx["producers"] = dict(run_ctx.get("producers", {}))
        steps = definition["steps"]

        while index < len(steps):
            step = steps[index]
            if "when" in step:
                records = _step_records(definition, run_ctx, session, upto=index)
                try:
                    if not evaluate_when(step["when"], records):
                        run_ctx["calls"][step["id"]] = None
                        index += 1
                        continue
                except WorkflowError as exc:
                    return _error_envelope(name, str(exc))
            break
        if index >= len(steps):
            return _final_envelope(definition, run_ctx, session)
        step = steps[index]
        context = _render_context(definition, run_ctx, session, upto=index)

        if "tool" in step or "function" in step:
            return _dispatch_tool_step(session, run_ctx, definition, index,
                                       step, context)
        if "group" in step:
            return _dispatch_group_step(session, run_ctx, definition, index,
                                        step, context)
        return _dispatch_map_step(session, run_ctx, definition, index,
                                  step, context)
    except (WorkflowError, KeyError, TypeError) as exc:
        return _error_envelope(run_ctx.get("name", "?"), str(exc))


def _dispatch_tool_call(session: Any, spec: dict, context: dict,
                        workflow_name: str):
    """Render one leaf spec and dispatch it; return the AgentTaskCall."""
    if "function" in spec:
        return _dispatch_function_call(session, spec, context, workflow_name)
    tool_name = spec["tool"]
    if tool_name == "workflow_run" and "name" not in (spec.get("args") or {}):
        raise WorkflowError(
            "A 'workflow_run' step needs 'args.name' naming the sub-workflow."
        )
    try:
        args = render_args(spec.get("args") or {}, context)
    except WorkflowError as exc:
        raise WorkflowError(f"Step args failed to render: {exc}") from exc
    if tool_name == "workflow_run":
        visited = context.get("__visited__", [workflow_name])
        target = args.get("name")
        if target in visited:
            raise WorkflowError(
                f"Workflow cycle detected: {' -> '.join(visited + [target])}."
            )
        if len(visited) >= MAX_DEPTH:
            raise WorkflowError(
                f"Workflow nesting exceeds {MAX_DEPTH} levels "
                f"({' -> '.join(visited + [target])})."
            )
        args["_visited"] = visited + [target]
    bound = _task_or_error(session, "tool", tool_name)
    if bound is None:
        raise WorkflowError(
            f"Step tool '{tool_name}' is not available to this session "
            "(unknown or not in allowedToolNames)."
        )
    try:
        serializable = json.loads(json.dumps(args))
    except (ValueError, TypeError) as exc:
        raise WorkflowError(
            f"Step args for tool '{tool_name}' are not JSON-serializable: {exc}"
        ) from exc
    return bound.delay(**serializable)


def _dispatch_function_call(session: Any, spec: dict, context: dict,
                            workflow_name: str):
    """Render one inline-function leaf and dispatch it; return the call.

    Goes through the internal ``workflow_inline`` task so the step gets a
    recorded call like any tool leaf (fail-fast, regroup, ``path`` and
    ``when`` all work unchanged). The body runs isolated in a subprocess
    at execution time; it was scanned and syntax-checked at save time.
    """
    try:
        args = render_args(spec.get("args") or {}, context)
    except WorkflowError as exc:
        raise WorkflowError(f"Step args failed to render: {exc}") from exc
    for auto in ("item", "index"):
        # Map consumers bind these per element; a function body names them
        # directly, so they arrive as variables without an explicit arg.
        # Explicit args win on collision.
        if auto in context and auto not in args:
            args[auto] = context[auto]
    try:
        serializable = json.loads(json.dumps(args))
    except (ValueError, TypeError) as exc:
        raise WorkflowError(
            "Step args for an inline function are not JSON-serializable: "
            f"{exc}"
        ) from exc
    import keyword

    for key in serializable:
        if not isinstance(key, str) or not key.isidentifier() \
                or keyword.iskeyword(key):
            raise WorkflowError(
                f"Inline function argument {key!r} is not a valid Python "
                "parameter name."
            )
    inline = _task_or_error(session, "task", "workflow_inline")
    if inline is None:
        raise WorkflowError(
            "Workflow engine task 'workflow_inline' is not available to "
            "this session."
        )
    return inline.delay(source=spec["function"], params=serializable)


def _dispatch_tool_step(session: Any, run_ctx: dict, definition: dict,
                        index: int, step: dict, context: dict):
    """Dispatch a single tool/function step plus its advance continuation."""
    name = run_ctx.get("name", "?")
    context = dict(context, __visited__=run_ctx.get("visited", [name]))
    leaf = {"args": step.get("args", {})}
    if "function" in step:
        leaf["function"] = step["function"]
    else:
        leaf["tool"] = step["tool"]
    try:
        call = _dispatch_tool_call(session, leaf, context, name)
    except WorkflowError as exc:
        return _error_envelope(name, str(exc))
    run_ctx["calls"][step["id"]] = [call.pk]
    advancer = session.get_task("workflow_advance")
    if advancer is None:
        return _error_envelope(name, "Workflow engine task 'workflow_advance' missing.")
    return advancer.delay(run_ctx=run_ctx, index=index, prior=call)


def _dispatch_group_step(session: Any, run_ctx: dict, definition: dict,
                         index: int, step: dict, context: dict):
    """Dispatch a group's flattened leaf calls plus a join continuation."""
    name = run_ctx.get("name", "?")
    leaves = _flatten_action({"group": step["group"]})
    context = dict(context, __visited__=run_ctx.get("visited", [name]))
    calls = []
    try:
        for leaf in leaves:
            calls.append(_dispatch_tool_call(session, leaf, context, name))
    except WorkflowError as exc:
        return _error_envelope(name, str(exc))
    run_ctx["calls"][step["id"]] = [c.pk for c in calls]
    joiner = session.get_task("workflow_join")
    if joiner is None:
        return _error_envelope(name, "Workflow engine task 'workflow_join' missing.")
    return joiner.delay(run_ctx=run_ctx, index=index, branches=calls)


def _dispatch_map_step(session: Any, run_ctx: dict, definition: dict,
                       index: int, step: dict, context: dict):
    """Dispatch a map's producer plus a fanout continuation."""
    name = run_ctx.get("name", "?")
    producer = step["map"]["producer"]
    context = dict(context, __visited__=run_ctx.get("visited", [name]))
    fanouter = session.get_task("workflow_fanout")
    if fanouter is None:
        return _error_envelope(name, "Workflow engine task 'workflow_fanout' missing.")
    if "step" in producer:
        leaves = run_ctx["calls"].get(producer["step"])
        if not leaves:
            return _error_envelope(
                name,
                f"Map producer step {producer['step']!r} produced no output.",
            )
        from server.models.tasks.agent_task_call import AgentTaskCall

        producer_calls = []
        for pk in leaves:
            try:
                producer_calls.append(AgentTaskCall.objects.get(pk=pk))
            except AgentTaskCall.DoesNotExist:
                return _error_envelope(
                    name, f"Workflow lost its recorded call {pk}."
                )
        run_ctx["producers"][step["id"]] = [c.pk for c in producer_calls]
        # Already-ended calls: the fanout resolves immediately (no wait).
        return fanouter.delay(run_ctx=run_ctx, index=index,
                              producer=producer_calls)
    try:
        leaf = producer.get("call", producer.get("function"))
        if leaf is None:
            raise WorkflowError(
                f"Invalid step {step['id']!r}: map producer has no 'call' "
                "or 'function' spec."
            )
        call = _dispatch_tool_call(session, leaf, context, name)
    except WorkflowError as exc:
        return _error_envelope(name, str(exc))
    run_ctx["producers"][step["id"]] = call.pk
    return fanouter.delay(run_ctx=run_ctx, index=index, producer=call)


def advance_workflow(session: Any, run_ctx: dict, index: int, prior: Any):
    """Continue after a tool step's call ended; dispatch the next step.

    ``prior`` carries the scheduler dependency (its resolved value is not
    needed — outputs are re-resolved from the recorded call pks).
    """
    # pylint: disable=unused-argument
    try:
        _name, definition = _load_pinned_definition(run_ctx["version_pk"])
        return _advance_or_finish(session, run_ctx, definition, index + 1)
    except (WorkflowError, KeyError, TypeError) as exc:
        return _error_envelope(run_ctx.get("name", "?"), str(exc))


def join_workflow(session: Any, run_ctx: dict, index: int, branches: list):
    """Continue after a group's branches all ended; dispatch the next step.

    ``branches`` carries the scheduler fan-in dependency (resolved values
    are re-read from the recorded call pks).
    """
    # pylint: disable=unused-argument
    try:
        _name, definition = _load_pinned_definition(run_ctx["version_pk"])
        return _advance_or_finish(session, run_ctx, definition, index + 1)
    except (WorkflowError, KeyError, TypeError) as exc:
        return _error_envelope(run_ctx.get("name", "?"), str(exc))


def fanout_workflow(session: Any, run_ctx: dict, index: int, producer: Any):
    """Continue after a map's producer ended; dispatch wave 1 + mapjoin."""
    name = run_ctx.get("name", "?")
    try:
        _name, definition = _load_pinned_definition(run_ctx["version_pk"])
        step = definition["steps"][index]
        spec = step["map"]["producer"]
        if isinstance(producer, list) and "step" in spec:
            # Step-ref producer: regroup this step's leaf results first.
            producer_def = next(
                s for s in definition["steps"] if s["id"] == spec["step"]
            )
            where = f"Map producer step '{spec['step']}'"
            value = _regroup_output(
                producer_def,
                [_unwrap_call_output(_raise_for_failure_envelope(v, where))
                 for v in producer],
            )
        else:
            if "call" in spec:
                tool = spec["call"].get("tool", "?")
                where = f"Map producer tool '{tool}'"
            else:
                where = "Map producer function"
            value = _unwrap_call_output(_raise_for_failure_envelope(
                producer, where))
        if "path" in spec and spec["path"]:
            try:
                value = _resolve_path(value, spec["path"])
            except WorkflowError as exc:
                return _error_envelope(name, str(exc))
        if isinstance(value, str):
            # Tools like `python` hand back strings (e.g. stdout). A
            # JSON-encoded list string parses to the list — anything
            # else falls through to the must-be-a-list error below.
            try:
                value = json.loads(value)
            except ValueError:
                pass
        if not isinstance(value, list):
            preview = str(value)
            return _error_envelope(
                name,
                f"Map producer for step {step['id']!r} must resolve to a list, "
                f"got {type(value).__name__}: {preview[:200]}.",
            )
        if len(value) > MAX_ITEMS:
            return _error_envelope(
                name,
                f"Map producer for step {step['id']!r} yielded {len(value)} "
                f"items (cap {MAX_ITEMS}).",
            )
        if not value:
            run_ctx["calls"][step["id"]] = []
            return _advance_or_finish(session, run_ctx, definition, index + 1)
        try:
            serializable = json.loads(json.dumps(value))
        except (ValueError, TypeError):
            return _error_envelope(
                name,
                f"Map items for step {step['id']!r} are not JSON-serializable.",
            )
        width = step["map"]["max_parallel"]
        return _dispatch_map_wave(session, run_ctx, definition, index, step,
                                  serializable, start=0, width=width,
                                  collected_pks=[])
    except (WorkflowError, KeyError, TypeError) as exc:
        return _error_envelope(name, str(exc))


def _dispatch_map_wave(session: Any, run_ctx: dict, definition: dict,
                       index: int, step: dict, items: list, start: int,
                       width: int, collected_pks: list):
    """Dispatch one consumer wave plus a mapjoin continuation."""
    name = run_ctx.get("name", "?")
    step_id = step["id"]
    consumer = step["map"]["consumer"]
    leaves = _flatten_action(consumer)
    context = _render_context(definition, run_ctx, session, upto=index)
    context = dict(context, __visited__=run_ctx.get("visited", [name]))
    wave_calls = []
    wave_end = min(start + width, len(items))
    try:
        for pos in range(start, wave_end):
            item_context = dict(context, item=items[pos], index=pos)
            for leaf in leaves:
                wave_calls.append(
                    _dispatch_tool_call(session, leaf, item_context, name)
                )
    except WorkflowError as exc:
        return _error_envelope(name, str(exc))
    all_pks = list(collected_pks) + [c.pk for c in wave_calls]
    run_ctx["calls"][step_id] = all_pks
    mapjoiner = session.get_task("workflow_mapjoin")
    if mapjoiner is None:
        return _error_envelope(name, "Workflow engine task 'workflow_mapjoin' missing.")
    return mapjoiner.delay(
        run_ctx=run_ctx,
        index=index,
        collected=all_pks,
        wave=wave_calls,
        remaining=items[wave_end:],
    )


def mapjoin_workflow(session: Any, run_ctx: dict, index: int,
                     collected: list, wave: list, remaining: list):
    """Continue after a map wave ended; dispatch the next wave or next step.

    ``wave`` carries the scheduler dependency for this wave's calls; wave
    outputs are re-read from ``collected`` (recorded call pks).
    """
    # pylint: disable=unused-argument
    name = run_ctx.get("name", "?")
    try:
        _name, definition = _load_pinned_definition(run_ctx["version_pk"])
        step = definition["steps"][index]
        if remaining:
            width = step["map"]["max_parallel"]
            try:
                serializable = json.loads(json.dumps(remaining))
            except (ValueError, TypeError):
                return _error_envelope(
                    name, f"Map items for step {step['id']!r} are not JSON-serializable."
                )
            return _dispatch_map_wave(
                session, run_ctx, definition, index, step, serializable,
                start=0, width=width,
                collected_pks=[pk for pk in collected],
            )
        run_ctx["calls"][step["id"]] = [pk for pk in collected]
        return _advance_or_finish(session, run_ctx, definition, index + 1)
    except (WorkflowError, KeyError, TypeError) as exc:
        return _error_envelope(name, str(exc))
