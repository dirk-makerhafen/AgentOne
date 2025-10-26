PROMPT_INSTRUCTIONS = '''
# Inter-Agent Tool
This tool allows you to send messages to other agent instances and manage your public description.
It is important to keep your description updated to reflect your current task, so other agents know what you are doing.

## Functions:
'''

PROMPT_AGENTLIST = '''
## Available Agent Instances for Communication

{% for agentInstance in agentInstances %}
### Agent: {{agentInstance.name}} ID: {{agentInstance.id}} 
Description: {{agentInstance.description}}  
{% endfor %}

'''


PROMPTS = [
    {
        "name": "instructions",
        "title": "Agent2Agent tool instructions",
        "description": "Contains general usage instructions for the agent2agent tool",
        "arguments": [],
        'template': PROMPT_INSTRUCTIONS,
    },
    {
        "name": "agentlist",
        "title": "List of available agents",
        "description": "TODO",
        "arguments": [
            {
                "name": "agents",
                "description": "list of agent dicts with name, description and agent_id",
                "required": True,
            }
        ],
        'template': PROMPT_AGENTLIST,
    },
]

TOOLS = {
    "agent_send_message" : {
        "name": "agent_send_message",
        "title": "Send message to agent",
        "description":  "Sends a message to another agent instance.",
        "inputSchema": {
            "type": "object",
            "parameters": {
                'agent_id': {
                    'type': 'int', 
                    'description': 'The agent_id of the agent instance to receive the message.', 
                    'required': True
                },
                'message': {
                    'type': 'string', 
                    'description': 'The message content to send.', 
                    'required': True
                },
            },
            "required" : ["agent_id", "message"],
        }
    },
    "set_agent_description": {   
        "name": "set_agent_description",
        "title": "Set agent description",
        "description": "Sets or updates the public description of the current agent instance. This description is visible to other agents and users. It should be a concise summary of the agent's current task or status.",
        "inputSchema": {
            "type": "object",
            "parameters": {
                "description": {
                    "type": "string", 
                    "description": "A brief summary of the agent's current activity. Max 2-3 sentences, abbreviations/keywords are encouraged.",
                    'required': True
                }
            },
            "required" : ["description"],
        }
    },
}

