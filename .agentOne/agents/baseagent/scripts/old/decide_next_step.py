
from runtime.agents.agent import Agent
from runtime.agents.session import Session
from server.models.message import Message
from registry.task_decorators import task
from server.models.queries.response import Response

@task()
def decide_next_step(session: Session, response: Response, tool_runs: list):
    print("here")
    message = Message.objects.create(
        session_version = session.get_version_model(),
        response=response,
        role='assistant',
    )
    if response.tool_calls.exists():
        message.tool_calls.set(response.tool_calls.all())
    if response.message_content:
        message.add_part(response.message_content.get())

    return message
    
    agent_instance = message.agent_instance
    agent_instance.refresh_from_db()
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
