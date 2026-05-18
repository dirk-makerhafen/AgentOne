
from registry.task_decorators import command
from runtime.agents.session import Session

'''
@group(description="building group task")
def group(runtime, *tasks):
    return tasks

@chain(description="building chain task")
def chain(runtime, *tasks):
    return tasks
'''

@command()
def ping(session: Session, message: str|None = None):
    r = f"Pong from Agent {session.agent.name}, Version {session.agent.version_number}, Session {session.name}"
    if message:
        r += f"\nMessage received:{message}"
    return r
