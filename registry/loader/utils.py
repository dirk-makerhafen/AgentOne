from pathlib import Path
import textwrap

def find_agent_md_files(root_dir: Path):
    """Recursively find agent.md files, deduplicating nested paths."""
    paths = sorted(root_dir.glob("**/agent.md"), key=lambda p: len(p.parts))
    result = []
    for p in paths:
        parent_str = p.parent.as_posix()
        if not any(parent_str.startswith(other.parent.as_posix()) for other in result):
            result.append(p)
    return result

def build_version_kwargs(entry, description, schema, commit, path, task_type, task_execution_mode):
    """Build TaskDefinitionVersion filter kwargs from a manifest entry."""
    kw = {
        "description": textwrap.dedent(description),
        "function_schema": schema or {},
        "task_type": task_type,
        "task_execution_mode": task_execution_mode,
        "function_name": entry.get("function", "") or "",
        "path": path.as_posix() if path else "",
        "commit": commit,
        "bound": entry.get("bound", False),
    }
    for opt_field in ("requires_approval", "max_retries", "retry_delay", "retry_requires_approval", "priority", "thinking"):
        val = entry.get(opt_field)
        if val is not None:
            kw[opt_field] = val
    return kw

