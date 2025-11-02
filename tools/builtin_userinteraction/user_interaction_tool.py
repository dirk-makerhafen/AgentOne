
from agents.models.llm_query import QueryMessagePart
from core.models.prompt import Prompt
from tools.base.base_tool import BaseTool
from .prompts import TOOLS, PROMPTS
from .apps import ToolsBuiltinUserinteractionConfig
import traceback

class UserInteractionTool(BaseTool):
    DESCRIPTION = "Allows the agent to pause its operation and wait for direct input from the user or other agents. Essential for seeking clarification, confirmation, or further instructions before proceeding with a task."
    TOOLS = TOOLS
    PROMPTS = PROMPTS

    def get_header_parts(self):
        instructionTemplate = Prompt.get_template(self.agentInstance, source=ToolsBuiltinUserinteractionConfig.name, key="instructions")
        functionsTemplate   = Prompt.get_template(self.agentInstance, source=ToolsBuiltinUserinteractionConfig.name, key="functions")
        return [
            QueryMessagePart(promptVariant=instructionTemplate, tags=["Prompts", "UserInteraction"]),
            QueryMessagePart(promptVariant=functionsTemplate  , tags=["Prompts", "UserInteraction"])
        ]
        #return [
        #    {"tpId": instructionTemplate.pk, "data": {}, 'tags': ['Prompts', 'UserInteraction'] },
        #    {"tpId": functionsTemplate.pk  , "data": {}, 'tags': ['Prompts', 'UserInteraction'] },
        #]

    def await_input(self, toolCall, reason = ""):
        """
        Sets the agent instance's require_user_interaction flag to True.
        The state machine will handle the status change.
        """
        try:
            self.agentInstance.require_user_interaction = True
            self.agentInstance.save(send_to_client=False)
            return (True, 'Successfully paused. Awaiting user input.')
        except Exception as e:
            return (False, f'An error occurred while trying to await user input: {str(e)}{traceback.format_exc()}')

    def get_history_limiting_rules(self):
        return [
            {
                'group_name': "User Interaction",
                'name': 'await',
                'description': 'General limit for all user interaction calls.',
                'match': lambda tc: tc.function_name == 'await_input',
                'key': lambda tc: '',
                'limits': {
                    'pending': self.agentInstance.effective_limit_max_conversation_messages, 
                    'success': 5, 
                    'failed': 3, 
                    'max': 8
                }
            }
        ]
