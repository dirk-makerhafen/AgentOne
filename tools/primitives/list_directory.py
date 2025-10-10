import os
from pathlib import Path
import traceback
from ._dispatch_decorator import dispatched_primitive_operation


@dispatched_primitive_operation
def list_directory(path, recursive=False, filter={}):
    """
    Lists the content of a directory, returning a structured list of objects.

    Args:
        'path': str,
        'recursive': bool (default: False),
        'filter': dict (optional)

    Returns:
        dict: {
            'status': 'success' or 'error',
            'content': [
                {
                    "path":  str
                    "is_directory": bool,
                    "size": int
                },
            ],
            'message': str (optional, on error)
        }
    """
    try:
        if not path:
            return {'status': 'error', 'message': 'Path not provided'}

        base_path = Path(path)
        if not base_path.is_dir():
            return {'status': 'error', 'message': f"Directory not found: {path}"}

        items = []

        if recursive:
            for root, dirs, files in os.walk(base_path, topdown=True):
                # Sort for consistent output
                dirs.sort()
                files.sort()

                # Exclude common noise directories from traversal
                dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', '.DS_Store']]

                rel_root = Path(root).relative_to(base_path)

                for dir_name in dirs:
                    full_path = Path(root) / dir_name
                    rel_path = rel_root / dir_name if str(rel_root) != '.' else Path(dir_name)
                    try:
                        stat = full_path.stat()
                        items.append({
                            "path": str(rel_path),
                            "is_directory": True,
                            "size": stat.st_size,
                        })
                    except OSError:
                        # Could be a broken symlink, etc.
                        continue

                for file_name in [f for f in files if f not in ['.DS_Store']]:
                    full_path = Path(root) / file_name
                    rel_path = rel_root / file_name if str(rel_root) != '.' else Path(file_name)
                    try:
                        stat = full_path.stat()
                        items.append({
                            "path": str(rel_path),
                            "is_directory": False,
                            "size": stat.st_size,
                        })
                    except OSError:
                        continue
        else: # Non-recursive
            for entry in sorted(os.scandir(base_path), key=lambda e: e.name):
                if entry.name in ['.git', '__pycache__', '.DS_Store']:
                    continue
                try:
                    stat = entry.stat()
                    is_dir = entry.is_dir()
                    items.append({
                        "path": entry.name, # For non-recursive, path is just the name
                        "is_directory": is_dir,
                        "size": stat.st_size,
                    })
                except OSError:
                    continue

        return {'status': 'success', 'content': items}

    except Exception as e:
        return {'status': 'error', 'message': "Error listing directory {}: {}\n{}".format(path, str(e), traceback.format_exc())}

