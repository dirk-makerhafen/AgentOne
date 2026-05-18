
from registry.task_decorators import task

from registry.task_decorators import task
from runtime.agents.session import Session
from server.models.message import Message
from server.models.queries.query import Query
# old
@task()
def process_message1(session: Session, message: Message):
    query = session.create_query.delay(message=message)
    response = session.execute_query.delay(query)
    response_handled = session.parse_response.delay(response)
    response_content = session.decide_next_step.delay(response_handled)
    return response_content



