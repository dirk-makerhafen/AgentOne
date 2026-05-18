import sys
import os

def copy(caller, source, destination, recursive=False):
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
    import sys
    sys.path.insert(0, '/Users/Dirk/AgentOne')

    class MockCaller:
        workingdir = os.getcwd()

    args = sys.argv[1:]
    if len(args) < 2:
        source = '/tmp/test_copy_src.txt'
        destination = '/tmp/test_copy_dst.txt'
        recursive = False
        print(f"Usage: python copytool.py <source> <destination> [recursive=true|false]")
        print(f"Defaulting to: {source} -> {destination}")
    elif len(args) == 2:
        source = args[0]
        destination = args[1]
        recursive = False
    else:
        source = args[0]
        destination = args[1]
        recursive = args[2].lower() == 'true'

    print(f"Copying: {source} -> {destination} (recursive={recursive})")
    success, result = copy.call(MockCaller(), source, destination, recursive)
    print(f"Success: {success}")
    print(f"Result: {result['message']}")
