from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from server.models.system import System, SystemStatus
import logging
from django.db.models import Q

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Checks the last heartbeat of each system and marks them as offline if they are stale.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Running heartbeat check...")

        stale_threshold = timezone.now() - timedelta(minutes=2)

        # Find systems that are currently 'online' and either have a stale heartbeat OR no heartbeat at all
        online_and_stale_systems = System.objects.filter(
            status='online'
        ).filter(
            Q(last_heartbeat__lt=stale_threshold) | Q(last_heartbeat__isnull=True)
        )

        stale_count = online_and_stale_systems.count() # Use count() for QuerySet
        if stale_count > 0:
            self.stdout.write(f"Found {stale_count} stale system(s) to mark as offline.")
            for system in online_and_stale_systems:
                system.status =  SystemStatus.OFFLINE
                system.save() 
                self.stdout.write(f"Marked system '{system.name}' (ID: {system.pk}) as offline.")
        else:
            self.stdout.write("No stale systems found.")

        # Check for systems that are offline but have a recent heartbeat
        offline_but_fresh_systems = System.objects.filter(
            status='offline',
            last_heartbeat__gte=stale_threshold
        )

        fresh_count = offline_but_fresh_systems.count()
        if fresh_count > 0:
            self.stdout.write(f"Found {fresh_count} system(s) marked offline but with a recent heartbeat. Marking them online.")
            for system in offline_but_fresh_systems:
                system.status = SystemStatus.ONLINE
                system.save()
                self.stdout.write(f"Marked system '{system.name}' (ID: {system.pk}) as online.")

        self.stdout.write(self.style.SUCCESS("Heartbeat check complete."))

                                                                                                                                                                                                                                                                                                                                                                                                                        


