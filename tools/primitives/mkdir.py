import os
import traceback
from ._dispatch_decorator import dispatched_primitive_operation

@dispatched_primitive_operation
def mkdir(path, parents=False, exist_ok=True):
    """
    Creates a directory, including any necessary parent directories.
    Behaves like `mkdir -p`.

    Args:
        path: str
        parents: bool 

    Returns:
        dict: {
            'status': 'success' or 'error',
            'message': str (optional)
        }
    """
    try:
        if not path:
            return {'status': 'error', 'message': 'Path not provided'}
        if parents:
            os.makedirs(path, exist_ok=exist_ok)
        elif not (os.path.exists(path) and exist_ok == True):
            os.mkdir(path)
        return {'status': 'success', 'message': f"Directory '{path}' created successfully."}
    except Exception as e:
        return {'status': 'error', 'message': f"Error creating directory {path}: {str(e)} {traceback.format_exc()}"}
    