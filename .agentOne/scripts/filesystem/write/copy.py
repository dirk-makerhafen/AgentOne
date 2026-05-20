def copy(source, destination, recursive=False):
    '''
    Copies a file or directory from source to destination.

    - For files, copies the file to the destination. If destination is a directory, copies into it.
    - For directories, use recursive=true to copy the entire directory tree.
    - Parent directories of the destination are created if they don't exist.

    Args:
        source (str): The absolute path to the file or directory to copy.
        destination (str): The absolute path to copy to.
        recursive (bool): If true, copies directories recursively. Default: false.

    Returns:
        tuple: (success: bool, result: dict)
            On success, result contains:
                - 'status': 'success'
                - 'message': str
            On error, result contains:
                - 'status': 'error'
                - 'message': str
    '''
    import shutil
    from pathlib import Path
    import traceback

    try:
        if not source or not destination:
            return (False, {'status': 'error', 'message': 'Source and destination paths are required'})

        src = Path(source)
        if not src.exists():
            return (False, {'status': 'error', 'message': f'Source not found: {source}'})

        dst = Path(destination)
        dst.parent.mkdir(parents=True, exist_ok=True)

        if src.is_dir():
            if recursive:
                if dst.exists():
                    dst = dst / src.name
                shutil.copytree(str(src), str(dst))
            else:
                return (False, {'status': 'error', 'message': f"Source is a directory. Use recursive=true to copy it."})
        else:
            shutil.copy2(str(src), str(dst))

        return (True, {
            'status': 'success',
            'message': f"Copied '{source}' to '{destination}'."
        })

    except Exception as e:
        return (False, {
            'status': 'error',
            'message': f"Error copying '{source}' to '{destination}': {str(e)}\n{traceback.format_exc()}"
        })

if __name__ == '__main__':
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Copy a file or directory.')
    parser.add_argument('source', type=str, help='Source path')
    parser.add_argument('destination', type=str, help='Destination path')
    parser.add_argument('--recursive', '-r', action='store_true', default=False, help='Copy directories recursively')
    args = parser.parse_args()

    success, result = copy(source=args.source, destination=args.destination, recursive=args.recursive)
    print(json.dumps(result, indent=2))
    exit(0 if success else 1)
