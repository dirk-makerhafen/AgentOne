from celery import shared_task

@shared_task
def execute_event(eventExecution_id):
    from agents.models.agentevents import EventExecution

    eventExecution = EventExecution.objects.get(pk=eventExecution_id)
    eventExecution.run()
