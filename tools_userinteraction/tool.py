from common.models import PromptString
from tools_common.models import BaseTool
from tools_userinteraction.prompts import FUNCTIONS

class UserInteractionTool(BaseTool):
    functions = FUNCTIONS

    def get_header_parts(self):
        descriptionTemplate = PromptString.get_template(self.agentInstance, source="Tools.UserInteraction", key="Description")
        functionsTemplate = PromptString.get_template(self.agentInstance, source="Tools.UserInteraction", key="Functions")
        return [
            {"tpId": descriptionTemplate.pk, "data": {}, 'tags': ['Prompts', 'UserInteraction'] },
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
