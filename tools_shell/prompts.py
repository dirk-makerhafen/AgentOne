INSTRUCTIONS = """
# Shell Tool

**Purpose:** The `shell` tool allows you to execute arbitrary shell commands or scripts.

**Execution Environment:**
*   The command is executed in a temporary file.
*   You can specify an interpreter: `bash`, `powershell`, or `cmd`.
*   On non-Windows systems, it defaults to `bash`.
*   On Windows, the system attempts to auto-detect between `powershell` and `cmd` based on script content.

**Output:**
*   The tool returns the `stdout`, `stderr`, and `return_code` of the command.
*   A `return_code` of `0` indicates success.
"""

FUNCTIONS = {
    "shell": {
        "name": "shell",
        "description": "Executes a shell command or script. The command is executed in a temporary file. You can use 'bash', 'powershell', or 'cmd' as the interpreter. On non-Windows systems, it defaults to 'bash'. On Windows, it attempts to auto-detect between 'powershell' and 'cmd'.",
        "parameters": {
            "source": {
                "type": "string",
                "description": "The shell command or script to execute.",
                'required': True
            },
            "interpreter": {
                "type": "string",
                "enum": ["auto", "bash", "powershell", "cmd"],
                "description": "The interpreter to use for the script. Defaults to 'auto'.",
                'required': False,
                'default': "auto"
            },
            "subscription_id": {
                "type": "string",
                "description": "A unique identifier for the subscription if mode is 'subscribe'. This will be used to unsubscribe later.",
                'required': False,
            },
            "mode": {
                "type": "string",
                "enum": ["one-shot", "subscribe"],
                "description": "Execution mode: 'one-shot' executes the command once (default), 'subscribe' executes it before every LLM query.",
                'required': False,
                'default': "one-shot"
            }
        }
    }
}
