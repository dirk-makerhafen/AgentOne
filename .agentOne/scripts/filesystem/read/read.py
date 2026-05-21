import os
from pathlib import Path

def read(path, offset=1, limit=2000):
    '''
    Read a file or directory from the local filesystem.

    For files:
    - Returns the content with each line prefixed by its line number as "<line>: <content>".
    - By default, returns up to 2000 lines from the start of the file.
    - Use offset to start from a specific line number (1-indexed).
    - Use limit to control the maximum number of lines to read.
    - To read later sections, call this tool again with a larger offset.
    - If the path does not exist, an error is returned.

    For directories:
    - Returns entries one per line (without line numbers) with a trailing "/" for subdirectories.

    Args:
        path (str): The absolute path to the file or directory to read.
        offset (int): The line number to start reading from (1-indexed). Default: 1.
        limit (int): The maximum number of lines to read. Default: 2000.

    Returns:
        tuple: (success: bool, result: dict)
            On success, result contains:
                - 'status': 'success'
                - 'content': str (file content with line numbers) or list (directory entries)
                - 'path': str
                - 'type': 'file' or 'directory'
            On error, result contains:
                - 'status': 'error'
                - 'message': str
    '''

    try:
        if not path:
            return (False, {'status': 'error', 'message': 'Path not provided'})

        p = Path(path)
        if not p.exists():
            return (False, {'status': 'error', 'message': f'Path does not exist: {path}'})

        if p.is_dir():
            entries = []
            for entry in sorted(os.scandir(p), key=lambda e: e.name):
                if entry.name in ['.git', '__pycache__', '.DS_Store']:
                    continue
                try:
                    is_dir = entry.is_dir()
                    entries.append({
                        'path': entry.name,
                        'is_directory': is_dir,
                        'size': entry.stat().st_size,
                    })
                except OSError:
                    continue
            return (True, {
                'status': 'success',
                'content': entries,
                'path': str(path),
                'type': 'directory'
            })

        if p.is_file():
            try:
                content = p.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                content = p.read_text(encoding='latin-1')

            lines = content.split('\n')
            start = max(0, offset - 1)
            end = start + limit
            sliced = lines[start:end]
            total_lines = len(lines)

            output_lines = []
            for i, line in enumerate(sliced):
                output_lines.append(f'{start + i + 1}: {line}')

            result_content = '\n'.join(output_lines)
            if end < total_lines:
                result_content += f'\n\n... ({total_lines - end} more lines)'

            return (True, {
                'status': 'success',
                'path': str(path),
                'type': 'file',
                'total_lines': total_lines,
                'offset': offset,
                'limit': limit
                'content': result_content,
            })

        return (False, {'status': 'error', 'message': f'Path is neither a file nor a directory: {path}'})

    except Exception as e:
        import traceback
        return (False, {'status': 'error', 'message': f'Error reading {path}: {str(e)}\n{traceback.format_exc()}'})

if __name__ == '__main__':
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Read a file or directory.')
    parser.add_argument('path', type=str, help='Path to file or directory')
    parser.add_argument('--offset', type=int, default=1, help='Starting line number (1-indexed)')
    parser.add_argument('--limit', type=int, default=2000, help='Max lines to read')
    args = parser.parse_args()

    success, result = read(path=args.path, offset=args.offset, limit=args.limit)
    if result.get('type') == 'file':
        print(result.get('content', ''))
    else:
        print(json.dumps(result, indent=2))
    exit(0 if success else 1)
