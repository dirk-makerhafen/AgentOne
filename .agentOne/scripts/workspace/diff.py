import os
import subprocess
import difflib

def diff(caller, path=None, staged=False, target=None):
    '''
    Show a git diff or file diff.

    For git repositories:
    - Shows unstaged changes by default (equivalent to `git diff`)
    - Set staged=true for staged changes (equivalent to `git diff --staged`)
    - Set target to compare against a specific commit or branch (e.g., "HEAD~1", "main")

    For files:
    - Set path to a file and target to another file path to show a unified diff between them

    Args:
        path (str, optional): The path within the git repo, or first file for file comparison.
        staged (bool): If true, shows staged changes. Default: false.
        target (str, optional): A git ref (commit, branch) to diff against, or second file for file comparison.

    Returns:
        tuple: (success: bool, result: dict)
            On success, result contains:
                - 'status': 'success'
                - 'diff': str (unified diff output)
                - 'has_changes': bool
            On error, result contains:
                - 'status': 'error'
                - 'message': str
    '''
    cwd = caller.workingdir if hasattr(caller, 'workingdir') and caller.workingdir else os.getcwd()

    try:
        git_dir = os.path.join(cwd, '.git')
        is_git_repo = os.path.isdir(git_dir)

        if is_git_repo:
            cmd = ['git', 'diff']
            if staged:
                cmd.append('--staged')
            if target:
                cmd.append(target)
            if path:
                cmd.extend(['--', path])

            proc = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if proc.returncode != 0:
                return (False, {'status': 'error', 'message': f'git diff failed: {proc.stderr}'})

            diff_output = proc.stdout
            return (True, {
                'status': 'success',
                'diff': diff_output if diff_output else '(no changes)',
                'has_changes': bool(diff_output.strip())
            })
        else:
            if path and target:
                from pathlib import Path
                file1 = Path(path).read_text(encoding='utf-8').splitlines(keepends=True)
                file2 = Path(target).read_text(encoding='utf-8').splitlines(keepends=True)
                diff_output = ''.join(difflib.unified_diff(file1, file2, fromfile=path, tofile=target))
                return (True, {
                    'status': 'success',
                    'diff': diff_output if diff_output else '(no differences)',
                    'has_changes': bool(diff_output.strip())
                })
            else:
                return (False, {'status': 'error', 'message': 'Not a git repo. Provide both path and target for file comparison.'})

    except Exception as e:
        import traceback
        return (False, {'status': 'error', 'message': f'Error generating diff: {str(e)}\n{traceback.format_exc()}'})

if __name__ == '__main__':
    import argparse
    import json

    class MockCaller:
        def __init__(self):
            self.workingdir = os.getcwd()

    parser = argparse.ArgumentParser(description='Show a git diff or file diff.')
    parser.add_argument('--path', type=str, default=None, help='File path or git repo path')
    parser.add_argument('--staged', action='store_true', default=False, help='Show staged changes')
    parser.add_argument('--target', type=str, default=None, help='Git ref or second file path')
    args = parser.parse_args()

    success, result = diff(MockCaller(), path=args.path, staged=args.staged, target=args.target)
    if success:
        print(result.get('diff', ''))
    else:
        print(json.dumps(result, indent=2))
    exit(0 if success else 1)
