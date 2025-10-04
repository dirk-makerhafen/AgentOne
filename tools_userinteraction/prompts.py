
INSTRUCTIONS = '''
# User Interaction Tool
This tool allows you to pause your autonomous operation and wait for input from the user.

**Function:**
`await_user_input()`

**Description:**
When you call this function, you will stop executing and enter a waiting state. The user will be notified that you are waiting for them. You should use this tool whenever you need clarification, a decision, or further instructions from the user to proceed with your task.
You must call this function whenever you need or expect user input, otherwise the user will not be notified! 

**Example:**
If you need the user to confirm a file deletion:

I have located the file 'test.txt'. Should I proceed with deleting it?
@@@await_user_input()@@@

'''


FUNCTIONS = {
    'await_user_input': {
        'description': 'Pauses the agents autonomous operation. The agent will stop executing further steps and wait for the user to provide the next message or instruction. This is useful when you need feedback, a decision, or more information from the user before proceeding.', 
        'parameters': {
            "reason": { "type": "string", "description": "Optionally provide a reason why user input is expected", "required": False},
        }
    },
}
