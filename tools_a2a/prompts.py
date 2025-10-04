INSTRUCTIONS = '''
# Inter-Agent Tool
This tool allows you to send messages to other agent instances and manage your public description.
It is important to keep your description updated to reflect your current task, so other agents know what you are doing.

## Functions:

'''

FUNCTIONS = {
    "agent_send_message": {
        "description":  "Sends a message to another agent instance.",
        "parameters": {
            'id': {'type': 'int', 'description': 'The id of the agent instance to receive the message.', 'required': True},
            'message': {'type': 'string', 'description': 'The message content to send.', 'required': True}
        }
    },
    "set_agent_description": {
        "description": "Sets or updates the public description of the current agent instance. This description is visible to other agents and users. It should be a concise summary of the agent's current task or status.",
        "parameters": {
            "description": {"type": "string", "description": "A brief summary of the agent's current activity. Max 2-3 sentences, abbreviations/keywords are encouraged.", "required": True}
        }
    }
}

AGENTLIST = '''
## Available Agent Instances for Communication

{% for agent in agents %}
### Agent: {{agent.name}} ID: {{agent.id}} 
Description: {{agent.description}}  

{% endfor %}

'''