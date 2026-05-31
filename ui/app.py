from runtime.agents.agents import Agents
from runtime.pipe.pipes import Pipes
from runtime.session.sessions import Sessions
from runtime.project.projects import Projects
from runtime.skill.skills import  Skills
from runtime.workspace.workspaces import Workspaces
from runtime.cron.crons import Cronjobs

from server.models.project import Project
from server.models.providers.api_provider import ApiProvider
from ui.lib.pyHtmlGui.pyhtmlgui.lib.observable import Observable
from server.models.system import System

class UiApp(Observable):
    def __init__(self):
        super().__init__()
        self.projects = Projects()
        self.workspaces = Workspaces()

        self.agents = Agents()
        self.pipes = Pipes()
        self.sessions = Sessions()
        self.skills = Skills()
        self.cronjobs = Cronjobs()
