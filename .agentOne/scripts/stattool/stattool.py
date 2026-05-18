from agentone_public import Query, QueryMessage, QueryMessagePart, task, tool, primitives


@tool()
def stat(caller, path):
    '''
    Gets metadata for a file or directory.

    Args:
        path (str): The absolute path to get metadata for.

    Returns:
        tuple: (success: bool, result: dict)
            On success, result contains:
                - 'status': 'success'
                - 'path': str
                - 'exists': bool
                - 'is_dir': bool
                - 'is_file': bool
                - 'size': int (file size in bytes, 0 for directories)
                - 'mtime': float (modification time as unix timestamp)
                - 'ctime': float (creation/change time as unix timestamp)
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
        if not p.exists():
            return (True, {
                'status': 'success',
                'path': path,
                'exists': False,
                'is_dir': False,
                'is_file': False,
                'size': 0,
                'mtime': 0.0,
                'ctime': 0.0
            })

        stat = p.stat()
        return (True, {
            'status': 'success',
            'path': path,
            'exists': True,
            'is_dir': p.is_dir(),
            'is_file': p.is_file(),
            'size': stat.st_size if p.is_file() else 0,
            'mtime': stat.st_mtime,
            'ctime': stat.st_ctime
        })

    except Exception as e:
        return (False, {
            'status': 'error',
            'message': f"Error getting stat for {path}: {str(e)}\n{traceback.format_exc()}"
        })
