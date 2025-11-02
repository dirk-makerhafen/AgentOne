PROMPT_INSTRUCTIONS = """
You are equipped with the **Sub-agent Tool** to create and manage subordinate agents. This allows you to delegate tasks to specialized agents, expanding your capabilities and parallelizing work.

When creating a sub-agent, you can base it on an existing Agent definition (a template) or let it use a default template. New sub-agents will appear below in your list of Available Agents and can be communicated with using the `a2a` tool.
"""

REGISTRATION_INSTRUCTION_TEMPLATE = """I am your supervisor, Agent {supervisor_id}.

Your first task is to register yourself in the shared key-value store using the `kv_storage.set` tool. This will make you discoverable by other agents.

Please execute the following tool call:
@@@kv_storage.set(key="{key}", value='{value}')@@@
After registering, you can discover other agents by calling `kv_storage.list(prefix="team:agents:")`.
"""

PROMPTS = [
    {
        "name": "instructions",
        "title": "Sub-agent tool instructions",
        "description": "Contains general usage instructions for the sub-agent tool",
        "arguments": [],
        'template': PROMPT_INSTRUCTIONS,
    },
    {
        "name": "available_agents_content",
        "title": "Available Agent Templates",
        "description": "Lists existing agent definitions that can be used as templates for creating new sub-agents.",
        "arguments": [],
        "template": """# Available Agent Templates
The following Agent definitions are available as templates for creating new sub-agents. You can specify `based_on_agent_pk` in the `create` function with the `pk` of one of these agents.

Available Agents:
{% for available_agent in available_agents %}
- Name: {{available_agent.name}} (PK: {{available_agent.pk}})
  Description: {{available_agent.description}}
{% endfor %}
"""
    },
    {
        "name": "current_subagents_content",
        "title": "Current Subordinate Agents",
        "description": "Lists sub-agents currently reporting to this agent instance.",
        "arguments": [],
        "template": """# Your Subordinate Agents
You currently have the following sub-agent instances under your supervision:

{% for subagent in subagents %}
- Name: '{{subagent.name}}' (agent_id: {{subagent.pk}})
  Status: {{subagent.status}}
  Description: {{subagent.description}}
{% endfor %}
"""
    },
    {
    "name": "registration_instruction",
    "title": "Sub-agent KV Store Registration Instruction",
    "description": "The initial instruction message sent to a new sub-agent, prompting it to register itself.",
    "arguments": ["supervisor_id", "key", "value"],
    "template": REGISTRATION_INSTRUCTION_TEMPLATE,
    },
    {
    "name": "supervisor_info_content",
    "title": "Supervisor Agent Information",
    "description": "Provides information about the parent (supervisor) agent instance if this agent is a sub-agent.",
    "arguments": [],
    "template": """
# Your Supervisor Agent

You are currently operating as a sub-agent under the supervision of another agent.
Your supervisor's details are as follows:

- Name: {{supervisor.name}} (ID: {{supervisor.pk}})
- Agent Type: {{supervisor.agent_name}}
- Description: {{supervisor.description_text}}
- Status: {{supervisor.status_display}}
- Working Directory: {{supervisor.workingdir}}
- Created At: {{supervisor.created_at}}
"""
}
]

TOOLS = {
    "update_working_dir": {
        "name": "update_working_dir",
        "title": "Update workingdir of a sub agent",
        "description": "Update the workingdir of a subagent",
        "inputSchema": {
            "type": "object",
            "parameters": {
                'agent_id': {
                    'type': 'int', 
                    'description': 'The agent_id of the agent instance to change.', 
                    'required': True
                },
                "workingdir": {
                    "type": "string",
                    "description": "The new working dir",
                    "required": True
                },
            },
            "required": ["agent_id", "workingdir"]
        }
    },
    "create": {
        "name": "create",
        "title": "Create sub-agent",
        "description": "Creates a new sub-agent instance, linked to the current agent instance as a subordinate. The sub-agent will run independently.",
        "inputSchema": {
            "type": "object",
            "parameters": {
                "agent_name": {
                    "type": "string",
                    "description": "The name of the new sub-agent instance.",
                    "required": True
                },
                "agent_description": {
                    "type": "string",
                    "description": "A brief description of the sub-agent's purpose.",
                    "required": True
                },
                "based_on_agent_pk": {
                    "type": "integer",
                    "description": "The primary key of an existing Agent definition to base this sub-agent on. If not provided, a default Agent definition will be used.",
                    "nullable": True,
                    "required": False
                },
                "workingdir": {
                    "type": "string",
                    "description": "A specific working directory for the sub-agent. If not provided, it will inherit the supervisor's working directory.",
                    "nullable": True,
                    "required": False
                }
            },
            "required": ["agent_name", "agent_description"]
        }
    }
}
