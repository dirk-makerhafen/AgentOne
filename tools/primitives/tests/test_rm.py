import pytest
import os
from tools.primitives.rm import rm

def test_rm_file_success(tmp_path):
    """Tests successful deletion of a single file."""
    f = tmp_path / "file.txt"
    f.touch()
    assert f.exists()
    
    result = rm(str(f))
    
    assert result['status'] == 'success'
    assert not f.exists()

def test_rm_empty_directory_success(tmp_path):
    """Tests successful deletion of an empty directory."""
    d = tmp_path / "empty_dir"
    d.mkdir()
    assert d.exists()
    
    result = rm(str(d))
    
    assert result['status'] == 'success'
    assert not d.exists()

def test_rm_non_empty_directory_fails_without_recursive(tmp_path):
    """Tests that rm fails on a non-empty directory without recursive=True."""
    d = tmp_path / "full_dir"
    d.mkdir()
    (d / "file.txt").touch()
    
    result = rm(str(d))
    
    assert result['status'] == 'error'
    assert "not empty" in result['message']
    assert d.exists()

def test_rm_non_empty_directory_recursive_succeeds(tmp_path):
    """Tests that rm succeeds on a non-empty directory with recursive=True."""
    d = tmp_path / "full_dir"
    d.mkdir()
    (d / "file.txt").touch()
    
    result = rm(str(d), recursive=True)
    
    assert result['status'] == 'success'
    assert not d.exists()

def test_rm_path_not_exist(tmp_path):
    """Tests that rm succeeds when the path does not exist."""
    p = tmp_path / "not_found"
    result = rm(str(p))
    
    assert result['status'] == 'success'
    assert "does not exist" in result['message']
