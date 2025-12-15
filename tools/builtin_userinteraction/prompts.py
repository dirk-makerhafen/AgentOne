TOOLS = {
    'await_input': {
        "name": "await_input",
        "title": "Wait for user/agent Input",
        'description': "Pauses the agents autonomous operation and waits for user or agent input. When this function is called, the agent stops executing all further steps and enters a waiting state until the next message or instruction is received. Use this tool whenever clarification, confirmation, additional information, or a decision is required before continuing.\n\nRules for using await_input:\n- Call this function whenever you need the user (or another agent) to provide input, make a choice, supply missing information, or approve an action.\n- If you expect user input and DO NOT call this function, the user will not be notified and the workflow will stall.\n- Use await_input for any step where you cannot proceed autonomously.\n\nExamples of proper use:\n- \"I found the file 'test.txt'. Should I delete it?\" → await_input.\n- \"Please choose between Option A and Option B.\" → await_input.\n- \"I need clarification before proceeding.\" → await_input.\n\nThe optional 'reason' parameter may be given to explain why input is needed. Never continue execution after calling this tool; the agent must wait for the next incoming message.", 
        "parameters": {
            "type": "object",
            'properties': {
                "reason": { 
                    "type": "string", 
                    "description": "Optionally provide a reason why input is expected", 
                },
            },
            "required" : []
        }
    },
}
