from server.models.agents.agent import Agent
from server.models.agents.agent_instance import AgentInstance

from server.models.providers.api_provider import ApiProvider
from ui.pyHtmlGui.pyhtmlgui.lib.observable import Observable
from server.models.system import System

class UiApp(Observable):
    def __init__(self):
        super().__init__()
        self.agents = Agent.objects
        self.agent_instances = AgentInstance.objects
        #self.prompts = PromptsModel.objects
        self.systems = System.objects
        self.providers = ApiProvider.objects
