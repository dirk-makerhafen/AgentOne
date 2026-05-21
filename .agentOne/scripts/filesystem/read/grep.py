import re
import os
from pathlib import Path
import traceback
import fnmatch

def grep(pattern, path=None, include=None):
    '''
    Fast content search tool that works with any codebase size.

    - Searches file contents using regular expressions.
    - Supports full regex syntax (e.g., "log.*Error", "function\\s+\\w+").
    - Filter files by pattern with the include parameter (e.g., "*.js", "*.{ts,tsx}").
    - Returns file paths and line numbers with at least one match.
    - If the directory is not specified, the current working directory is used.

    Args:
        pattern (str): The regex pattern to search for in file contents.
        path (str, optional): The directory to search in. Defaults to the current working directory.
        include (str, optional): File pattern to include in the search (e.g., "*.js", "*.{ts,tsx}").

    Returns:
        tuple: (success: bool, result: dict)
            On success, result contains:
                - 'status': 'success'
                - 'matches': list[dict] (each dict has 'file', 'line_number', 'line')
                - 'file_count': int (number of files with at least one match)
                - 'match_count': int (total number of matching lines)
            On error, result contains:
                - 'status': 'error'
                - 'message': str
    '''

    try:
        if not pattern:
            return (False, {'status': 'error', 'message': 'Pattern not provided'})

        search_dir = path if path else os.getcwd()
        search_dir = Path(search_dir)

        if not search_dir.exists():
            return (False, {'status': 'error', 'message': f'Search directory not found: {search_dir}'})

        regex = re.compile(pattern)
        matches = []
        files_with_matches = set()

        for root, dirs, files in os.walk(search_dir):
            # Skip common noise directories
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', '.DS_Store', 'node_modules', '.pytest_cache', '_staticfiles']]

            for filename in files:
                if include and not fnmatch.fnmatch(filename, include):
                    continue

                filepath = os.path.join(root, filename)
                try:
                    p = Path(filepath)
                    try:
                        content = p.read_text(encoding='utf-8')
                    except UnicodeDecodeError:
                        continue

                    for line_num, line in enumerate(content.split('\n'), 1):
                        if regex.search(line):
                            matches.append({
                                'file': str(filepath),
                                'line_number': line_num,
                                'line': line.strip()
                            })
                            files_with_matches.add(filepath)
                except (OSError, PermissionError):
                    continue

        return (True, {
            'status': 'success',
            'file_count': len(files_with_matches),
            'match_count': len(matches),
            'matches': matches,

        })

    except Exception as e:
        return (False, {
            'status': 'error',
            'message': f"Error searching for pattern '{pattern}': {str(e)}\n{traceback.format_exc()}"
        })

if __name__ == '__main__':
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Fast content search with regex.')
    parser.add_argument('pattern', type=str, help='Regex pattern to search for')
    parser.add_argument('--path', type=str, default=None, help='Directory to search in')
    parser.add_argument('--include', type=str, default=None, help='File pattern to include (e.g., "*.js")')
    args = parser.parse_args()

    success, result = grep(pattern=args.pattern, path=args.path, include=args.include)
    print(json.dumps(result, indent=2))
    exit(0 if success else 1)
