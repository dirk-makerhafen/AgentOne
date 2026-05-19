
import ast
import inspect
from pathlib import Path
import pkgutil
import sys
from django.core.exceptions import ValidationError

from server.models.providers.ai_model import AiModel

def get_ai_model(model_name: str|None):
    if model_name is None:
        return None
    print("model_name", model_name)
    try:
        ai_model = AiModel.objects.get(name=model_name)
        if not ai_model.enabled:
            raise ValidationError(f"AI Model '{model_name}' exists but is not enabled.")
        return ai_model
    except AiModel.DoesNotExist as e:
        raise ValidationError(f"AI Model '{model_name}' does not exist in the database.") from e


import inspect
import enum
import re
from typing import (
    get_type_hints, get_origin, get_args,
    Annotated, Union, Literal, List, Dict, TypedDict
)


def generate_schema_for_function(func):
    """
    Generate an LLM-optimized JSON schema for a function.
    Supports:
    - TypedDict (preferred)
    - Nested dict parsing from docstrings
    - Enum / Literal
    - Optional / Union
    - Annotated metadata
    """

    sig = inspect.signature(func)

    # --- Resolve type hints ---
    try:
        type_hints = get_type_hints(func, globalns=func.__globals__)
    except Exception:
        type_hints = {n: p.annotation for n, p in sig.parameters.items()}

    # --- Parse docstring ---
    doc = inspect.getdoc(func) or ""
    lines = doc.splitlines()

    param_descriptions = {}
    description_lines = []

    # --- Nested fields detection ---
    nested_fields = {}
    current_parent = None

    in_params = False
    current_param = None

    for line in lines:
        stripped = line.strip()

        # --- Sphinx ---
        m = re.search(r":param\s+(\w+):\s*(.*)", stripped)
        if m:
            param_descriptions[m.group(1)] = m.group(2)
            continue

        # --- Section detection ---
        if stripped.lower() in ("args:", "parameters:", "params:"):
            in_params = True
            continue
        elif in_params and stripped and not line.startswith(" "):
            in_params = False

        # --- Google/Numpy param parsing ---
        if in_params:
            m = re.match(r"^(\w+)\s*(?:\([^)]+\))?\s*:\s*(.*)", stripped)
            if m:
                name, desc = m.groups()
                param_descriptions[name] = desc
                current_param = name

                # detect "with fields:"
                if "field" in desc.lower():
                    current_parent = name
                    nested_fields[current_parent] = {}
                continue

            # multiline continuation
            if current_param and line.startswith("    "):
                param_descriptions[current_param] += " " + stripped

            # nested fields
            nm = re.match(r"^[-•]\s*(\w+)\s*\(([^)]+)\):\s*(.*)", stripped)
            if nm and current_parent:
                n_name, n_type, n_desc = nm.groups()
                nested_fields[current_parent][n_name] = {
                    "type": n_type,
                    "description": n_desc
                }
                continue
        else:
            description_lines.append(stripped)

    # --- Type resolver ---
    def resolve(annotation):
        if annotation is inspect._empty:
            return {"type": "string"}

        origin = get_origin(annotation)
        args = get_args(annotation)

        # --- Annotated ---
        if origin is Annotated:
            base = resolve(args[0])
            for meta in args[1:]:
                if isinstance(meta, str):
                    base["description"] = meta
                elif hasattr(meta, "description"):
                    base["description"] = meta.description
            return base

        # --- Optional / Union ---
        if origin is Union:
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                return resolve(non_none[0])
            return {"anyOf": [resolve(a) for a in non_none]}

        # --- Literal ---
        if origin is Literal:
            return {"enum": list(args)}

        # --- Enum ---
        if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
            return {
                "type": "string",
                "enum": [e.value for e in annotation]
            }

        # --- TypedDict ---
        if isinstance(annotation, type) and issubclass(annotation, dict) and hasattr(annotation, "__annotations__"):
            props = {}
            required = []

            for k, v in annotation.__annotations__.items():
                props[k] = resolve(v)
                required.append(k)

            return {
                "type": "object",
                "properties": props,
                "required": required,
                "additionalProperties": False
            }

        # --- List ---
        if origin in (list, List):
            return {
                "type": "array",
                "items": resolve(args[0] if args else str)
            }

        # --- Dict ---
        if origin in (dict, Dict):
            val_type = args[1] if len(args) == 2 else str
            return {
                "type": "object",
                "additionalProperties": resolve(val_type)
            }

        # --- Primitives ---
        mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            bytes: "string",
        }

        if annotation in mapping:
            return {"type": mapping[annotation]}

        if annotation in ("str",):
            return {"type": "string"}
        if annotation in ("int",):
            return {"type": "integer"}
        if annotation in ("float",):
            return {"type": "number"}
        if annotation in ("bool",):
            return {"type": "boolean"}

        return {"type": "string"}

    # --- Build schema ---
    schema = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False
    }

    for name, param in sig.parameters.items():
        if name in ("self", "task_run", "task_context"):
            continue

        annotation = type_hints.get(name, param.annotation)
        field_schema = resolve(annotation)

        # --- attach description ---
        if not field_schema.get("description"):
            field_schema["description"] = param_descriptions.get(name, "")

        # --- nested override ---
        if name in nested_fields:
            field_schema = {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False
                }
            }

            for n, meta in nested_fields[name].items():
                field_schema["items"]["properties"][n] = {
                    "type": meta["type"],
                    "description": meta["description"]
                }
                field_schema["items"]["required"].append(n)

        # --- required vs default ---
        if param.default is inspect.Parameter.empty:
            schema["required"].append(name)
        else:
            field_schema["default"] = param.default

        schema["properties"][name] = field_schema

    description = "\n".join([l for l in description_lines if l])

    return description, schema