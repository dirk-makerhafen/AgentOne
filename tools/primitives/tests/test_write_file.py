import pytest
import os
from pathlib import Path
from tools.primitives.write_file import write_file

def test_write_file_success(tmp_path):
    """Tests that write_file successfully creates and writes content to a new file."""
    test_file = tmp_path / "test.txt"
    content = "Hello, world!"

    result = write_file(str(test_file), content)

    assert result['status'] == 'success'
    assert test_file.exists()
    assert test_file.read_text(encoding='utf-8') == content

def test_write_file_overwrite(tmp_path):
    """Tests that write_file correctly overwrites an existing file."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Initial content")
    new_content = "Overwritten content"

    result = write_file(str(test_file), new_content)

    assert result['status'] == 'success'
    assert test_file.read_text(encoding='utf-8') == new_content

def test_write_file_creates_directories(tmp_path):
    """Tests that write_file creates necessary parent directories."""
    test_file = tmp_path / "subdir" / "another_dir" / "test.txt"
    content = "Content in a nested directory"

    result = write_file(str(test_file), content)

    assert result['status'] == 'success'
    assert test_file.exists()
    assert test_file.read_text(encoding='utf-8') == content
    assert (tmp_path / "subdir" / "another_dir").is_dir()

def test_write_file_no_path():
    """Tests that write_file returns an error if no path is provided."""
    result = write_file("", "some content")
    assert result['status'] == 'error'
    assert "Path not provided" in result['message']

def test_write_file_permission_error(monkeypatch):
    """Tests error handling for file system permissions."""
    # Mock Path.write_text to raise a PermissionError
    def mock_write_text(*args, **kwargs):
        raise PermissionError("Permission denied")

    monkeypatch.setattr(Path, "write_text", mock_write_text)

    # We need to mock mkdir as well, as it's called before write_text
    monkeypatch.setattr(Path, "mkdir", lambda *args, **kwargs: None)
    
    result = write_file("/fake/path/test.txt", "content")
    
    assert result['status'] == 'error'
    assert "Permission denied" in result['message']
