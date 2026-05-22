from __future__ import annotations


def rm(path: str, recursive: bool = False) -> tuple[bool, dict]:
    '''
    Deletes a file or directory.

    Args:
        path: The absolute path to the file or directory to delete.
        recursive: If true, deletes directories and their contents.
            Default: false.

    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - message: str
        On error, result contains:
            - status: "error"
            - message: str
    '''
    import os
    from pathlib import Path
    import shutil
    import traceback

    try:
        if not path:
            return (False, {'status': 'error', 'message': 'Path not provided'})

        p = Path(path)

        if not p.exists():
            return (True, {'status': 'success', 'message': f"Path '{path}' does not exist, no action needed."})

        if p.is_file():
            os.remove(p)
            return (True, {'status': 'success', 'message': f"File '{path}' deleted successfully."})
        elif p.is_dir():
            if recursive:
                shutil.rmtree(p)
                return (True, {'status': 'success', 'message': f"Directory '{path}' and its contents deleted recursively."})
            else:
                try:
                    os.rmdir(p)
                    return (True, {'status': 'success', 'message': f"Empty directory '{path}' deleted successfully."})
                except OSError as e:
                    err_str = str(e)
                    if "Directory not empty" in err_str or "The directory is not empty" in err_str:
                        return (False, {'status': 'error', 'message': f"Directory '{path}' is not empty. Use recursive=True to delete its contents."})
                    else:
                        return (False, {'status': 'error', 'message': f"Error deleting directory {path}: {err_str}"})
        else:
            return (False, {'status': 'error', 'message': f"Path '{path}' is neither a file nor a directory. Cannot delete."})

    except Exception as e:
        return (False, {
            'status': 'error',
            'message': f"Error deleting path {path}: {str(e)}\n{traceback.format_exc()}",
        })

if __name__ == '__main__':
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Delete a file or directory.')
    parser.add_argument('path', type=str, help='Path to delete')
    parser.add_argument('--recursive', '-r', action='store_true', default=False, help='Delete directories recursively')
    args = parser.parse_args()

    success, result = rm(path=args.path, recursive=args.recursive)
    print(json.dumps(result, indent=2))
    exit(0 if success else 1)
