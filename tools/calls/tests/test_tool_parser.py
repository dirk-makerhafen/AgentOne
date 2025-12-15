import pytest
from tools.calls.tool_parser import parse_responsestring # Corrected import

@pytest.mark.django_db
def test_parse_single_tool_call():
    """
    Tests parsing a single, valid tool call.
    """
    code = """
@@@fs_load(path="example.txt")@@@
"""
    parsed_calls = parse_responsestring(code) 

    assert len(parsed_calls) == 1
    assert parsed_calls[0]['tool'] == 'fs_load' # Changed 'function' to 'tool' based on parse_tool_code's output structure
    assert parsed_calls[0]['arguments'] == {'path': 'example.txt'} # Changed 'kwargs' to 'arguments'

@pytest.mark.django_db
def test_parse_multiple_tool_calls():
    """
    Tests parsing multiple valid tool calls.
    """
    code = """
@@@fs_load(path="file1.txt")@@@
Some intermediate text.
@@@fs_write(path="file2.txt", content="hello")@@@
"""
    parsed_calls = parse_responsestring(code) 

    assert len(parsed_calls) == 3
    assert parsed_calls[0]['tool'] == 'fs_load'
    assert parsed_calls[0]['arguments'] == {'path': 'file1.txt'}
    assert parsed_calls[2]['tool'] == 'fs_write'
    assert parsed_calls[2]['arguments'] == {'path': 'file2.txt', 'content': 'hello'}

@pytest.mark.django_db
def test_parse_tool_call_with_various_arg_types():
    """
    Tests parsing a tool call with different argument types (str, int, bool, list, dict).
    """
    code = """
@@@some_tool(name='test', count=10, active=True, items=['a', 'b'], details={'key': 'value'})@@@
"""
    parsed_calls = parse_responsestring(code) 
    print(parsed_calls)
    assert len(parsed_calls) == 1
    call = parsed_calls[0]
    assert call['tool'] == 'some_tool'
    assert call['arguments'] == {
        'name': 'test',
        'count': 10,
        'active': True,
        'items': ['a', 'b'],
        'details': {'key': 'value'}
    }

@pytest.mark.django_db
def test_parse_tool_call_with_escaped_strings():
    """
    Tests parsing tool calls where string arguments contain escaped quotes.
    """
    code = """
@@@fs_write(path='quoted_file.txt', content='This has a \\'single\\' quote and a \\"double\\" quote.')@@@
@@@another_tool(message="Path with spaces: C:\\\\Users\\\\Me\\\\file.txt")@@@
"""
    parsed_calls = parse_responsestring(code) 
    print(parsed_calls)
    assert len(parsed_calls) == 2
    assert parsed_calls[0]['tool'] == 'fs_write'
    assert parsed_calls[0]['arguments'] == {'path': 'quoted_file.txt', 'content': 'This has a \'single\' quote and a "double" quote.'}
    assert parsed_calls[1]['tool'] == 'another_tool'
    assert parsed_calls[1]['arguments'] == {'message': 'Path with spaces: C:\\Users\\Me\\file.txt'}


@pytest.mark.django_db
def test_parse_tool_call_with_multi_line_content():
    """
    Tests parsing tool calls with multi-line string content.
    """
    code = '''
@@@fs_write(path='multi_line.txt', content=\'\'\'
Line 1
Line 2
Line 3
\'\'\')@@@
'''
    parsed_calls = parse_responsestring(code) 

    assert len(parsed_calls) == 1
    call = parsed_calls[0]
    assert call['tool'] == 'fs_write'
    expected_content = "\nLine 1\nLine 2\nLine 3\n"
    assert call['arguments'] == {'path': 'multi_line.txt', 'content': expected_content}

@pytest.mark.django_db
def test_parse_malformed_tool_call_missing_function():
    """
    Tests parsing of a malformed tool call missing the function name.
    Should return an empty list or ignore it.
    """
    code = """
@@@ (path="invalid.txt")@@@
"""
    parsed_calls = parse_responsestring(code) 
    assert len(parsed_calls) == 1

@pytest.mark.django_db
def test_parse_no_tool_calls():
    """
    Tests parsing content with no tool calls.
    """
    code = "This is a regular message without any tool calls."
    parsed_calls = parse_responsestring(code) 
    assert len(parsed_calls) == 1

@pytest.mark.django_db
def test_parse_empty_string():
    """
    Tests parsing an empty string.
    """
    code = ""
    parsed_calls = parse_responsestring(code) 
    assert len(parsed_calls) == 0

@pytest.mark.django_db
def test_parse_mixed_content_with_invalid_calls():
    """
    Tests parsing content with valid and invalid tool calls.
    Invalid calls should be ignored, and valid ones parsed.
    """
    code = """
@@@fs_load(path="valid1.txt")@@@
Some text.
@@@fs_write(path="valid2.txt", content="stuff")@@@
@@@invalid_call(arg=)@@@
More text.
@@@fs_append(path="valid3.txt", content="more stuff")@@@
"""
    parsed_calls = parse_responsestring(code) 
    assert len(parsed_calls) == 6
    assert parsed_calls[0]['tool'] == 'fs_load'
    assert parsed_calls[0]['arguments'] == {'path': 'valid1.txt'}
    assert parsed_calls[2]['tool'] == 'fs_write'
    assert parsed_calls[2]['arguments'] == {'path': 'valid2.txt', 'content': 'stuff'}
    assert parsed_calls[5]['tool'] == 'fs_append'
    assert parsed_calls[5]['arguments'] == {'path': 'valid3.txt', 'content': 'more stuff'}
