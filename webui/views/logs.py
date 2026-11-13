"""Log viewer: a file picker and a tail fragment that polls."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.http import Http404
from django.shortcuts import render

from webui.views.common import render_page


def _log_dir() -> Path | None:
    if not getattr(settings, "LOG_DIR", None):
        return None
    return Path(settings.LOG_DIR)


def log_files() -> list[str]:
    directory = _log_dir()
    if directory is None or not directory.is_dir():
        return []
    return sorted(path.name for path in directory.glob("*.log") if path.is_file())


def _resolve(name: str) -> Path:
    directory = _log_dir()
    if directory is None:
        raise Http404("logging is disabled")
    candidate = (directory / name).resolve()
    if candidate.parent != directory.resolve() or not candidate.is_file():
        raise Http404("unknown log file")
    return candidate


def tail(path: Path, lines: int = 200) -> str:
    """Return the last *lines* lines of *path* (best effort, bounded read)."""
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            block = min(size, 256 * 1024)
            handle.seek(size - block)
            data = handle.read()
    except OSError:
        return ""
    text = data.decode("utf-8", "replace")
    return "\n".join(text.splitlines()[-lines:])


def logs(request):
    files = log_files()
    selected = request.GET.get("file") or (files[0] if files else "")
    content = ""
    if selected:
        try:
            content = tail(_resolve(selected))
        except Http404:
            selected = ""
    context = {
        "error": request.GET.get("error", ""),
        "selected_file": selected,
        "content": content,
    }
    return render_page(request, "logs", "webui/logs/page.html", context)


def logs_tail(request):
    name = request.GET.get("file") or ""
    try:
        lines = max(20, min(int(request.GET.get("lines") or 200), 2000))
    except ValueError:
        lines = 200
    if not name:
        files = log_files()
        if not files:
            return render(request, "webui/logs/_tail.html", {"content": "", "file": ""})
        name = files[0]
    path = _resolve(name)
    return render(
        request,
        "webui/logs/_tail.html",
        {"content": tail(path, lines), "file": name},
    )
