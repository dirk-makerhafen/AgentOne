from runtime.agents.agents import Agents
from runtime.agents.sessions import Sessions
from runtime.agents.projects import Projects
from runtime.agents.skills import  Skills
from runtime.agents.workspaces import Workspaces
from runtime.agents.crons import Cronjobs

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
        self.sessions = Sessions()
        self.skills = Skills()
        self.cronjobs = Cronjobs()

        #self.systems = System.objects
        #self.providers = ApiProvider.objects
        #self.projects = Project.objects
        #self.skills = Skill.objects
