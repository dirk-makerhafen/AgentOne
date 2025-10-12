import pytest
from tools.primitives.list_directory import list_directory

def test_list_directory_success(tmp_path):
    """Tests listing contents of a directory."""
    d = tmp_path / "test_dir"
    d.mkdir()
    (d / "file1.txt").touch()
    (d / "file2.log").touch()
    (d / "subdir").mkdir()
    
    result = list_directory(str(d))
    print(result)
    assert result['status'] == 'success'
    assert len(result['content']) == 3
    # Use sets for order-independent comparison
    assert set(item['path'] for item in result['content']) == {"file1.txt", "file2.log", "subdir"}
    
    # Check item types
    item_map = {item['path']: item for item in result['content']}
    assert item_map['file1.txt']['is_directory'] == False
    assert item_map['subdir']['is_directory'] == True

def test_list_directory_recursive_success(tmp_path):
    """Tests listing contents of a directory recursively."""
    d = tmp_path / "test_dir"
    d.mkdir()
    (d / "file1.txt").touch()
    sub = d / "subdir"
    sub.mkdir()
    (sub / "nested_file.txt").touch()

    result = list_directory(str(d), recursive=True)
    assert result['status'] == 'success'
    assert len(result['content']) == 3

def test_list_directory_not_found(tmp_path):
    """Tests listing a non-existent path."""
    result = list_directory(str(tmp_path / "nonexistent"))
    assert result['status'] == 'error'
    assert "Directory not found" in result['message']

def test_list_directory_path_is_file(tmp_path):
    """Tests listing a path that is a file."""
    f = tmp_path / "file.txt"
    f.touch()
    result = list_directory(str(f))
    assert result['status'] == 'error'
    assert "Not a Directory" in result['message']
