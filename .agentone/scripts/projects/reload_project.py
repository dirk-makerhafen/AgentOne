from __future__ import annotations


def reload_project(project_path: str) -> tuple[bool, dict]:
    '''
    Run ``reload_all`` on a project to sync its manifest files into the
    database.

    Call this after creating or editing any manifest files (agent.md,
    scripts.md, cron.md, etc.) in the project's ``.agentone/`` directory.
    Returns a summary of what was loaded and any errors encountered.

    Args:
        project_path: Absolute path to the project root directory (containing
            ``.agentone/``).

    Returns:
        A tuple of (success, result).
        On success/partial success, result contains:
            - status: "success" | "partial"
            - summary: human-readable summary of what was loaded
            - counts: dict with per-category counts (agents, scripts, ...)
            - details: list of per-item dicts (name, type, action)
            - errors: list of error strings (empty on full success)
        On error (folder not found, no .agentone/), result contains:
            - status: "error"
            - summary: str
            - message: str
    '''
    try:
        from registry.management.commands.reload_all import run_reload_all
        result = run_reload_all(project_path)
    except Exception as e:
        return (False, {"status": "error", "summary": str(e), "message": f"reload_all failed: {e}"})

    if result["status"] == "error":
        return (False, {"status": "error", "summary": result["summary"], "message": result["summary"]})

    success = result["status"] == "success"
    return (success, {
        "status": result["status"],
        "summary": result["summary"],
        "counts": result["counts"],
        "details": result["details"],
        "errors": result["errors"],
    })
