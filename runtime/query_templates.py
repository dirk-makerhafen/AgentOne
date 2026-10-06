"""Reusable query (prompt) templates stored in the session-private folder.

Each template is a Markdown file at::

    <SESSIONS_BASE>/<session_pk>/templates/<slug>.md

with YAML frontmatter (``name``, ``description``, ``variables``) and a Jinja2
body rendered with caller-supplied structured data::

    ---
    name: summarize
    description: Summarize text into N bullet points
    variables:
      - name: text
        type: string
        required: true
        description: Text to summarize
      - name: max_points
        type: integer
        required: false
        default: 5
    ---
    Summarize the following in {{ max_points }} bullet points:

    {{ text }}

Variable entries accept ``name`` (required), ``type`` (``string`` |
``integer`` | ``number``/``float`` | ``boolean``), ``required`` (default
``True`` when no ``default`` is given; parsed like a boolean so the
string ``"false"`` means False), ``default``, and ``description``.
A plain string entry (``variables: [text]``) means a required string.

Coercion is lenient for numbers: ``"5"`` → ``5`` for ``integer``/``number``,
``"5.5"`` → ``5.5`` for ``number``.  Booleans accept ``"true"``/``"false"``,
``"1"``/``"0"``, ``"yes"``/``"no"`` (case-insensitive) plus real bools/1/0.

Rendering uses Jinja2 with ``StrictUndefined`` so misspelled variables fail
instead of silently rendering empty (stricter than the turn pipeline's
``QueryMessagePart``, which is intentional for reusable templates).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frontmatter
import yaml
from jinja2 import BaseLoader, Environment, StrictUndefined

from runtime.session_folder import ensure_session_templates_dir, session_templates_dir

_JINJA_ENV = Environment(loader=BaseLoader(), undefined=StrictUndefined)

#: Hard cap so a runaway template cannot blow up the LLM context.
MAX_BODY_CHARS = 65536

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-_]*$")
_VAR_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_TYPE_ALIASES = {
    "string": "string",
    "str": "string",
    "text": "string",
    "integer": "integer",
    "int": "integer",
    "number": "number",
    "float": "number",
    "boolean": "boolean",
    "bool": "boolean",
}

_TRUE_STRINGS = {"true", "1", "yes", "y", "on"}
_FALSE_STRINGS = {"false", "0", "no", "n", "off"}


class TemplateError(ValueError):
    """Raised when a template file, schema, or supplied variables are invalid."""


@dataclass
class TemplateVariable:
    """One declared template variable."""

    name: str
    type: str = "string"
    required: bool = True
    default: Any = None
    has_default: bool = False
    description: str = ""

    def to_dict(self) -> dict:
        out: dict = {"name": self.name, "type": self.type, "required": self.required}
        if self.has_default:
            out["default"] = self.default
        if self.description:
            out["description"] = self.description
        return out


@dataclass
class QueryTemplate:
    """A parsed query template (frontmatter schema + Jinja body)."""

    name: str
    description: str = ""
    variables: list[TemplateVariable] = field(default_factory=list)
    body: str = ""

    def to_dict(self, include_body: bool = True) -> dict:
        out: dict = {
            "name": self.name,
            "description": self.description,
            "variables": [v.to_dict() for v in self.variables],
        }
        if include_body:
            out["body"] = self.body
        return out


def slugify_name(name: str) -> str:
    """Return the filename slug for *name* (lowercase, safe chars)."""
    slug = re.sub(r"[^a-z0-9-_]+", "-", str(name or "").strip().lower()).strip("-")
    if not slug or not _NAME_RE.match(slug):
        raise TemplateError(
            f"Invalid template name {name!r}: use lowercase letters, digits, '-' or '_'."
        )
    return slug


def template_path(session_pk: int | str, name: str) -> Path:
    """Return the file path for template *name* (pure, no I/O)."""
    return session_templates_dir(session_pk) / f"{slugify_name(name)}.md"


def _normalize_variable(raw: Any, index: int) -> TemplateVariable:
    if isinstance(raw, str):
        raw = {"name": raw}
    if not isinstance(raw, dict):
        raise TemplateError(f"Variable #{index} must be a mapping or string, got {raw!r}.")
    name = raw.get("name")
    if not name or not isinstance(name, str) or not _VAR_NAME_RE.match(name):
        raise TemplateError(f"Variable #{index} needs a valid 'name' (identifier), got {name!r}.")
    raw_type = str(raw.get("type", "string")).lower()
    var_type = _TYPE_ALIASES.get(raw_type)
    if var_type is None:
        raise TemplateError(
            f"Variable {name!r} has unknown type {raw.get('type')!r}; "
            "use string, integer, number, or boolean."
        )
    has_default = "default" in raw
    if "required" in raw and raw["required"] is not None:
        # Coerce (don't bool()): the string "false" is truthy in Python
        # but clearly means False here.
        try:
            required = _coerce_boolean(raw["required"], f"Variable {name!r} 'required'")
        except TemplateError as exc:
            raise TemplateError(str(exc)) from exc
    else:
        required = not has_default
    default = raw.get("default")
    if has_default:
        try:
            default = coerce_value(var_type, default, var_name=name)
        except TemplateError as exc:
            raise TemplateError(f"Variable {name!r} has an invalid default: {exc}") from exc
    description = raw.get("description", "") or ""
    if not isinstance(description, str):
        raise TemplateError(f"Variable {name!r} 'description' must be a string.")
    return TemplateVariable(
        name=name, type=var_type, required=required,
        default=default, has_default=has_default, description=description or "",
    )


def _parse_structured_string(raw: str, what: str) -> Any:
    """Parse a JSON/YAML string into a list or dict, raising TemplateError."""
    try:
        parsed = json.loads(raw)
    except ValueError:
        try:
            parsed = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise TemplateError(
                f"'{what}' string could not be parsed as JSON or YAML: {exc}"
            ) from exc
    return parsed


def normalize_variables_list(raw_vars: Any) -> list:
    """Coerce caller-supplied ``variables`` into a list of specs.

    Accepts a list (as declared), or a JSON/YAML string encoding a list
    (LLMs sometimes serialize the argument).  A bare string like
    ``"question"`` is rejected explicitly — it is almost certainly one
    variable name, not a spec list, and iterating it would create one
    variable per character.
    """
    if raw_vars is None:
        return []
    if isinstance(raw_vars, str):
        if not raw_vars.strip():
            return []
        parsed = _parse_structured_string(raw_vars, "variables")
        if isinstance(parsed, dict):
            # A single mapping is one variable spec, not a spec list.
            return [parsed]
        if isinstance(parsed, list):
            return parsed
        raise TemplateError(
            "'variables' must be a list of variable specs "
            "(e.g. [{'name': 'question'}]). "
            f"Got a string encoding {type(parsed).__name__}: {raw_vars!r}. "
            "To declare a single variable named X, pass [{'name': 'X'}]."
        )
    if isinstance(raw_vars, dict):
        # A single mapping is one variable spec.
        return [raw_vars]
    if isinstance(raw_vars, list):
        return raw_vars
    raise TemplateError(
        f"'variables' must be a list of variable specs, got {type(raw_vars).__name__}."
    )


def normalize_context_dict(raw: Any) -> dict:
    """Coerce caller-supplied template values into a dict.

    Accepts a dict, or a JSON/YAML string encoding one.  Anything else —
    including a bare string — raises a clear error instead of failing
    later with a confusing message.
    """
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        if not raw.strip():
            return {}
        parsed = _parse_structured_string(raw, "variables")
        if isinstance(parsed, dict):
            return parsed
        raise TemplateError(
            "'variables' values must be an object mapping variable names "
            f"to values (e.g. {{\"question\": \"...\"}}), got {raw!r}."
        )
    raise TemplateError(
        f"'variables' values must be a dict, got {type(raw).__name__}."
    )


def _normalize_variables(raw_vars: Any) -> list[TemplateVariable]:
    """Normalize the frontmatter ``variables`` list, checking duplicates."""
    raw_vars = normalize_variables_list(raw_vars)
    if not isinstance(raw_vars, list):
        raise TemplateError("'variables' must be a list.")
    seen: set[str] = set()
    variables: list[TemplateVariable] = []
    for i, raw in enumerate(raw_vars):
        var = _normalize_variable(raw, i)
        if var.name in seen:
            raise TemplateError(f"Duplicate variable name {var.name!r}.")
        seen.add(var.name)
        variables.append(var)
    return variables


def parse_template_text(raw_text: str) -> QueryTemplate:
    """Parse template file text into a :class:`QueryTemplate`.

    Raises :class:`TemplateError` on any schema problem.
    """
    if not raw_text or not raw_text.strip():
        raise TemplateError("Template file is empty.")
    try:
        post = frontmatter.loads(raw_text)
    except Exception as exc:
        raise TemplateError(f"Could not parse frontmatter: {exc}") from exc
    meta = post.metadata or {}
    body = (post.content or "").strip("\n")
    # A file without a frontmatter block yields empty metadata — require it.
    if not meta:
        raise TemplateError("Template is missing its frontmatter head (name, description, variables).")
    name = meta.get("name")
    if not name or not isinstance(name, str):
        raise TemplateError("Template frontmatter needs a 'name' string.")
    try:
        slugify_name(name)
    except TemplateError as exc:
        raise TemplateError(str(exc)) from exc
    description = meta.get("description", "") or ""
    if not isinstance(description, str):
        raise TemplateError("Template 'description' must be a string.")
    variables = _normalize_variables(meta.get("variables", []))
    unknown = set(meta.keys()) - {"name", "description", "variables"}
    if unknown:
        raise TemplateError(f"Unknown frontmatter keys: {sorted(unknown)}.")
    if not body.strip():
        raise TemplateError("Template body is empty.")
    if len(body) > MAX_BODY_CHARS:
        raise TemplateError(f"Template body exceeds {MAX_BODY_CHARS} characters.")
    return QueryTemplate(name=name.strip(), description=description, variables=variables, body=body)


def _coerce_string(value: Any, label: str) -> str:
    if value is None:
        raise TemplateError(f"{label} must be a string, got None.")
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    raise TemplateError(f"{label} must be a string, got {type(value).__name__}.")


def _coerce_integer(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise TemplateError(f"{label} must be an integer, got boolean.")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        raise TemplateError(f"{label} must be an integer, got {value!r}.")
    if isinstance(value, str):
        text = value.strip()
        try:
            return int(text)
        except ValueError:
            pass
        try:
            as_float = float(text)
        except ValueError:
            raise TemplateError(f"{label} must be an integer, got {value!r}.") from None
        if as_float.is_integer():
            return int(as_float)
        raise TemplateError(f"{label} must be an integer, got {value!r}.") from None
    raise TemplateError(f"{label} must be an integer, got {type(value).__name__}.")


def _coerce_number(value: Any, label: str) -> int | float:
    if isinstance(value, bool):
        raise TemplateError(f"{label} must be a number, got boolean.")
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            as_float = float(value.strip())
        except ValueError:
            raise TemplateError(f"{label} must be a number, got {value!r}.") from None
        if as_float.is_integer():
            return int(as_float)
        return as_float
    raise TemplateError(f"{label} must be a number, got {type(value).__name__}.")


def _coerce_boolean(value: Any, label: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
        raise TemplateError(f"{label} must be a boolean, got {value!r}.")
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in _TRUE_STRINGS:
            return True
        if lowered in _FALSE_STRINGS:
            return False
        raise TemplateError(f"{label} must be a boolean, got {value!r}.")
    raise TemplateError(f"{label} must be a boolean, got {type(value).__name__}.")


_COERCERS = {
    "string": _coerce_string,
    "integer": _coerce_integer,
    "number": _coerce_number,
    "boolean": _coerce_boolean,
}


def coerce_value(var_type: str, value: Any, var_name: str = "") -> Any:
    """Coerce *value* to *var_type*, raising :class:`TemplateError` on failure."""
    try:
        coercer = _COERCERS[var_type]
    except KeyError:
        raise TemplateError(f"Unknown variable type {var_type!r}.") from None
    label = f"Variable {var_name!r}" if var_name else "Value"
    return coercer(value, label)


def build_context(template: QueryTemplate, variables: dict | str | None) -> dict:
    """Merge caller *variables* over template defaults, coercing types.

    Missing required variables raise :class:`TemplateError`.  Extra keys the
    template does not declare are ignored.
    """
    supplied = normalize_context_dict(variables)
    context: dict = {}
    missing: list[str] = []
    for var in template.variables:
        if var.name in supplied:
            value = supplied[var.name]
            if var.required and (
                value is None
                or (isinstance(value, str) and not value.strip())
            ):
                # A blank required field is the same as omitting it —
                # rendering with it would silently produce an empty prompt.
                missing.append(var.name)
                continue
            context[var.name] = coerce_value(var.type, value, var_name=var.name)
        elif var.has_default:
            context[var.name] = var.default
        elif var.required:
            missing.append(var.name)
        # Optional without default: omitted — referencing it fails loudly.
    if missing:
        raise TemplateError(f"Missing required variable(s): {', '.join(missing)}.")
    return context


def render_template(template: QueryTemplate, variables: dict | str | None) -> str:
    """Validate *variables* against *template* and render its Jinja body."""
    context = build_context(template, variables)
    try:
        return _JINJA_ENV.from_string(template.body).render(**context)
    except TemplateError:
        raise
    except Exception as exc:
        raise TemplateError(f"Could not render template {template.name!r}: {exc}") from exc


def list_templates(session_pk: int | str) -> list[dict]:
    """List this session's templates as ``{name, description, variables}`` dicts."""
    folder = session_templates_dir(session_pk)
    if not folder.is_dir():
        return []
    out: list[dict] = []
    for path in sorted(folder.glob("*.md")):
        try:
            template = parse_template_text(path.read_text(encoding="utf-8"))
        except (OSError, TemplateError):
            continue  # skip unreadable/invalid files; get_template reports them
        if slugify_name(template.name) != path.stem:
            continue  # file does not own this name — skip to avoid duplicates
        out.append(template.to_dict(include_body=False))
    return out


def get_template(session_pk: int | str, name: str) -> QueryTemplate:
    """Load template *name* for *session_pk*, raising :class:`TemplateError`."""
    slug = slugify_name(name)
    path = session_templates_dir(session_pk) / f"{slug}.md"
    if not path.is_file():
        raise TemplateError(f"Template {name!r} not found.")
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TemplateError(f"Could not read template {name!r}: {exc}") from exc
    template = parse_template_text(raw)
    if slugify_name(template.name) != slug:
        raise TemplateError(
            f"Template file {path.name} declares name {template.name!r} — rename one of them."
        )
    return template


def save_template(
    session_pk: int | str,
    name: str,
    body: str,
    description: str = "",
    variables: list | dict | str | None = None,
) -> QueryTemplate:
    """Validate and write template *name* for *session_pk* (create or overwrite)."""
    slug = slugify_name(name)
    if not body or not str(body).strip():
        raise TemplateError("Template body must not be empty.")
    if len(str(body)) > MAX_BODY_CHARS:
        raise TemplateError(f"Template body exceeds {MAX_BODY_CHARS} characters.")
    if description is None:
        description = ""
    if not isinstance(description, str):
        raise TemplateError("'description' must be a string.")
    # Canonical form: the slug is the name (lowercase, file-stable), so the
    # frontmatter name always matches the file stem exactly.
    frontmatter_data: dict = {"name": slug, "description": description}
    normalized_vars: list[dict] = []
    for i, raw in enumerate(normalize_variables_list(variables)):
        normalized_vars.append(_normalize_variable(raw, i).to_dict())
    frontmatter_data["variables"] = normalized_vars
    # Validate the assembled document through the same parser used on read.
    raw_text = "---\n" + yaml.safe_dump(frontmatter_data, sort_keys=False).strip() + "\n---\n" + str(body).strip() + "\n"
    template = parse_template_text(raw_text)
    if slugify_name(template.name) != slug:
        raise TemplateError(f"Template name {name!r} does not match file {slug!r}.")
    folder = ensure_session_templates_dir(session_pk)
    try:
        (folder / f"{slug}.md").write_text(raw_text, encoding="utf-8")
    except OSError as exc:
        raise TemplateError(f"Could not write template {name!r}: {exc}") from exc
    return template


def delete_template(session_pk: int | str, name: str) -> None:
    """Delete template *name*, raising :class:`TemplateError` if absent."""
    slug = slugify_name(name)
    path = session_templates_dir(session_pk) / f"{slug}.md"
    if not path.is_file():
        raise TemplateError(f"Template {name!r} not found.")
    try:
        path.unlink()
    except OSError as exc:
        raise TemplateError(f"Could not delete template {name!r}: {exc}") from exc


def render_template_by_name(
    session_pk: int | str, name: str, variables: dict | str | None
) -> tuple[QueryTemplate, str]:
    """Load *name* and render it with *variables*; returns ``(template, text)``."""
    template = get_template(session_pk, name)
    return template, render_template(template, variables)
