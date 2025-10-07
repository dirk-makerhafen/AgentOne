
from core.models.prompt_string import PromptString
from tools.base.base_tool import BaseTool
from .prompts import FUNCTIONS
from .apps import ToolsBuildinUserinteractionConfig

class UserInteractionTool(BaseTool):
    DESCRIPTION = "Allows the agent to pause its operation and wait for direct input from the user. Essential for seeking clarification, confirmation, or further instructions before proceeding with a task."
    functions = FUNCTIONS

    def get_header_parts(self):
        instructionTemplate = PromptString.get_template(self.agentInstance, source=ToolsBuildinUserinteractionConfig.name, key="Instructions")
        functionsTemplate   = PromptString.get_template(self.agentInstance, source=ToolsBuildinUserinteractionConfig.name, key="Functions")
        return [
            {"tpId": instructionTemplate.pk, "data": {}, 'tags': ['Prompts', 'UserInteraction'] },
            {"tpId": functionsTemplate.pk  , "data": {}, 'tags': ['Prompts', 'UserInteraction'] },
        ]

    def await_user_input(self, toolCall, reason = ""):
        """
        Sets the agent instance's require_user_interaction flag to True.
        The state machine will handle the status change.
        """
        try:
            self.agentInstance.require_user_interaction = True
            self.agentInstance.save(send_to_client=False)
            return (True, 'Successfully paused. Awaiting user input.')
        except Exception as e:
            return (False, f'An error occurred while trying to await user input: {str(e)}')

    def get_history_limiting_rules(self):
        return [
            {
                'group_name': "User Interaction",
                'name': 'await',
                'description': 'General limit for all user interaction calls.',
                'match': lambda tc: tc.function_name == 'await_user_input',
                'key': lambda tc: '',
                'limits': {
                    'pending': self.agentInstance.limit_max_conversation_messages, 
                    'success': 5, 
                    'failed': 3, 
                    'max': 8
                }
            }
        ]
