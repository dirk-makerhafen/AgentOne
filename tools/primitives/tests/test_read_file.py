import pytest
from tools.primitives.read_file import read_file

def test_read_file_success(tmp_path):
    """Tests successful reading of a file's content."""
    test_file = tmp_path / "test.txt"
    content = "Hello, world!"
    test_file.write_text(content, encoding='utf-8')

    result = read_file(str(test_file))

    assert result['status'] == 'success'
    assert result['content'] == content

def test_read_file_not_found(tmp_path):
    """Tests that read_file returns an error for a non-existent file."""
    non_existent_file = tmp_path / "not_here.txt"
    
    result = read_file(str(non_existent_file))
    
    assert result['status'] == 'error'
    assert "File not found" in result['message']

def test_read_file_is_directory(tmp_path):
    """Tests that read_file returns an error when the path is a directory."""
    result = read_file(str(tmp_path))
    
    assert result['status'] == 'error'
    assert "not a regular file" in result['message']

def test_read_file_encoding_fallback(tmp_path):
    """Tests that read_file correctly falls back to latin-1 for non-UTF-8 files."""
    test_file = tmp_path / "test_latin1.txt"
    # 0xe9 is 'é', which is valid in latin-1 but not as a standalone byte in UTF-8
    content_bytes = b"H\xe9llo"
    test_file.write_bytes(content_bytes)
    
    result = read_file(str(test_file))

    assert result['status'] == 'success'
    assert result['content'] == content_bytes.decode('latin-1')

def test_read_file_no_path():
    """Tests that read_file returns an error if no path is provided."""
    result = read_file("")
    assert result['status'] == 'error'
    assert "Path not provided" in result['message']
