import pytest
import os
from tools.primitives.mkdir import mkdir

def test_mkdir_success(tmp_path):
    """Tests successful creation of a single directory."""
    new_dir = tmp_path / "new_dir"
    result = mkdir(str(new_dir))
    
    assert result['status'] == 'success'
    assert new_dir.is_dir()

def test_mkdir_recursive_success(tmp_path):
    """Tests successful creation of nested directories."""
    nested_dir = tmp_path / "parent" / "child"
    result = mkdir(str(nested_dir), parents=True)
    
    assert result['status'] == 'success'
    assert nested_dir.is_dir()

def test_mkdir_already_exists_not_allowed(tmp_path):
    """Tests that mkdir fails if the directory already exists and exist_ok is False"""
    existing_dir = tmp_path / "exists"
    existing_dir.mkdir()
    
    result = mkdir(str(existing_dir), exist_ok=False)
    
    assert result['status'] == 'error'
    assert "Directory already exists" in result['message']

def test_mkdir_already_exists_allowed(tmp_path):
    """Tests that mkdir succeeds if the directory already exists and exist_ok is True"""
    existing_dir = tmp_path / "exists"
    existing_dir.mkdir()
    
    result = mkdir(str(existing_dir))
    
    assert result['status'] == 'success'


def test_mkdir_path_is_file_error(tmp_path):
    """Tests that mkdir returns an error if a file exists at the path."""
    test_file = tmp_path / "file.txt"
    test_file.touch()
    
    result = mkdir(str(test_file))
    print(result)
    assert result['status'] == 'error'
    assert "A file already exists with the same name" in result['message']

def test_mkdir_no_path():
    """Tests that mkdir returns an error if no path is provided."""
    result = mkdir("")
    assert result['status'] == 'error'
    assert "Path not provided" in result['message']
