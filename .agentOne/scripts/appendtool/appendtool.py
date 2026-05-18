from agentone_public import Query, QueryMessage, QueryMessagePart, task, tool, primitives


@tool()
def append(caller, path, content):
    '''
    Appends content to the end of a file.

    - Creates the file and parent directories if they don't exist.
    - Content is appended as-is, without a leading newline.
    - Use this when you want to add to an existing file without overwriting.

    Args:
        path (str): The absolute path to the file to append to.
        content (str): The content to append.

    Returns:
        tuple: (success: bool, result: dict)
            On success, result contains:
                - 'status': 'success'
                - 'message': str
            On error, result contains:
                - 'status': 'error'
                - 'message': str
    '''
    from pathlib import Path
    import traceback

    try:
        if not path:
            return (False, {'status': 'error', 'message': 'Path not provided'})
        if content is None:
            return (False, {'status': 'error', 'message': 'Content not provided'})

        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding='utf-8') as f:
            f.write(str(content))

        return (True, {
            'status': 'success',
            'message': f"Appended to file '{path}' successfully."
        })

    except Exception as e:
        return (False, {
            'status': 'error',
            'message': f"Error appending to file {path}: {str(e)}\n{traceback.format_exc()}"
        })
