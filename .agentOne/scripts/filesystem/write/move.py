
def move(source, destination):
    '''
    Moves a file or directory from source to destination.

    - If the destination exists, it will be overwritten for files.
    - Parent directories of the destination are created if they don't exist.
    - Works across filesystem boundaries (unlike os.rename).

    Args:
        source (str): The absolute path to the file or directory to move.
        destination (str): The absolute path to move to.

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

        shutil.move(str(src), str(dst))

        return (True, {
            'status': 'success',
            'message': f"Moved '{source}' to '{destination}'."
        })

    except Exception as e:
        return (False, {
            'status': 'error',
            'message': f"Error moving '{source}' to '{destination}': {str(e)}\n{traceback.format_exc()}"
        })

if __name__ == '__main__':
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Move a file or directory.')
    parser.add_argument('source', type=str, help='Source path')
    parser.add_argument('destination', type=str, help='Destination path')
    args = parser.parse_args()

    success, result = move(source=args.source, destination=args.destination)
    print(json.dumps(result, indent=2))
    exit(0 if success else 1)
