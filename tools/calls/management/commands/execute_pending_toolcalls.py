from django.core.management.base import BaseCommand
import logging

from agents.models.agent_instance import AgentInstance
from agents.tasks.execute_query import decide_next_step
from tools.calls.models.tool_call import ToolCall

logger = logging.getLogger(__name__)

class Command(BaseCommand):

    def handle(self, *args, **kwargs):

        agentInstances = AgentInstance.objects.all()
        for agentInstance in agentInstances:
            toolCalls = agentInstance.toolCalls.filter(status=ToolCall.ToolCallStatusChoices.PENDING)
            if toolCalls.count() > 0:
                agentInstance.set_status(AgentInstance.AgentInstanceStatusChoices.EXECUTING_TOOLS)
                for tc in toolCalls:
                    try:
                        tc.run()
                    except:
                        pass
            decide_next_step(agentInstance)
      
