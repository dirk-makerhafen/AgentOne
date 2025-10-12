import pytest
from tools.primitives.run_python_code import run_python_code

def test_run_python_success_with_stdout():
    """Tests successful execution of Python code that prints to stdout."""
    code = "print('hello python')"
    result = run_python_code(code)
    
    assert result['status'] == 'success'
    assert result['stdout'].strip() == 'hello python'

def test_run_python_with_exception():
    """Tests code that raises an exception."""
    code = 'raise ValueError("This is a test error")'
    result = run_python_code(code)
    
    assert result['status'] == 'error'
    # The runner script catches the exception and puts it in the message
    assert 'Exception: This is a test error' in result['message']
    # The traceback is printed to stderr
    assert 'ValueError: This is a test error' in result['stderr']

def test_run_python_return_vars():
    """Tests the returning of specified local variables."""
    code = "x = 10; y = 'hello'; z = [1, 2]"
    result = run_python_code(code, locals_to_return=['x', 'z'])
    
    assert result['status'] == 'success'
    assert 'vars' in result
    assert result['vars']['x'] == 10
    assert result['vars']['z'] == [1, 2]
    assert 'y' not in result['vars']

def test_run_python_uses_provided_locals():
    """Tests that the executed code can access provided local variables."""
    code = "c = a + b"
    # CORRECTED: The keyword argument is 'locals_dict', not 'locals'.
    locals_in = {"a": 5, "b": 7}
    result = run_python_code(code, locals_dict=locals_in, locals_to_return=['c'])
    
    assert result['status'] == 'success'
    assert result['vars']['c'] == 12
