from django.contrib import admin

from events.models.event_execution import EventExecution
from events.models.event_subscription import EventSubscription
from .models.event_handler import EventHandler

@admin.register(EventHandler)
class EventHandlerAdmin(admin.ModelAdmin):
    list_display = ('name', 'receiver_agent', 'receiver_agentInstance', 'event', 'enabled', "source_path", "source_string", "source_function_name")
    list_filter = ('receiver_agent', 'receiver_agentInstance', 'event', 'enabled', "source_path", "source_string", "source_function_name")
    search_fields = ('name', 'description', 'source')

@admin.register(EventSubscription)
class EventSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('description', 'emitter_agent', 'emitter_agentInstance', 'eventHandler')
    list_filter = ('emitter_agent', 'emitter_agentInstance',  'eventHandler__name')
    search_fields = ('description',)

@admin.register(EventExecution)
class EventEventExecutionAdmin(admin.ModelAdmin):
    pass