from agentone_public import  Query, QueryMessage, QueryMessagePart, task, tool, primitives



@tool()
def shell(caller, source, interpreter="auto"):
    '''
        Execute a shell command or script in a temporary file. This tool allows the agent to run system-level commands using an interpreter such as bash, powershell, or cmd.

        Execution environment:
        - The provided source code is written to a temporary file and executed.
        - The interpreter may be explicitly chosen or left as 'auto'. On non-Windows systems, 'auto' defaults to bash. On Windows, 'auto' attempts to detect whether powershell or cmd is appropriate based on script content.

        Usage rules:
        - Use this tool only when shell execution is explicitly needed, such as running scripts, invoking command-line tools, inspecting the file system, or automating OS-level tasks.
        - Never use this tool for speculative actions—only run commands that the user has directly requested or clearly permitted.
        - Ensure commands are safe, non-destructive unless the user explicitly approves them.
        - Avoid long-running or interactive commands; the tool must complete execution without waiting for input.

        Output behavior:
        - The tool returns stdout, stderr, and return_code.
        - A return_code of 0 indicates successful execution; non-zero codes indicate errors.

        Mode options:
        - one-shot: Run the command once and return its output (default).
        - subscribe: The command will run automatically before every subsequent LLM query until unsubscribed using the subscription_id.

        Use the 'interpreter' parameter to choose the execution environment, and 'subscription_id' if using subscription mode.
    '''
    result = primitives.run_shell_script(agent_instance=caller, script=source, interpreter=interpreter, cwd=caller.workingdir)
    success = result.get("return_code") == 0 and result.get("status") == "success"
    return (success, result)
