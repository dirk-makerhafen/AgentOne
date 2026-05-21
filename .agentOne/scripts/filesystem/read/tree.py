import os
from pathlib import Path

def tree(path=None, depth=3, include_hidden=False):
    '''
    Display a visual directory tree structure.

    Shows files and directories in a tree format, useful for understanding project structure.
    Much better UX than a flat directory listing.

    Args:
        path (str, optional): The directory to display. Defaults to the working directory.
        depth (int): Maximum depth to traverse. Default: 3.
        include_hidden (bool): Include hidden files/dirs (starting with "."). Default: false.

    Returns:
        tuple: (success: bool, result: dict)
            On success, result contains:
                - 'status': 'success'
                - 'tree': str (visual tree output)
                - 'path': str
            On error, result contains:
                - 'status': 'error'
                - 'message': str
    '''
    target = path if path else  os.getcwd()

    try:
        target_path = Path(target)
        if not target_path.exists():
            return (False, {'status': 'error', 'message': f'Path not found: {target}'})
        if not target_path.is_dir():
            return (False, {'status': 'error', 'message': f'Not a directory: {target}'})

        skip_dirs = {'.git', '__pycache__', '.DS_Store', 'node_modules', '.pytest_cache', '_staticfiles'}

        lines = []

        def _walk(dir_path, prefix, current_depth):
            if current_depth > depth:
                return
            try:
                entries = sorted(os.scandir(dir_path), key=lambda e: e.name)
            except PermissionError:
                return

            dirs = []
            files = []
            for entry in entries:
                if not include_hidden and entry.name.startswith('.'):
                    continue
                if entry.is_dir():
                    if entry.name not in skip_dirs:
                        dirs.append(entry)
                else:
                    files.append(entry)

            all_items = dirs + files
            for i, entry in enumerate(all_items):
                is_last = (i == len(all_items) - 1)
                connector = "└── " if is_last else "├── "
                if entry.is_dir():
                    lines.append(f"{prefix}{connector}{entry.name}/")
                    extension = "    " if is_last else "│   "
                    _walk(entry.path, prefix + extension, current_depth + 1)
                else:
                    try:
                        size = entry.stat().st_size
                        size_str = _human_size(size)
                        lines.append(f"{prefix}{connector}{entry.name} ({size_str})")
                    except OSError:
                        lines.append(f"{prefix}{connector}{entry.name}")

        def _human_size(n):
            for unit in ['B', 'KB', 'MB', 'GB']:
                if n < 1024:
                    return f"{n:.0f}{unit}" if n > 0 else f"0{unit}"
                n /= 1024
            return f"{n:.0f}TB"

        lines.append(target_path.name + "/")
        _walk(target_path, "", 1)

        return (True, {
            'status': 'success',
            'path': str(target),
            'tree': '\n'.join(lines),
        })

    except Exception as e:
        import traceback
        return (False, {'status': 'error', 'message': f'Error generating tree: {str(e)}\n{traceback.format_exc()}'})

if __name__ == '__main__':
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Display directory tree.')
    parser.add_argument('path', type=str, nargs='?', default=None, help='Directory to display')
    parser.add_argument('--depth', type=int, default=3, help='Max depth to traverse')
    parser.add_argument('--hidden', action='store_true', default=False, help='Include hidden files')
    args = parser.parse_args()

    success, result = tree(path=args.path, depth=args.depth, include_hidden=args.hidden)
    if success:
        print(result.get('tree', ''))
    else:
        print(json.dumps(result, indent=2))
    exit(0 if success else 1)
