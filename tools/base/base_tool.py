

class BaseTool():
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
    