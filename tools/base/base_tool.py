from typing import Any, Dict, List


class BaseTool():
    DESCRIPTION = "NOT SET"
    TOOLS = {}
    PROMPTS = {}

    def __init__(self, agentInstance):
        self.agentInstance = agentInstance
   
    def get_functions(self):
        return {f"{f}":{
            "callable": self.__getattribute__(f), 
            "description": item["description"], 
            "arguments": item["parameters"]
        } for f, item in self.functions.items()}
    
    def get_content_parts(self):
        return []
    
    def list_tools(self) -> List[Dict[str, Any]]:
        return self.TOOLS
    
    def list_prompts(self, cursor = None):
        return self.PROMPTS
    
    def list_resources(self, cursor = None):
        return []
    
    def list_resource_templates(self, cursor = None):
        return []

    def read_resource(self, uri):
        return None

    def get_prompt(self, name, arguments = None):
        return None

    def call_tool(self, name, toolCall=None, arguments = None, read_timeout_seconds = None, progress_callback = None):
        return getattr(self, name)(toolCall=toolCall, **arguments)
