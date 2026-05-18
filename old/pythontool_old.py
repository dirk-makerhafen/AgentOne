from agentone_public import Query, QueryMessage, QueryMessagePart, task, tool, primitives


@tool()
def python(caller, source):
    '''
    Execute a Python script in a controlled sandbox environment. 
    This tool allows the agent to run Python code for computation, data processing, file manipulation, or other programmatic tasks.
    
    Execution environment:
    - The provided Python source code is executed inside an isolated runtime environment.
    - Execution does not allow interactive input; all necessary data must be included in the script.
    - The environment may restrict network access, long-running processes, or specific OS-level operations depending on system configuration.
    - Python code is executed in a fresh context unless the backend explicitly provides persistence.
    
    Usage rules:
- Use this tool only when Python execution is explicitly required, such as performing calculations, transforming data, generating files, or verifying code behavior.
- Do not execute code that is destructive, harmful, or not explicitly authorized by the user.
- Avoid speculative or unnecessary tool calls—use Python only when the result depends on code execution.
- Scripts should be self-contained; avoid expecting interactive prompts or external input.
- Ensure that long-running or infinite loops are avoided so execution can complete in a finite time.

Output behavior:
- The tool returns stdout, stderr, and any generated files that the environment supports exporting.
- Python exceptions will appear in stderr.

Typical use cases:
- Numerical computations or simulations
- File parsing, transformation, or generation
- Data analysis and visualization (if supported by the environment)
- Testing or executing small Python utilities

Use this tool when Python execution is the most reliable or efficient way to accomplish the requested task."
    '''
    result = primitives.run_python_code(agent_instance=caller, python_code_string=source, workingdir=caller.workingdir)
    return ( result.get("status")=="success", result)



