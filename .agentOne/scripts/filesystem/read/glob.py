import glob as glob_module
import os
import traceback

def glob(caller, pattern, path=None):
    '''
    Fast file pattern matching tool that works with any codebase size.

    - Supports glob patterns like "**/*.js" or "src/**/*.tsx".
    - Returns matching file paths sorted by modification time.
    - Use this tool when you need to find files by name patterns.
    - If the directory is not specified, the current working directory is used.

    Args:
        pattern (str): The glob pattern to match files against (e.g., "**/*.py", "src/**/*.ts").
        path (str, optional): The directory to search in. If not specified, the current working directory is used.

    Returns:
        tuple: (success: bool, result: dict)
            On success, result contains:
                - 'status': 'success'
                - 'matches': list[str] (sorted list of matching file paths)
                - 'count': int
            On error, result contains:
                - 'status': 'error'
                - 'message': str
    '''

    try:
        if not pattern:
            return (False, {'status': 'error', 'message': 'Pattern not provided'})

        search_dir = path if path else os.getcwd()

        search_pattern = os.path.join(search_dir, pattern)
        matches = sorted(glob_module.glob(search_pattern, recursive=True), key=os.path.getmtime)

        return (True, {
            'status': 'success',
            'matches': matches,
            'count': len(matches)
        })

    except Exception as e:
        return (False, {
            'status': 'error',
            'message': f"Error searching for pattern '{pattern}': {str(e)}\n{traceback.format_exc()}"
        })

if __name__ == '__main__':
    import argparse
    import json

    class MockCaller:
        def __init__(self):
            self.workingdir = os.getcwd()

    parser = argparse.ArgumentParser(description='Fast file pattern matching.')
    parser.add_argument('pattern', type=str, help='Glob pattern (e.g., "**/*.py")')
    parser.add_argument('--path', type=str, default=None, help='Directory to search in')
    args = parser.parse_args()

    success, result = glob(MockCaller(), pattern=args.pattern, path=args.path)
    print(json.dumps(result, indent=2))
    exit(0 if success else 1)
