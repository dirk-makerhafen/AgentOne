
def write(caller, path, content):
    '''
    Write a file to the local filesystem.

    - This tool will overwrite the existing file if there is one at the provided path.
    - If this is an existing file, you MUST use the Read tool first to read the file's contents.
    - ALWAYS prefer editing existing files in the codebase. NEVER write new files unless explicitly required.
    - NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
    - Only use emojis if the user explicitly requests it. Avoid writing emojis to files unless asked.

    Args:
        path (str): The absolute path to the file to write (must be absolute, not relative).
        content (str): The content to write to the file.

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

        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            p.write_text(content, encoding='utf-8')
        else:
            p.write_bytes(content)

        return (True, {
            'status': 'success',
            'message': f"File '{path}' written successfully."
        })

    except Exception as e:
        return (False, {
            'status': 'error',
            'message': f"Error writing to file {path}: {str(e)}\n{traceback.format_exc()}"
        })
