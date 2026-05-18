
   


from runtime.agents.session import Session
from server.models.message import Message


def process_message(session: Session, message: Message) -> Message:

    query = session.create_query.delay(message=message)

    response = session.execute_query.delay(query)
    
    parts = session.parse_api_response.delay(response)
    
    response_content = session.process_assistant_message.delay(response=response, parsed_response_data=parts)
    
    return response_content