from __future__ import annotations


def mkdir(path: str, parents: bool = False, exist_ok: bool = True) -> tuple[bool, dict]:
    '''
    Creates a directory, including any necessary parent directories.

    Behaves like `mkdir -p` when parents=True.

    Args:
        path: The absolute path to the directory to create.
        parents: Create parent directories if they don't exist.
            Default: false.
        exist_ok: Do not raise an error if the directory already
            exists. Default: true.

    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - message: str
        On error, result contains:
            - status: "error"
            - message: str
    '''
    import os
    import traceback

    try:
        if not path:
            return (False, {'status': 'error', 'message': 'Path not provided'})

        if parents:
            os.makedirs(path, exist_ok=exist_ok)
        else:
            if os.path.isfile(path):
                return (False, {'status': 'error', 'message': f"A file already exists with the same name: {path}"})
            elif os.path.isdir(path):
                if exist_ok is False:
                    return (False, {'status': 'error', 'message': f"Directory already exists: {path}"})
            else:
                os.mkdir(path)

        return (True, {
            'status': 'success',
            'message': f"Directory '{path}' created successfully.",
        })

    except Exception as e:
        return (False, {
            'status': 'error',
            'message': f"Error creating directory {path}: {str(e)}\n{traceback.format_exc()}",
        })

if __name__ == '__main__':
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Create a directory.')
    parser.add_argument('path', type=str, help='Directory path to create')
    parser.add_argument('--parents', '-p', action='store_true', default=False, help='Create parent directories')
    parser.add_argument('--exist-ok', action='store_true', default=True, help='No error if directory exists')
    args = parser.parse_args()

    success, result = mkdir(path=args.path, parents=args.parents, exist_ok=args.exist_ok)
    print(json.dumps(result, indent=2))
    exit(0 if success else 1)
