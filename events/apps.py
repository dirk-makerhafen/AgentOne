from django.apps import AppConfig
import sys
from django.db.utils import OperationalError



class EventsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'events'

    def ready(self):

        if 'manage.py'  in sys.argv and 'migrate' in sys.argv:
            try:
                from events.models.event_type import EventType, EventTypes
                for e in EventTypes:
                    EventType.objects.get_or_create(
                        name=e.value[0],
                        defaults={"description": e.value[1]},
                    )
            except OperationalError:
                pass