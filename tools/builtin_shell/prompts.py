TOOLS = {
    "shell": {
        "name": "shell",
        "title": "Run shell/cmd script",
        "description": "Execute a shell command or script in a temporary file. This tool allows the agent to run system-level commands using an interpreter such as bash, powershell, or cmd.\n\nExecution environment:\n- The provided source code is written to a temporary file and executed.\n- The interpreter may be explicitly chosen or left as 'auto'. On non-Windows systems, 'auto' defaults to bash. On Windows, 'auto' attempts to detect whether powershell or cmd is appropriate based on script content.\n\nUsage rules:\n- Use this tool only when shell execution is explicitly needed, such as running scripts, invoking command-line tools, inspecting the file system, or automating OS-level tasks.\n- Never use this tool for speculative actions—only run commands that the user has directly requested or clearly permitted.\n- Ensure commands are safe, non-destructive unless the user explicitly approves them.\n- Avoid long-running or interactive commands; the tool must complete execution without waiting for input.\n\nOutput behavior:\n- The tool returns stdout, stderr, and return_code.\n- A return_code of 0 indicates successful execution; non-zero codes indicate errors.\n\nMode options:\n- one-shot: Run the command once and return its output (default).\n- subscribe: The command will run automatically before every subsequent LLM query until unsubscribed using the subscription_id.\n\nUse the 'interpreter' parameter to choose the execution environment, and 'subscription_id' if using subscription mode.",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "The shell command or script to execute.",
                },
                "interpreter": {
                    "type": "string",
                    "enum": ["auto", "bash", "powershell", "cmd"],
                    "description": "The interpreter to use for the script. Defaults to 'auto'.",
                    'default': "auto",
                },
                "subscription_id": {
                    "type": "string",
                    "description": "A unique identifier for the subscription if mode is 'subscribe'. This will be used to unsubscribe later.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["one-shot", "subscribe"],
                    "description": "Execution mode: 'one-shot' executes the command once (default), 'subscribe' executes it before every LLM query.",
                    'default': "one-shot",
                }
            },
            "required" : ["source"],
        }
    }
}
