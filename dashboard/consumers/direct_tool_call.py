import json
from tools_common.models import ToolCall

def handle_direct_tool_call(consumer, payload):
    tool_calls_data = payload.get('tool_calls', [])
    from agent.models.agent import AgentInstance
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get('instance_pk')} not found.'}))
        return
    for tc_data in tool_calls_data:
        if 'function_name' in tc_data and 'arguments' in tc_data:
            if agent_instance.get_tool_function(tc_data['function_name']):
                tool_call = ToolCall(agent=agent_instance.agent, agentInstance=agent_instance, function_name=tc_data['function_name'], arguments=tc_data['arguments'])
                tool_call.save()
                tool_call.run()
            else:
                consumer.send(text_data=json.dumps({'object': 'error', 'message': f"Tool '{tc_data['function_name']}' is not available to this agent."}))