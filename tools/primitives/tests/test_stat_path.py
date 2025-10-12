import pytest
import os
import time
from tools.primitives.stat_path import stat_path

def test_stat_file(tmp_path):
    """Tests stat on a file."""
    p = tmp_path / "test.txt"
    content = "hello"
    p.write_text(content)
    
    result = stat_path(str(p))
    print(result)
    assert result['status'] == 'success'
    assert result['exists'] is True
    assert result['is_file'] is True
    assert result['is_dir'] is False
    assert result['size'] == len(content)
    assert 'ctime' in result
    assert 'mtime' in result

def test_stat_directory(tmp_path):
    """Tests stat on a directory."""
    p = tmp_path / "test_dir"
    p.mkdir()
    
    result = stat_path(str(p))
    
    assert result['status'] == 'success'
    assert result['exists'] is True
    assert result['is_file'] is False
    assert result['is_dir'] is True

def test_stat_not_found(tmp_path):
    """Tests stat on a non-existent path."""
    p = tmp_path / "not_found"
    result = stat_path(str(p))
    
    assert result['status'] == 'success'
    assert result['exists'] is False
    assert result['is_file'] is False
    assert result['is_dir'] is False
