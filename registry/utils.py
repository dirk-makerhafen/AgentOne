
import ast
import inspect
from pathlib import Path
import pkgutil
import sys
from django.core.exceptions import ValidationError

from server.models.providers.ai_model import AiModel

def get_import_strings(source_path, class_name):
    with open(source_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    # 1. Map names/aliases to their full import nodes
    name_to_node = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                # The name actually used in code is 'asname' if it exists, else 'name'
                name_used = alias.asname if alias.asname else alias.name
                name_to_node[name_used] = (node, alias)

    # 2. Find the target class definition       
    target_class = next((n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == class_name), None)
    if not target_class:
        return []

    # 3. Find all names referenced inside the class
    used_in_class = set()
    for node in ast.walk(target_class):
        if isinstance(node, ast.Name):
            used_in_class.add(node.id)
        elif isinstance(node, ast.Attribute):
            # For 'np.array', we need to catch 'np'
            curr = node.value
            while isinstance(curr, ast.Attribute):
                curr = curr.value
            if isinstance(curr, ast.Name):
                used_in_class.add(curr.id)

    
    # 4. Reconstruct the exact import strings used
    exec_strings = set()


    '''
    for name in used_in_class:
        if name in name_to_node:
            node, alias = name_to_node[name]
            # Format: "original_name as alias" or "original_name"
            alias_str = f"{alias.name} as {alias.asname}" if alias.asname else alias.name
            if isinstance(node, ast.Import):
                exec_strings.add(f"import {alias_str}")
            elif isinstance(node, ast.ImportFrom):
                exec_strings.add(f"from {node.module} import {alias_str}")
    '''

    # Filtering Logic: Keep only non-local modules
    for name in used_in_class:
        if name in name_to_node:
            node, alias = name_to_node[name]
            # Determine the base module name (e.g., 'os' from 'os.path' or 'from os import...')
            if isinstance(node, ast.ImportFrom):
                base_module = node.module.split('.')[0] if node.module else ""
            else:
                base_module = alias.name.split('.')[0]
            is_local= (Path(source_path).parent  / Path(base_module)).exists() and not base_module == "AgentOne"
                
            # CHECK: If it's a built-in or installed package, keep it
            is_builtin = base_module in sys.builtin_module_names
            is_installed = pkgutil.find_loader(base_module) is not None
            if (is_builtin or is_installed) and not is_local :
                alias_str = f"{alias.name} as {alias.asname}" if alias.asname else alias.name
                if isinstance(node, ast.Import):
                    exec_strings.add(f"import {alias_str} # {is_builtin}{is_installed}")
                elif isinstance(node, ast.ImportFrom):
                    exec_strings.add(f"from {node.module} import {alias_str} # {is_builtin}{is_installed}")

    imports = sorted(list(exec_strings))
    return imports



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



def generate_schema_for_function(func):
    """
    Generates a robust JSON Schema for the function's parameters.
    Features:
    - Resolves full type hints (handles forward references and string annotations).
    - Extracts parameter descriptions from docstrings (Sphinx, Google, and Numpy styles).
    - Handles complex typing: Optional, Union, List, Dict, Literal, and Annotated.
    - Supports standard Python Enums.
    - Identifies required fields and includes default values.
    """
    import enum
    import re
    from typing import get_type_hints, get_origin, get_args, Annotated, Union, Literal, List, Dict
    
    sig = inspect.signature(func)
    
    # 1. Resolve Type Hints effectively
    try:
        # Using func.__globals__ allows resolving types imported in the agent's file
        type_hints = get_type_hints(func, globalns=func.__globals__)
    except Exception:
        # Fallback to parameter annotations if resolution fails
        type_hints = {name: param.annotation for name, param in sig.parameters.items()}

    # 2. Robust Docstring Parsing for parameter-level descriptions
    doc = inspect.getdoc(func) or ""
    param_descriptions = {}
    
    desc_lines = doc.splitlines()
    in_params_section = False
    current_param = None
    #print("desc_lines", desc_lines)
    description_lines=[]
    for line in desc_lines:
        stripped = line.strip()
        # Try Sphinx style: :param name: description
        sphinx_match = re.search(r":param\s+(\w+):\s*(.*)", stripped)
        if sphinx_match:
            param_descriptions[sphinx_match.group(1)] = sphinx_match.group(2).strip()
            continue
            
        # Detect section headers (Google/Numpy style)
        if stripped.lower() in ("args:", "parameters:", "params:"):
            in_params_section = True
            continue
        elif in_params_section and line and not line.startswith(" ") and line.endswith(":"):
            in_params_section = False
        
        if in_params_section:
            # Matches 'name (type): description' or 'name: description'
            param_match = re.search(r"^([\w\d_]+)\s*(?:\([^)]+\))?\s*:\s*(.*)", stripped)
            if param_match:
                p_name, p_desc = param_match.groups()
                param_descriptions[p_name] = p_desc.strip()
                current_param = p_name
            elif current_param and line.startswith("    ") and stripped:
                # Multi-line description continuation
                param_descriptions[current_param] += " " + stripped
        else:
            description_lines.append(stripped)

    # 3. JSON Schema Mapping Logic
    def resolve_json_type(annotation) -> Dict:
        """Recursively maps Python types to JSON Schema types."""
        # Handle Annotated[T, metadata]
        if get_origin(annotation) is Annotated:
            inner_args = get_args(annotation)
            base = inner_args[0]
            schema = resolve_json_type(base)
            # Check for description metadata
            for meta in inner_args[1:]:
                if isinstance(meta, str):
                    schema["description"] = meta
                elif hasattr(meta, 'description'):
                    schema["description"] = getattr(meta, 'description')
            return schema

        origin = get_origin(annotation)
        args = get_args(annotation)

        # Handle Union (including Optional[T] which is Union[T, None])
        if origin is Union:
            pure_args = [a for a in args if a is not type(None)]
            if len(pure_args) == 1:
                return resolve_json_type(pure_args[0])
            return {"anyOf": [resolve_json_type(a) for a in pure_args]}

        # Handle Literals (Enums equivalent in typing)
        if origin is Literal:
            return {"enum": list(args)}

        # Handle standard Python Enums
        if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
            return {
                "type": "string",
                "enum": [e.value for e in annotation],
                "description": f"Must be one of: {', '.join([e.name for e in annotation])}"
            }

        # Handle Lists/Arrays
        if origin in (list, List) or annotation is list:
            item_schema = {"type": "string"}
            if args:
                item_schema = resolve_json_type(args[0])
            return {"type": "array", "items": item_schema}
        
        # Handle Dicts/Objects
        if origin in (dict, Dict) or annotation is dict:
            return {"type": "object"}

        # Primitive Mapping
        mapping = {
            str: "string", int: "integer", float: "number", bool: "boolean", bytes: "string",
        }
        # Fallback for common string-named types
        if annotation == "str": 
            return {"type": "string"}
        if annotation == "int": 
            return {"type": "integer"}
        if annotation == "float": 
            return {"type": "number"}
        if annotation == "bool": 
            return {"type": "boolean"}

        return {"type": mapping.get(annotation, "string")}

    # 4. Construct Final Parameters Object
    params_schema = {"type": "object", "properties": {}, "required": []}

    for name, param in sig.parameters.items():
        # Skip framework-specific arguments
        if name in ["self", "task_run", "task_context"]:
            continue

        # Generate type schema
        p_annotation = type_hints.get(name, param.annotation)
        field_schema = resolve_json_type(p_annotation)
        
        # Attach description from docstring if metadata didn't provide one
        if "description" not in field_schema or not field_schema["description"]:
            field_schema["description"] = param_descriptions.get(name, "")

        # Set Default vs Required
        if param.default is inspect.Parameter.empty:
            params_schema["required"].append(name)
        else:
            field_schema["default"] = param.default

        params_schema["properties"][name] = field_schema
    description = "\n".join(description_lines)
    #params_schema["description"] = description
    return description, params_schema
