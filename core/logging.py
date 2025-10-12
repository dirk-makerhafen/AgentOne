from django.contrib.auth.models import User
from core.tasks.send_websocket_update import celery_send_websocket_update

def log_to_clients(message, level='info', users=None):
    """
    Sends a structured log message to specific users or all users via WebSocket.

    Args:
        message (str): The log message content.
        level (str): The log level ('info', 'warn', 'error', 'debug').
        users (QuerySet or list): A queryset or list of User objects to send the log to.
                                  If None, the message is broadcast to all users.
    """
    print(f"LOG [{level.upper()}]: {message}") # Keep server-side log

    message_data = {
        'object': 'ConsoleOutput',
        'message': message,
        'level': level
    }

    user_pks = []
    if users is not None:
        # If users is a queryset, we can get pks directly
        if hasattr(users, 'values_list'):
            user_pks = users.values_list('pk', flat=True)
        # If it's a list of user objects
        else:
            user_pks = [user.pk for user in users]
    else:
        # Broadcast to all users if no specific users are provided
        user_pks = User.objects.values_list('pk', flat=True)

    for pk in user_pks:
        celery_send_websocket_update.delay(message_data, user_pk=pk)
