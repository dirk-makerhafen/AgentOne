
def multiedit(caller, path, edits):
    '''
    Performs multiple exact string replacements in a single file.

    Use this when you need to make several edits to the same file in one call.
    Edits are applied in order. If any edit fails, the entire operation fails
    and the file is left unchanged.

    Args:
        path (str): The absolute path to the file to modify.
        edits (list[dict]): A list of edit operations, each containing:
            - old_string (str): The text to replace (required).
            - new_string (str): The text to replace it with (required).
            - replace_all (bool): Replace all occurrences. Default: false (optional).

    Returns:
        tuple: (success: bool, result: dict)
            On success, result contains:
                - 'status': 'success'
                - 'message': str
            On error, result contains:
                - 'status': 'error'
                - 'message': str
                - 'edits_applied': int (number of edits successfully applied before failure)
    '''
    from pathlib import Path
    import traceback

    try:
        if not path:
            return (False, {'status': 'error', 'message': 'Path not provided'})
        if not edits:
            return (False, {'status': 'error', 'message': 'No edits provided'})

        p = Path(path)
        if not p.exists():
            return (False, {'status': 'error', 'message': f'File not found: {path}'})

        content = p.read_text(encoding='utf-8')
        edits_applied = 0

        for i, edit in enumerate(edits):
            old_string = edit.get('old_string', '')
            new_string = edit.get('new_string', '')
            replace_all = edit.get('replace_all', False)

            if not old_string:
                return (False, {
                    'status': 'error',
                    'message': f'Edit {i}: old_string not provided',
                    'edits_applied': edits_applied
                })
            if old_string == new_string:
                return (False, {
                    'status': 'error',
                    'message': f'Edit {i}: old_string and new_string are identical',
                    'edits_applied': edits_applied
                })

            occurrences = content.count(old_string)
            if occurrences == 0:
                return (False, {
                    'status': 'error',
                    'message': f'Edit {i}: old_string not found in {path}',
                    'edits_applied': edits_applied
                })

            content = content.replace(old_string, new_string, -1 if replace_all else 1)
            edits_applied += 1

        p.write_text(content, encoding='utf-8')

        return (True, {
            'status': 'success',
            'message': f"Applied {edits_applied} edit(s) to '{path}'."
        })

    except Exception as e:
        return (False, {
            'status': 'error',
            'message': f"Error editing file {path}: {str(e)}\n{traceback.format_exc()}"
        })
