import json
from tools.calls.models.tool_call import ToolCall
from agents.models.agent_instance import AgentInstance
from ui.router import register_handler

@register_handler('toolcall_direct')
def handle_toolcall_direct(consumer, user_pk, payload):
    tool_calls_data = payload.get('tool_calls', [])
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get("instance_pk")} not found.'}))
        return

    for tc_data in tool_calls_data:
        function_name = tc_data.get('function_name')
        arguments = tc_data.get('arguments')
        if function_name and arguments is not None:
            if agent_instance.get_tool_function(function_name):
                tool_call = ToolCall(
                    agent=agent_instance.agent, 
                    agentInstance=agent_instance, 
                    function_name=function_name, 
                    arguments=arguments
                )
                tool_call.save()
                tool_call.run(user_pk=user_pk)
            else:
                consumer.send(text_data=json.dumps({'object': 'error', 'message': f"Tool '{function_name}' is not available to this agent."}))
