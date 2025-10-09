import os
from pathlib import Path
import shutil
import traceback
from .dispatch_decorator import dispatched_primitive_operation

@dispatched_primitive_operation
def rm(path, recursive=False):
    """
    Deletes a file or directory.

    Args:
        path: str
        recursive: bool (default: False) - If True, deletes directories and their contents.

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

        if not p.exists():
            return {'status': 'success', 'message': f"Path '{path}' does not exist, no action needed."}

        if p.is_file():
            os.remove(p)
            return {'status': 'success', 'message': f"File '{path}' deleted successfully."}
        elif p.is_dir():
            if recursive:
                shutil.rmtree(p)
                return {'status': 'success', 'message': f"Directory '{path}' and its contents deleted recursively."}
            else:
                # Try to remove empty directory
                try:
                    os.rmdir(p)
                    return {'status': 'success', 'message': f"Empty directory '{path}' deleted successfully."}
                except OSError as e:
                    if "Directory not empty" in str(e) or "The directory is not empty" in str(e):
                        return {'status': 'error', 'message': f"Directory '{path}' is not empty. Use recursive=True to delete its contents."}
                    else:
                        return {'status': 'error', 'message': f"Error deleting empty directory {path}: {str(e)} {traceback.format_exc()}"}
        else:
            return {'status': 'error', 'message': f"Path '{path}' is neither a file nor a directory (e.g., symlink to non-existent target). Cannot delete."}

    except Exception as e:
        return {'status': 'error', 'message': f"Error deleting path {path}: {str(e)} {traceback.format_exc()}"}
