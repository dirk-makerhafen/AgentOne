from __future__ import annotations
import html
from pathlib import Path
from typing import TYPE_CHECKING
from server.models.sessions.session import SessionModel
from server.models.terminal import TerminalSession
from ui.lib.model_view import ModelView


if TYPE_CHECKING:
    from ui.main.rightpanel.session.rightpanel_session import RightPanelSession


#: Lines of log tail shown for the selected terminal.
LOG_TAIL_LINES = 40


class RightPanelSessionTerminals(ModelView):
    """Read-only viewer for a session's persistent terminals.

    Agent-only control: the agent drives terminals through the
    ``terminal_*`` tools. This tab lists them (name, status, tmux
    liveness, cwd, last activity), shows the tail of the selected
    terminal's log, and offers Refresh / Kill. There is no input path.
    """
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
    TEMPLATE_STR = '''
        <div class="panel-header">
            <span>Terminals</span>
            <div class="panel-actions">
                <button class="panel-icon-btn" onclick="pyview.refresh()" title="Refresh">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
                </button>
            </div>
        </div>
        <div style="flex:1;overflow-y:auto;padding:8px">
            {% if pyview.terminals %}
            {% for t in pyview.terminals %}
            <div class="terminal-item" style="display:flex;align-items:center;gap:8px;padding:6px 0">
                <span title="{{ t.status }}{% if t.alive %} (tmux live){% else %} (tmux not live){% endif %}" style="flex-shrink:0;width:8px;height:8px;border-radius:50%;background:{% if t.alive %}var(--success){% elif t.status == 'running' %}var(--warning){% else %}var(--muted){% endif %}"></span>
                <div style="flex:1;min-width:0">
                    <div style="font-size:13px;font-weight:500;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ t.name }}</div>
                    <div style="font-size:10px;color:var(--muted);margin-top:1px">{{ t.status }}{% if t.cwd %} · {{ t.cwd }}{% endif %}{% if t.last_active_at %} · {{ t.last_active_at }}{% endif %}</div>
                </div>
                <button class="btn btn-sm btn-outline" onclick="pyview.select('{{ t.name }}')" style="flex-shrink:0;font-size:11px;padding:2px 8px;border-radius:4px;cursor:pointer;background:none;border:1px solid var(--border2);color:var(--text)">View</button>
                <button class="btn btn-sm btn-outline" onclick="pyview.kill('{{ t.name }}')" style="flex-shrink:0;font-size:11px;padding:2px 8px;border-radius:4px;cursor:pointer;background:none;border:1px solid var(--border2);color:var(--text)">Kill</button>
            </div>
            {% endfor %}
            {% else %}
            <div style="font-size:12px;color:var(--muted);padding:8px 0">No terminals yet — the agent creates them with terminal_exec.</div>
            {% endif %}
            {% if pyview.selected_output %}
            <div style="border-top:1px solid var(--border2);margin:8px 0"></div>
            <div class="section-label" style="font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;margin:4px 0 8px">Output: {{ pyview.selected_name }}</div>
            <pre style="font-size:11px;line-height:1.4;background:var(--bg2);border:1px solid var(--border2);border-radius:4px;padding:8px;white-space:pre-wrap;word-break:break-word;max-height:400px;overflow-y:auto">{{ pyview.selected_output }}</pre>
            {% endif %}
            <div style="font-size:10px;color:var(--muted);padding:8px 0">Read-only — only the agent can type into a terminal.</div>
        </div>
    '''

    def __init__(self, subject: SessionModel, parent: RightPanelSession, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.selected_name: str | None = None

    @property
    def terminals(self) -> list[dict]:
        """This session's terminals, newest first (liveness when tmux is up)."""
        try:
            from runtime.terminal.manager import list_terminals

            rows = list_terminals(self.subject)
            return sorted(rows, key=lambda r: r["name"])
        except Exception:  # pylint: disable=broad-exception-caught
            # No tmux binary / libtmux — fall back to DB rows.
            return [
                {
                    "name": row.name,
                    "status": row.status,
                    "tmux": row.tmux_session_name,
                    "alive": False,
                    "cwd": row.cwd,
                    "last_active_at": str(row.last_active_at) if row.last_active_at else None,
                }
                for row in TerminalSession.objects.filter(session=self.subject).order_by("name")
            ]

    @property
    def selected_output(self) -> str:
        """Escaped tail of the selected terminal's log file (or live buffer)."""
        if not self.selected_name:
            return ""
        text = ""
        row = TerminalSession.objects.filter(
            session=self.subject, name=self.selected_name
        ).first()
        if row is not None and row.log_path:
            try:
                lines = Path(row.log_path).read_text(errors="replace").splitlines()
                text = "\n".join(lines[-LOG_TAIL_LINES:])
            except OSError:
                text = ""
        if not text:
            try:
                from runtime.terminal.manager import poll_output

                result = poll_output(self.subject, name=self.selected_name, lines=LOG_TAIL_LINES)
                text = result.get("output", "")
            except Exception:  # pylint: disable=broad-exception-caught
                text = ""
        if not text:
            return "(no output captured yet)"
        if len(text) > 8000:
            text = "...[truncated]...\n" + text[-8000:]
        return html.escape(text)

    def select(self, name: str) -> None:
        self.selected_name = name
        self.update()

    def refresh(self) -> None:
        self.update()

    def kill(self, name: str) -> None:
        try:
            from runtime.terminal.manager import kill_terminal

            kill_terminal(self.subject, name=name)
        except Exception:  # pylint: disable=broad-exception-caught
            TerminalSession.objects.filter(session=self.subject, name=name).update(status="dead")
        if self.selected_name == name:
            self.selected_name = None
        self.update()
