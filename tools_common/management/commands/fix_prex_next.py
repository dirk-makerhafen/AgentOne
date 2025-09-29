from django.core.management.base import BaseCommand
from agent.models.agent import AgentInstance
from agent.tasks import decide_next_step
import logging

from tools_filesystem.models import FsDirectoryLogEntry, FsLogEntry

logger = logging.getLogger(__name__)

class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        '''
        agentInstances = AgentInstance.objects.all()
        for agentInstance in agentInstances:
            is_loaded = False
            is_deleted = False
            for e in agentInstance.fsDirectoryLogEntries.all().order_by("pk"):
                if e.action == "load":
                    is_loaded = True
                elif e.action == "unload":
                    is_loaded = False
                elif e.action == "delete":
                    is_deleted = True
                else:
                    is_deleted = False
                print(e.is_loaded , is_loaded)
                e.is_loaded = is_loaded
                e.deleted_on_filesystem = is_deleted
                e.save(send_to_client=False)                
        '''
        return

        items = FsLogEntry.objects.all()
        for item in items:
            item.next_version = None
            item.save(send_to_client=False)
        for item in items:  
            next_item = FsLogEntry.objects.filter(agentInstance=item.agentInstance, path=item.path, pk__gt=item.pk).order_by("pk").first()
            if next_item:
                item.next_version = next_item
                item.save(send_to_client=False)
                print("updated")
            print(item.next_version)
        
     