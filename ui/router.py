MESSAGE_HANDLERS = {}

def register_handler(message_type):
    def decorator(func):
        MESSAGE_HANDLERS[message_type] = func
        return func
    return decorator
