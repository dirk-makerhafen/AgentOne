from runtime.agents.agent import Agents, Instances, Projects, Skills

from server.models.project import Project
from server.models.providers.api_provider import ApiProvider
from server.models.skill import Skill
from ui.lib.pyHtmlGui.pyhtmlgui.lib.observable import Observable
from server.models.system import System

class UiApp(Observable):
    def __init__(self):
        super().__init__()
        self.projects = Projects()
        self.agents = Agents()
        self.instances = Instances()
        self.skills = Skills()

        #self.systems = System.objects
        #self.providers = ApiProvider.objects
        #self.projects = Project.objects
        #self.skills = Skill.objects
