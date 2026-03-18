import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('agentTasks')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

# Celery Beat scheduled tasks
app.conf.beat_schedule = {
    'poll-remote-executors-every-30-seconds': {
        'task': 'systems.tasks.heartbeat.poll_remote_executors_for_heartbeat',
        'schedule': 120.0, # Run every 30 seconds
        'options': {
            'queue': 'celery' # Ensure this runs on the main server's default queue
        },
    },
}