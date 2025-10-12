import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# This single test now covers the synchronous wrapper's validation logic.
def test_manage_tool_process_validation():
    """
    Tests that the synchronous wrapper `manage_tool_process` correctly
    validates the presence of required arguments for the 'start' action
    BEFORE dispatching to the async function.
    """
    from tools.primitives.manage_tool_process import manage_tool_process
    
    # We call the function with missing arguments.
    # We expect it to fail validation immediately.
    result = manage_tool_process(
        action='start',
        process_id='test_process_validation',
        command='python',
        cwd=None, # Missing cwd
        tool_config=None # Missing tool_config
    )
    
    # The function should return an error without ever trying to run async code.
    assert result['status'] == 'error'
    assert "'command', 'cwd', and 'tool_config' are required for start." in result['message']


# The rest of the tests will now focus on the internal async logic.
# By patching the internal async function, we can test its behavior directly.
@patch('tools.primitives.manage_tool_process._manage_tool_process_async', new_callable=AsyncMock)
def test_start_action_calls_async_correctly(mock_async_func):
    """
    Tests that a valid 'start' call to the sync wrapper correctly invokes
    the internal async function with all the right parameters.
    """
    from tools.primitives.manage_tool_process import manage_tool_process
    
    # We don't care about the return value of the mock, only that it was called.
    mock_async_func.return_value = {"status": "success"}

    manage_tool_process(
        action='start',
        process_id='test_start',
        command='test_cmd',
        args=['-a'],
        cwd='/test',
        env={'VAR': '1'},
        tool_config={'key': 'val'},
        tool_name='test_tool',
        tool_kwargs={'p': 1}
    )

    # Verify the internal async function was called exactly once with the correct args.
    mock_async_func.assert_awaited_once_with(
        'start', 'test_start', 'test_cmd', ['-a'], '/test', {'VAR': '1'},
        {'key': 'val'}, 'test_tool', {'p': 1}
    )

@patch('tools.primitives.manage_tool_process._manage_tool_process_async', new_callable=AsyncMock)
def test_stop_action_calls_async_correctly(mock_async_func):
    """
    Tests that a valid 'stop' call to the sync wrapper correctly invokes
    the internal async function.
    """
    from tools.primitives.manage_tool_process import manage_tool_process
    mock_async_func.return_value = {"status": "success"}

    manage_tool_process(action='stop', process_id='test_stop')

    # For 'stop', many arguments are None, which is expected.
    mock_async_func.assert_awaited_once_with(
        'stop', 'test_stop', None, None, None, None, None, None, None
    )

@patch('tools.primitives.manage_tool_process._manage_tool_process_async', new_callable=AsyncMock)
def test_invoke_action_calls_async_correctly(mock_async_func):
    """
    Tests that a valid 'invoke_tool' call dispatches correctly.
    """
    from tools.primitives.manage_tool_process import manage_tool_process
    mock_async_func.return_value = {"status": "success"}

    manage_tool_process(
        action='invoke_tool',
        process_id='test_invoke',
        tool_name='a_tool',
        tool_kwargs={'x': 'y'}
    )

    mock_async_func.assert_awaited_once_with(
        'invoke_tool', 'test_invoke', None, None, None, None, None, 'a_tool', {'x': 'y'}
    )
