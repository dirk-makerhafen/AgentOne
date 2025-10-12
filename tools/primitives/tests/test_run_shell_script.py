import pytest
import sys
from tools.primitives.run_shell_script import run_shell_script

def test_run_shell_success_with_stdout():
    """Tests a successful shell command that produces stdout."""
    # 'echo' is a cross-platform command
    command = 'echo "hello shell"'
    result = run_shell_script(command)
    
    assert result['status'] == 'success'
    assert result['return_code'] == 0
    assert result['stdout'].strip() == "hello shell"
    assert 'stderr' not in result or result['stderr'] == ''

def test_run_shell_with_stderr():
    """Tests a command that fails and produces stderr."""
    # This command will fail on all platforms and write to stderr
    command = 'ls non_existent_directory_for_test'
    result = run_shell_script(command)
    
    assert result['status'] == 'success' # The script itself ran, but the command failed
    assert result['return_code'] != 0
    assert 'stderr' in result
    assert 'non_existent_directory_for_test' in result['stderr']

def test_run_shell_timeout():
    """Tests the timeout functionality."""
    # Use a platform-specific sleep command
    sleep_command = 'timeout 3' if sys.platform == 'win32' else 'sleep 3'
    result = run_shell_script(sleep_command, timeout=1)
    
    assert result['status'] == 'error'
    assert 'timed out' in result['message']
