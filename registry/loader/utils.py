from pathlib import Path
import textwrap
from typing import Any, Dict, List, Optional

from server.models.enums.task_enums import TaskExecutionMode, TaskType


def find_agent_md_files(root_dir: Path) -> List[Path]:
    """Recursively find agent.md files, deduplicating nested paths."""
    paths = sorted(root_dir.glob("**/agent.md"), key=lambda p: len(p.parts))
    result: List[Path] = []
    for p in paths:
        parent_str = p.parent.as_posix()
        if not any(parent_str.startswith(other.parent.as_posix()) for other in result):
            result.append(p)
    return result


def build_version_kwargs(
    entry: dict,
    description: str,
    schema: dict,
    commit: str|None,
    path: Optional[Path],
    task_type: TaskType,
    task_execution_mode: TaskExecutionMode,
) -> Dict[str, Any]:
    """Build ``TaskDefinitionVersion`` filter kwargs from a manifest entry.

    Returns a dict suitable for ``get_or_create`` that includes the function
    schema, type info, and any optional overrides (e.g. retry config).
    """
    kw: Dict[str, Any] = {
        "description": textwrap.dedent(description),
        "function_schema": schema or {},
        "task_type": task_type,
        "task_execution_mode": task_execution_mode,
        "function_name": entry.get("function", "") or "",
        "path": path.as_posix() if path else "",
        "commit": commit,
        "bound": entry.get("bound", False),
    }
    for opt_field in (
        "requires_approval",
        "max_retries",
        "retry_delay",
        "retry_requires_approval",
        "priority",
        "thinking",
    ):
        val = entry.get(opt_field)
        if val is not None:
            kw[opt_field] = val
    return kw
