def append(path, content):
    '''
    Appends content to the end of a file.

    - Creates the file and parent directories if they don't exist.
    - Content is appended as-is, without a leading newline.
    - Use this when you want to add to an existing file without overwriting.

    Args:
        path (str): The absolute path to the file to append to.
        content (str): The content to append.

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
        if content is None:
            return (False, {'status': 'error', 'message': 'Content not provided'})

        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding='utf-8') as f:
            f.write(str(content))

        return (True, {
            'status': 'success',
            'message': f"Appended to file '{path}' successfully."
        })

    except Exception as e:
        return (False, {
            'status': 'error',
            'message': f"Error appending to file {path}: {str(e)}\n{traceback.format_exc()}"
        })

if __name__ == '__main__':
    import argparse
    import json
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(description='Append content to a file.')
    parser.add_argument('path', type=str, help='Path to file')
    parser.add_argument('--content', type=str, default=None, help='Content to append')
    parser.add_argument('--file', type=str, default=None, help='File to read content from')
    args = parser.parse_args()

    content = args.content
    if args.file:
        content = Path(args.file).read_text(encoding='utf-8')
    elif content is None:
        content = sys.stdin.read()

    success, result = append(path=args.path, content=content)
    print(json.dumps(result, indent=2))
    exit(0 if success else 1)
