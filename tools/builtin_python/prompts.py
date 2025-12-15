
TOOLS = {
    'python': {
        "name": "python",
        "title": "Execute Python script",
        'description': "Execute a Python script in a controlled sandbox environment. This tool allows the agent to run Python code for computation, data processing, file manipulation, or other programmatic tasks.\n\nExecution environment:\n- The provided Python source code is executed inside an isolated runtime environment.\n- Execution does not allow interactive input; all necessary data must be included in the script.\n- The environment may restrict network access, long-running processes, or specific OS-level operations depending on system configuration.\n- Python code is executed in a fresh context unless the backend explicitly provides persistence.\n\nUsage rules:\n- Use this tool only when Python execution is explicitly required, such as performing calculations, transforming data, generating files, or verifying code behavior.\n- Do not execute code that is destructive, harmful, or not explicitly authorized by the user.\n- Avoid speculative or unnecessary tool calls—use Python only when the result depends on code execution.\n- Scripts should be self-contained; avoid expecting interactive prompts or external input.\n- Ensure that long-running or infinite loops are avoided so execution can complete in a finite time.\n\nOutput behavior:\n- The tool returns stdout, stderr, and any generated files that the environment supports exporting.\n- Python exceptions will appear in stderr.\n\nTypical use cases:\n- Numerical computations or simulations\n- File parsing, transformation, or generation\n- Data analysis and visualization (if supported by the environment)\n- Testing or executing small Python utilities\n\nUse this tool when Python execution is the most reliable or efficient way to accomplish the requested task.",
        "parameters": {
            "type": "object",
            'properties': {
                'source': {
                    'type': 'string',
                    'description': 'The Python source code to run.',
                },
                'subscription_id': {
                    'type': 'string',
                    'description': "A unique identifier for the subscription if mode is 'subscribe'. This will be used to unsubscribe later.",
                },
                'mode': {
                    'type': 'string',
                    'enum': ['one-shot', 'subscribe'],
                    'description': "Execution mode: 'one-shot' executes the code once (default), 'subscribe' executes it before every LLM query.",
                    'default': 'one-shot',
                },
            },
            "required" : ["source"],
        }
    }
}

