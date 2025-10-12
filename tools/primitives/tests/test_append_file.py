import pytest
from tools.primitives.append_file import append_file

def test_append_to_existing_file(tmp_path):
    """Tests appending content to a file that already exists."""
    test_file = tmp_path / "log.txt"
    initial_content = "Line 1\n"
    append_content = "Line 2"
    test_file.write_text(initial_content)
    
    result = append_file(str(test_file), append_content)
    
    assert result['status'] == 'success'
    assert test_file.read_text() == initial_content + append_content

def test_append_creates_new_file(tmp_path):
    """Tests that append_file creates a new file if it doesn't exist."""
    test_file = tmp_path / "new_log.txt"
    content = "First line"
    
    result = append_file(str(test_file), content)
    
    assert result['status'] == 'success'
    assert test_file.exists()
    assert test_file.read_text() == content

def test_append_no_path():
    """Tests that append_file returns an error if no path is provided."""
    result = append_file("", "some content")
    assert result['status'] == 'error'
    assert "Path not provided" in result['message']

def test_append_to_directory_error(tmp_path):
    """Tests that appending to a directory returns an error."""
    result = append_file(str(tmp_path), "some content")
    assert result['status'] == 'error'
    # Error message varies by OS, so check for a common part
    assert "Error appending to file" in result['message']
