from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def tree(
    path: str,
    depth: int = 3,
    include_hidden: bool = False,
) -> tuple[bool, dict]:
    '''
    Display a visual directory tree structure.

    Shows files and directories in a tree format, useful for
    understanding project structure. Much better UX than a flat
    directory listing.

    Args:
        path: The directory to display. Defaults to the working
            directory.
        depth: Maximum depth to traverse. Default: 3.
        include_hidden: Include hidden files/dirs (starting with ".").
            Default: false.

    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - tree: visual tree output (str)
            - path: str
        On error, result contains:
            - status: "error"
            - message: str
    '''

    try:
        target_path = Path(path)
        if not target_path.exists():
            return (False, {'status': 'error', 'message': f'Path not found: {path}'})
        if not target_path.is_dir():
            return (False, {'status': 'error', 'message': f'Not a directory: {path}'})

        skip_dirs = {'.git', '__pycache__', '.DS_Store', 'node_modules', '.pytest_cache', '_staticfiles'}

        lines = []

        def _walk(dir_path: str, prefix: str, current_depth: int) -> None:
            '''Recursively walk a directory and build tree lines.

            Args:
                dir_path: Path to the directory to walk.
                prefix: String prefix for tree indentation.
                current_depth: Current recursion depth.
            '''
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
                connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
                if entry.is_dir():
                    lines.append(f"{prefix}{connector}{entry.name}/")
                    extension = "    " if is_last else "\u2502   "
                    _walk(entry.path, prefix + extension, current_depth + 1)
                else:
                    try:
                        size = entry.stat().st_size
                        size_str = _human_size(size)
                        lines.append(f"{prefix}{connector}{entry.name} ({size_str})")
                    except OSError:
                        lines.append(f"{prefix}{connector}{entry.name}")

        def _human_size(n: float) -> str:
            '''Convert a byte count to a human-readable string.

            Args:
                n: Number of bytes.

            Returns:
                Human-readable size string (e.g., "1KB", "2MB").
            '''
            for unit in ['B', 'KB', 'MB', 'GB']:
                if n < 1024:
                    return f"{n:.0f}{unit}" if n > 0 else f"0{unit}"
                n /= 1024
            return f"{n:.0f}TB"

        lines.append(target_path.name + "/")
        _walk(target_path.as_posix(), "", 1)

        return (True, {
            'status': 'success',
            'path': str(target_path),
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
