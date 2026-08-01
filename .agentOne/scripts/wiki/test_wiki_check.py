from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
import django
django.setup()

from wiki_checks import (
    _resolve_wikilink_target,
    _strip_code_fences,
    _strip_inline_code,
)


def _eq(a: Path | None, b: Path | None) -> bool:
    if a is None or b is None:
        return a == b
    return a.resolve() == b.resolve()


def test_basic_resolve():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src_dir = root / "a"
        src_dir.mkdir()
        target = src_dir / "test.md"
        target.write_text("hello")

        assert _eq(_resolve_wikilink_target("test", src_dir, root), target)
        assert _eq(_resolve_wikilink_target("test.md", src_dir, root), target)


def test_anchor_strip():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src_dir = root / "a"
        src_dir.mkdir()
        target = src_dir / "test.md"
        target.write_text("hello")

        assert _eq(_resolve_wikilink_target("test#section", src_dir, root), target)
        assert _eq(_resolve_wikilink_target("test^block-id", src_dir, root), target)


def test_anchor_in_filename():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src_dir = root / "a"
        src_dir.mkdir()
        target = src_dir / "C-3PO#friends.md"
        target.write_text("hello")

        assert _eq(_resolve_wikilink_target("C-3PO#friends.md", src_dir, root), target)


def test_full_link_before_anchor():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src_dir = root / "a"
        src_dir.mkdir()
        target = src_dir / "C-3PO#friends.md"
        target.write_text("hello")

        anchor_target = src_dir / "C-3PO.md"
        anchor_target.write_text("hello")

        assert _eq(_resolve_wikilink_target("C-3PO#friends.md", src_dir, root), target)


def test_root_relative_prepending():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src_dir = root / "sub" / "dir"
        src_dir.mkdir(parents=True)
        target = root / "target.md"
        target.write_text("hello")

        assert _eq(_resolve_wikilink_target("target.md", src_dir, root), target)


def test_directory_link():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src_dir = root / "a"
        src_dir.mkdir()
        sub = root / "sub"
        sub.mkdir()
        idx = sub / "index.md"
        idx.write_text("hello")

        assert _eq(_resolve_wikilink_target("sub/", src_dir, root), idx)


def test_skip_urls():
    assert _resolve_wikilink_target("http://example.com", Path("/tmp"), Path("/tmp")) is None
    assert _resolve_wikilink_target("https://example.com", Path("/tmp"), Path("/tmp")) is None


def test_code_fence_strip():
    text = "normal [[link]]\n```\n[[inside-fence]]\n```\nouter [[link2]]"
    result = _strip_code_fences(text)
    assert "[[inside-fence]]" not in result
    assert "[[link]]" in result
    assert "[[link2]]" in result


def test_inline_code_strip():
    text = "text `[[not-a-link]]` more text"
    result = _strip_inline_code(text)
    assert "[[not-a-link]]" not in result


def test_skip_dir_dotdot():
    assert _resolve_wikilink_target("dir/..", Path("/tmp"), Path("/tmp")) is None


def test_percent_encoding():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src_dir = root / "a"
        src_dir.mkdir(parents=True)
        target = src_dir / "Märklin.md"
        target.write_text("hello")

        assert _eq(_resolve_wikilink_target("M%C3%A4rklin", src_dir, root), target)
        assert _eq(_resolve_wikilink_target("M%C3%A4rklin.md", src_dir, root), target)
