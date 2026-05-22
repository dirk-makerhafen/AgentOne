import os
import traceback
from ._dispatch_decorator import dispatched_detached

@dispatched_detached
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
        else:
            if os.path.isfile(path):
                return {'status': 'error', 'message': f"A file already exists with the same name"}
            elif os.path.isdir(path):
                if exist_ok is False:
                    return {'status': 'error', 'message': f"Directory already exists"}

            else:
                os.mkdir(path)
        return {'status': 'success', 'message': f"Directory '{path}' created successfully."}
    except Exception as e:
        return {'status': 'error', 'message': f"Error creating directory {path}: {str(e)} {traceback.format_exc()}"}
    