
def mkdir(caller, path, parents=False, exist_ok=True):
    '''
    Creates a directory, including any necessary parent directories.
    Behaves like `mkdir -p` when parents=True.

    Args:
        path (str): The absolute path to the directory to create.
        parents (bool): Create parent directories if they don't exist. Default: false.
        exist_ok (bool): Do not raise an error if the directory already exists. Default: true.

    Returns:
        tuple: (success: bool, result: dict)
            On success, result contains:
                - 'status': 'success'
                - 'message': str
            On error, result contains:
                - 'status': 'error'
                - 'message': str
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
            'message': f"Directory '{path}' created successfully."
        })

    except Exception as e:
        return (False, {
            'status': 'error',
            'message': f"Error creating directory {path}: {str(e)}\n{traceback.format_exc()}"
        })
