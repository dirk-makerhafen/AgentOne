from django.core.management.base import BaseCommand
from agent.models.agent import AgentInstance
from agent.tasks import decide_next_step
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):

    def handle(self, *args, **kwargs):

        agentInstances = AgentInstance.objects.all()
        for agentInstance in agentInstances:
            toolCalls = agentInstance.toolCalls.filter(status="pending")
            if toolCalls.count() > 0:
                agentInstance.status = 'EXECUTING_TOOLS'
                agentInstance.save()
                for tc in toolCalls:
                    try:
                        tc.run()
                    except:
                        pass
            decide_next_step(agentInstance)
      
