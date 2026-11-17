from pathlib import Path

from django.conf import settings


def _log_files() -> list[str]:
    if not settings.LOG_DIR:
        return []
    try:
        return sorted(p.name for p in Path(settings.LOG_DIR).glob("*.log"))
    except OSError:
        return []


def build_sidebar_context(request, project_id, ctx):
    files = _log_files()
    ctx["log_files"] = files
    ctx["log_dir"] = str(settings.LOG_DIR or "")
    ctx["selected_log"] = request.GET.get("file") or (files[0] if files else "")


def sidebar_keys(context):
    return ()


def register_sidebar_component():
    from webui.core.components import register_section_sidebar

    register_section_sidebar("logs", sidebar_keys)
