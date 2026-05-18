from registry.task_decorators import task
from runtime.agents.session import Session
from server.models.message import Message
from server.models.queries.response import Response

def process_assistant_message(session:Session, response: Response, parsed_response_data):
    print(parsed_response_data)

    session_version = session.get_version_model()
    prev_message = session_version.related_messages.filter(next_messages=None).last()

    message = Message.objects.create(
        session_version = session_version,
        response=response,
        role='assistant',
        prev_message = prev_message,
    )

    tool_calls = parsed_response_data.get("tool_calls", [])
    if tool_calls:
        message.tool_calls.set(tool_calls)

    content = parsed_response_data.get("content", "")
    if content:
        message.add_part(content)

    if session.max_turns >= session.current_turn_count:
        print("MAX TURNS REACHED")
        return message
    if session.max_unattended_turns >= session.current_unattended_turn_count:
        print("MAX UNATTENDD TURNS REACHED")
        return message
    if not tool_calls:
        print("NO TOOLCALLS; FINISHED")
        return message
    

    '''
    if agent_instance.require_user_interaction:
        agent_instance.set_status(AgentInstanceStatusChoices.AWAITING_USER_INPUT)
    elif agent_instance.effective_limit_max_automated_steps == 0: # automatic steps are  disabls, we need user input next
        agent_instance.set_status(AgentInstanceStatusChoices.AWAITING_USER_INPUT)
    elif agent_instance.automated_step_count >= agent_instance.effective_limit_max_automated_steps:  # automated step LIMIT REACHED, require user confirmation
        agent_instance.set_status(AgentInstance.AgentInstanceStatusChoices.AWAITING_USER_INPUT)
    else: # limit not reached, automation enabled
        agent_instance.set_status(AgentInstance.AgentInstanceStatusChoices.IDLE)
        if agent_instance.tasks.first(): # is task agent
            if not agent_instance.get_active_task(): # no active task
                agent_instance.process_next_task()
        else: # chat agent, no tasks
            print("# chat agent, no tasks")
            #runtime._create_query()
            #celery_create_query.delay(agent_instance.instance_pk)
    '''

    return process_message(message=message)
