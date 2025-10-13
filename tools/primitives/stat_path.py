
from pathlib import Path
from ._dispatch_decorator import dispatched_detached



@dispatched_detached
def stat_path(path):
    """
    Gets metadata for a file or directory.

    Args:
        'path': str

    Returns:
        dict: {
            'status': 'success' or 'error',
            'path': str,
            'exists': bool,
            'is_dir': bool,
            'is_file': bool,
            'size': int,
            'mtime': float,
            'ctime': float,
            'message': str (optional, on error)
        }
    """
    try:
        p = Path(path)
        if not p.exists():
            return {
                'status': 'success',
                'path': path,
                'exists': False,
                'is_dir': False,
                'is_file': False,
                'size': 0,
                'mtime': 0.0,
                'ctime': 0.0
            }

        stat = p.stat()
        return {
            'status': 'success',
            'path': path,
            'exists': True,
            'is_dir': p.is_dir(),
            'is_file': p.is_file(),
            'size': stat.st_size if p.is_file() else 0,
            'mtime': stat.st_mtime,
            'ctime': stat.st_ctime
        }
    except Exception as e:
        import traceback
        return {'status': 'error', 'message': f"Error getting stat for {path}: {str(e)} {traceback.format_exc()}"}
