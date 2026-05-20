
def write(path, content):
    '''
    Write a file to the local filesystem.

    - This tool will overwrite the existing file if there is one at the provided path.
    - If this is an existing file, you MUST use the Read tool first to read the file's contents.
    - ALWAYS prefer editing existing files in the codebase. NEVER write new files unless explicitly required.
    - NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
    - Only use emojis if the user explicitly requests it. Avoid writing emojis to files unless asked.

    Args:
        path (str): The absolute path to the file to write (must be absolute, not relative).
        content (str): The content to write to the file.

    Returns:
        tuple: (success: bool, result: dict)
            On success, result contains:
                - 'status': 'success'
                - 'message': str
            On error, result contains:
                - 'status': 'error'
                - 'message': str
    '''
    from pathlib import Path
    import traceback

    try:
        if not path:
            return (False, {'status': 'error', 'message': 'Path not provided'})

        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            p.write_text(content, encoding='utf-8')
        else:
            p.write_bytes(content)

        return (True, {
            'status': 'success',
            'message': f"File '{path}' written successfully."
        })

    except Exception as e:
        return (False, {
            'status': 'error',
            'message': f"Error writing to file {path}: {str(e)}\n{traceback.format_exc()}"
        })

if __name__ == '__main__':
    import argparse
    import json
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(description='Write a file.')
    parser.add_argument('path', type=str, help='Path to write')
    parser.add_argument('--content', type=str, default=None, help='Content to write')
    parser.add_argument('--file', type=str, default=None, help='File to read content from')
    args = parser.parse_args()

    content = args.content
    if args.file:
        content = Path(args.file).read_text(encoding='utf-8')
    elif content is None:
        content = sys.stdin.read()

    success, result = write(path=args.path, content=content)
    print(json.dumps(result, indent=2))
    exit(0 if success else 1)
