from agentone_public import Query, QueryMessage, QueryMessagePart, task, tool, primitives


@tool()
def edit(caller, path, old_string, new_string, replace_all=False):
    '''
    Performs exact string replacements in files.

    Usage:
    - You must use the Read tool at least once in the conversation before editing.
    - When editing text, ensure you preserve the exact indentation (tabs/spaces).
    - The edit will FAIL if old_string is not found in the file.
    - The edit will FAIL if old_string is found multiple times and replace_all is False.
    - Use replace_all for replacing strings across the file. This parameter is useful if you want to rename a variable.

    Args:
        path (str): The absolute path to the file to modify.
        old_string (str): The text to replace.
        new_string (str): The text to replace it with (must be different from old_string).
        replace_all (bool): Replace all occurrences of old_string. Default: false.

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
        if not old_string:
            return (False, {'status': 'error', 'message': 'old_string not provided'})
        if old_string == new_string:
            return (False, {'status': 'error', 'message': 'old_string and new_string are identical'})

        p = Path(path)
        if not p.exists():
            return (False, {'status': 'error', 'message': f'File not found: {path}'})

        content = p.read_text(encoding='utf-8')
        occurrences = content.count(old_string)

        if occurrences == 0:
            return (False, {'status': 'error', 'message': f'old_string not found in {path}'})

        if occurrences > 1 and not replace_all:
            return (False, {
                'status': 'error',
                'message': f'Found {occurrences} occurrences of old_string. Provide more surrounding lines to make it unique, or use replace_all=True.'
            })

        new_content = content.replace(old_string, new_string, -1 if replace_all else 1)
        p.write_text(new_content, encoding='utf-8')

        return (True, {
            'status': 'success',
            'message': f"Replaced {occurrences if replace_all else 1} occurrence(s) in '{path}'."
        })

    except Exception as e:
        return (False, {
            'status': 'error',
            'message': f"Error editing file {path}: {str(e)}\n{traceback.format_exc()}"
        })
