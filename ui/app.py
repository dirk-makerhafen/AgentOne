from typing import Any

from runtime.agents.agents import Agents
from runtime.session.sessions import Sessions
from runtime.project.projects import Projects
from runtime.skill.skills import  Skills
from runtime.workspace.workspaces import Workspaces
from runtime.cron.crons import Cronjobs
from runtime.settings import UserSettings

from server.models.project import Project
from server.models.providers.api_provider import ApiProvider
from ui.lib.pyHtmlGui.pyhtmlgui.lib.observable import Observable
from server.models.system import System
from ui.live import LiveSession
from ui.model_observer import ModelObserver


class UiApp(Observable):
    _instance = None

    def __init__(self):
        super().__init__()
        UiApp._instance = self
        self.settings = UserSettings()
        self.projects = Projects()
        self.workspaces = Workspaces()

        self.agents = Agents()
        self.sessions = Sessions()
        self.skills = Skills()
        self.cronjobs = Cronjobs()

        self._live_sessions: dict[int, LiveSession] = {}
        self.model_observer = ModelObserver()

    @classmethod
    def get_instance(cls):
        return cls._instance

    def get_live_session(self, session_id: int) -> LiveSession:
        if session_id not in self._live_sessions:
            self._live_sessions[session_id] = LiveSession(session_id)
        return self._live_sessions[session_id]

    def dispatch_session_event(
        self, session_id: int | None, event_type: str, payload: dict[str, Any]
    ) -> None:
        if event_type == "model_event":
            try:
                with open("/tmp/agentone_events.log", "a") as _f:
                    import time
                    _f.write(f"[{time.strftime('%H:%M:%S')}] UiApp.dispatch: "
                             f"model={payload.get('model_name')} "
                             f"action={payload.get('action')} "
                             f"pk={payload.get('pk')} "
                             f"fc={payload.get('filter_context')}\n")
            except Exception:
                pass
            self.model_observer.dispatch(
                payload.get("model_name", ""),
                payload.get("action", ""),
                payload.get("pk"),
                payload.get("filter_context", {}),
            )
            return
        ls = self._live_sessions.get(session_id) if session_id else None
        if ls is not None:
            ls.notify_observers()
