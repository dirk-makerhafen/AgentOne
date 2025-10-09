import json
from tools.calls.models.tool_call import ToolCall
from agents.models.agent_instance import AgentInstance
from ui.router import register_handler

@register_handler('toolcall_direct')
def handle_toolcall_direct(consumer, instance_pk, tool_calls=None):
    if tool_calls is None:
        tool_calls = []
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=instance_pk)
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {instance_pk} not found.'}))
        return

    for tc_data in tool_calls:
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
                tool_call.run()
            else:
                consumer.send(text_data=json.dumps({'object': 'error', 'message': f"Tool '{function_name}' is not available to this agent."}))
