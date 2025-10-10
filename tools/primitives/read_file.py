from pathlib import Path
from ._dispatch_decorator import dispatched_primitive_operation

@dispatched_primitive_operation
def read_file(path):
    """
    Reads the content of a file.

    Args:
        'path': str

    Returns:
        dict: {
            'status': 'success' or 'error',
            'content': str (if successful),
            'message': str (optional, on error)
        }
    """
    try:
        if not path:
            return {'status': 'error', 'message': 'Path not provided'}

        p = Path(path)
        if not p.is_file():
            return {'status': 'error', 'message': f"File not found or not a regular file: {path}"}

        # Attempt to read as UTF-8, fall back to latin-1
        try:
            content = p.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            content = p.read_text(encoding='latin-1')

        return {'status': 'success', 'content': content}
    except Exception as e:
        return {'status': 'error', 'message': f"Error reading file {path}: {str(e)} {traceback.format_exc()}"}
