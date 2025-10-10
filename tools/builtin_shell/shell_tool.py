from core.models.prompt_string import PromptString
from tools.primitives import run_shell_script
from tools.base.base_tool import BaseTool
from tools.builtin_subscriptions.models.tool_subscription import ToolSubscription
from .prompts import FUNCTIONS
from .apps import ToolsBuiltinShellConfig

class ShellTool(BaseTool):
    DESCRIPTION = "Executes arbitrary shell commands and scripts in bash, PowerShell, or cmd. Fundamental for interacting with the operating system, running programs, and managing system-level tasks."
    functions = FUNCTIONS

    def get_header_parts(self):
        instructionsTemplate = PromptString.get_template(self.agentInstance, source=ToolsBuiltinShellConfig.name, key="Instructions")
        functionsTemplate = PromptString.get_template(self.agentInstance, source=ToolsBuiltinShellConfig.name, key="Functions")
        return [
            {"tpId": instructionsTemplate.pk, "tags": ["Prompts", "Shell"], "data": {} },
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

        result = run_shell_script(agentInstance=self.agentInstance, script=source, interpreter=interpreter, cwd=self.agentInstance.workingdir)
        
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
