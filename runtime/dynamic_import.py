"""Import a Python file by path with proper ``sys.modules`` registration.

``importlib.util.module_from_spec`` does not register the new module.  Decorators
such as :func:`dataclasses.dataclass` look the defining module up in
``sys.modules`` while the module body executes, so executing a spec without this
registration fails with ``AttributeError: 'NoneType' object has no attribute
'__dict__'``.  Keep the module registered after a successful load (runtime code
may define dataclasses lazily) and restore the previous entry on failure.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def exec_module_from_path(module_name: str, file_path: Path | str) -> ModuleType:
    """Execute *file_path* as *module_name* and return the loaded module."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load Python module from {file_path}")
    module = importlib.util.module_from_spec(spec)

    had_previous = module_name in sys.modules
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        if had_previous:
            sys.modules[module_name] = previous
        else:
            sys.modules.pop(module_name, None)
        raise
    return module
