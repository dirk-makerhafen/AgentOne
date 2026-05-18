from agentone_public import Query, QueryMessage, QueryMessagePart, task, tool, primitives


@tool()
def glob(caller, pattern, path=None):
    '''
    Fast file pattern matching tool that works with any codebase size.

    - Supports glob patterns like "**/*.js" or "src/**/*.tsx".
    - Returns matching file paths sorted by modification time.
    - Use this tool when you need to find files by name patterns.
    - If the directory is not specified, the current working directory is used.

    Args:
        pattern (str): The glob pattern to match files against (e.g., "**/*.py", "src/**/*.ts").
        path (str, optional): The directory to search in. If not specified, the current working directory is used.

    Returns:
        tuple: (success: bool, result: dict)
            On success, result contains:
                - 'status': 'success'
                - 'matches': list[str] (sorted list of matching file paths)
                - 'count': int
            On error, result contains:
                - 'status': 'error'
                - 'message': str
    '''
    import glob as glob_module
    import os
    import traceback

    try:
        if not pattern:
            return (False, {'status': 'error', 'message': 'Pattern not provided'})

        search_dir = path if path else (caller.workingdir if hasattr(caller, 'workingdir') and caller.workingdir else os.getcwd())

        search_pattern = os.path.join(search_dir, pattern)
        matches = sorted(glob_module.glob(search_pattern, recursive=True), key=os.path.getmtime)

        return (True, {
            'status': 'success',
            'matches': matches,
            'count': len(matches)
        })

    except Exception as e:
        return (False, {
            'status': 'error',
            'message': f"Error searching for pattern '{pattern}': {str(e)}\n{traceback.format_exc()}"
        })
