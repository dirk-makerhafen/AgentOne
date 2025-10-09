from pathlib import Path
from .dispatch_decorator import dispatched_primitive_operation

@dispatched_primitive_operation
def append_file(path, content):
    """
    Appends content to a file. Creates the file and parent directories if they don't exist.

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
        with p.open("a", encoding='utf-8') as f:
            f.write(content)
        return {'status': 'success', 'message': f"Appended to file '{path}' successfully."}
    except Exception as e:
        return {'status': 'error', 'message': f"Error appending to file {path}: {str(e)}"}
