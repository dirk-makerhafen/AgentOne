from common.models import PromptString
from executor.primitives import run_shell_script
from tools_common.models import BaseTool
from tools_subscriptions.models import ToolSubscription
from .prompts import FUNCTIONS

class ShellTool(BaseTool):
    functions = FUNCTIONS

    def get_header_parts(self):
        descriptionTemplate = PromptString.get_template(self.agentInstance, source="Tools.Shell", key="Description")
        functionsTemplate = PromptString.get_template(self.agentInstance, source="Tools.Shell", key="Functions")
        return [
            {"tpId": descriptionTemplate.pk, "tags": ["Prompts", "Shell"], "data": {} },
            {"tpId": functionsTemplate.pk, "tags": ["Prompts", "Shell"], "data": {} },
        ]

    def shell(self, source, interpreter="auto", subscription_id=None, mode="one-shot", toolCall=None):
        if mode == "subscribe":
            if not subscription_id:
                return (False, {"status": "error", "message": "A unique 'subscription_id' is required when mode is 'subscribe'."})

            subscription_args = {
                "source": source,
                "interpreter": interpreter,
            }

            ToolSubscription.objects.update_or_create(
                agentInstance=self.agentInstance,
                subscription_id=subscription_id,
                defaults={
                    'agent': self.agentInstance.agent,
                    'creating_tool_call': toolCall,
                    'tool_name': 'shell',
                    'arguments': subscription_args,
                    'is_active': True
                }
            )

        result = run_shell_script(agentInstance=self.agentInstance, script=source, interpreter=interpreter)
        
        success = result.get("return_code") == 0 and result.get("status") == "success"

        if mode == "subscribe":
            if "message" not in result:
                result["message"] = ""
            result["message"] += f"\nSuccessfully created/updated subscription with ID '{subscription_id}'."

        return (success, result)

    def get_history_limiting_rules(self):
        limit = self.agentInstance.limit_max_conversation_messages
        return [
            {'group_name': "Shell", 'name': 'any', 'description': 'General limit for all shell tool calls.', 'match': lambda tc: tc.function_name == 'shell', 'key': lambda tc: '', 'limits': {'pending': limit, 'success': limit, 'failed': 3, 'max': limit}},
        ]
