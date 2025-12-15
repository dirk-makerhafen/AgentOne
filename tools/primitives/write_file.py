from pathlib import Path
import traceback
from ._dispatch_decorator import dispatched_detached

@dispatched_detached
def write_file(path, content):
    """
    Writes (overwrites) content to a file. Creates parent directories if they don't exist.

    Args:
        path: str, 
        content: str

    Returns:
        dict: {
            'status': 'success' or 'error',
            'message': str (optional)
        }
    """
    try:
        if not path:
            return {'status': 'error', 'message': 'Path not provided'}

        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if type(content) == str:
            p.write_text(content, encoding='utf-8')
        else:
            p.write_bytes(content)
        return {'status': 'success', 'message': f"File '{path}' written successfully."}
    except Exception as e:
        return {'status': 'error', 'message': f"Error writing to file {path}: {str(e)} {traceback.format_exc()}"}
