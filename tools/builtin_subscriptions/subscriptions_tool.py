from core.models.prompt_string import Prompt
from tools.base.base_tool import BaseTool
from .models.tool_subscription import ToolSubscription
from .prompts import TOOLS, PROMPTS
from .apps import ToolsBuiltinSubscriptionsConfig
import traceback

class SubscriptionsTool(BaseTool):
    DESCRIPTION = "Create and manage subscriptions to recurring shell commands or Python scripts. This allows the agent to maintain situational awareness by receiving automatic, live updates of contextual information."
    TOOLS = TOOLS
    PROMPTS = PROMPTS

    def get_header_parts(self):
        instructionsTemplate = Prompt.get_template(self.agentInstance, source=ToolsBuiltinSubscriptionsConfig.name, key="instructions")
        functionsTemplate    = Prompt.get_template(self.agentInstance, source=ToolsBuiltinSubscriptionsConfig.name, key="functions")
        return [
            {"tpId": instructionsTemplate.pk, "tags": ["Prompts", "Subscriptions"], "data": {} },
            {"tpId": functionsTemplate.pk, "tags": ["Prompts", "Subscriptions"], "data": {} },
        ]

    def unsubscribe(self, subscription_id: str, toolCall=None):
        try:
            subscription = ToolSubscription.objects.get(agentInstance=self.agentInstance, subscription_id=subscription_id, is_active=True)
            subscription.is_active = False
            subscription.save()
            return (True, {"status": "success", "message": f"Subscription '{subscription_id}' has been successfully unsubscribed."})
        except ToolSubscription.DoesNotExist:
            return (False, {"status": "error", "message": f"No active subscription found with ID '{subscription_id}'."})
        except Exception as e:
            return (False, {"status": "error", "message": f"An unexpected error occurred: {str(e)} {traceback.format_exc()}"})
