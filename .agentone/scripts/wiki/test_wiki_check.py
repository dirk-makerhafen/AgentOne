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
    _resolve_folder,
    _resolve_wikilink_target,
    _strip_code_fences,
    _strip_inline_code,
    wiki_check,
)


class _FakeWorkspace:
    def __init__(self, path):
        self.path = path


class _FakeAgent:
    def __init__(self, name):
        self.name = name


class _FakeVersion:
    def __init__(self, agent_name, workspace_path):
        self.agent = _FakeAgent(agent_name)
        self.workspace = _FakeWorkspace(workspace_path) if workspace_path else None


class _FakeSession:
    def __init__(self, agent_name, workspace_path):
        self.workspace = _FakeWorkspace(workspace_path) if workspace_path else None
        self._version = _FakeVersion(agent_name, workspace_path)

    def get_version_model(self):
        return self._version


def test_resolve_folder_wiki_agent_self_uses_own_workspace():
    session = _FakeSession("wiki", "/tmp/vault")
    assert _resolve_folder(None, session) == "/tmp/vault"


def test_resolve_folder_explicit_folder_wins():
    session = _FakeSession("wiki", "/tmp/vault")
    assert _resolve_folder("/elsewhere/wiki", session) == "/elsewhere/wiki"


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


def test_dead_wikilink_suggestion_is_vault_root_relative():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src = root / "buchhaltung" / "2021" / "02" / "Eingangs_Rechnungen"
        src.mkdir(parents=True)
        src_file = src / "Soniflex-Rechnung-446658.md"
        src_file.write_text("[[../../../../timeline/2021/02/08/Soniflex-Rechnung-446658.md]]\n")
        tgt = root / "timeline" / "2021" / "02" / "2021" / "02" / "08"
        tgt.mkdir(parents=True)
        (tgt / "Soniflex-Rechnung-446658.md").write_text("hi\n")

        ok, res = wiki_check(None, folder=str(root), limit=0)
        assert ok
        dead = next(c for c in res["checks"] if c["check"] == "dead_wikilinks")
        assert dead["wrong"] == 1
        item = dead["items"][0]
        assert item["suggestion"] == "timeline/2021/02/2021/02/08/Soniflex-Rechnung-446658.md"
        assert not item["suggestion"].startswith("..")


def test_link_format_flags_bare_and_relative_not_root_relative():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "a").mkdir()
        (root / "b" / "c").mkdir(parents=True)
        (root / "b" / "c" / "note.md").write_text("hi\n")
        main = root / "a" / "main.md"
        main.write_text("[[note]] and [[../b/c/note.md]] and [[/b/c/note.md]] and [[b/c/note.md]]\n")

        ok, res = wiki_check(None, folder=str(root), limit=0)
        assert ok
        fmt = next(c for c in res["checks"] if c["check"] == "link_format")
        assert fmt["wrong"] == 3
        by_link = {i["link"]: i for i in fmt["items"]}
        assert by_link["note"]["suggestion"] == "b/c/note.md"
        assert by_link["../b/c/note.md"]["suggestion"] == "b/c/note.md"
        assert by_link["/b/c/note.md"]["suggestion"] == "b/c/note.md"
        assert all(i["can_autofix"] for i in fmt["items"])


def test_link_format_autofix_rewrites_to_root_relative():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "a").mkdir()
        (root / "b" / "c").mkdir(parents=True)
        (root / "b" / "c" / "note.md").write_text("hi\n")
        main = root / "a" / "main.md"
        main.write_text("[[../b/c/note.md]]\n")

        ok, res = wiki_check(None, folder=str(root), limit=0, autofix=True)
        assert ok
        assert main.read_text() == "[[b/c/note.md]]\n"
        fmt = next(c for c in res["checks"] if c["check"] == "link_format")
        assert fmt["items"][0]["autofixed"] is True


def _structure(root: Path) -> dict:
    ok, res = wiki_check(None, folder=str(root), limit=0)
    assert ok
    return next(c for c in res["checks"] if c["check"] == "folder_structure")


def test_folder_structure_detects_duplicate_year():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        d = root / "timeline" / "2020" / "2020"
        d.mkdir(parents=True)
        (d / "note.md").write_text("hi\n")
        res = _structure(root)
        assert res["wrong"] == 1
        assert res["items"][0]["folder"] == "timeline/2020/2020"
        assert any("multiple year segments" in i for i in res["items"][0]["issues"])


def test_folder_structure_detects_nested_date_folders():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        d = root / "timeline" / "2021" / "02" / "2021" / "02" / "08"
        d.mkdir(parents=True)
        (d / "note.md").write_text("hi\n")
        res = _structure(root)
        assert res["wrong"] == 1
        assert res["items"][0]["folder"] == "timeline/2021/02/2021"
        assert res["items"][0]["issues"] == ["multiple year segments: 2021 / 2021"]


def test_folder_structure_detects_invalid_month_and_day():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "timeline" / "2021" / "13").mkdir(parents=True)
        (root / "timeline" / "2021" / "13" / "note.md").write_text("hi\n")
        (root / "timeline" / "2022" / "02" / "32").mkdir(parents=True)
        (root / "timeline" / "2022" / "02" / "32" / "note.md").write_text("hi\n")
        res = _structure(root)
        assert res["wrong"] == 2
        issues = {i["folder"]: i["issues"] for i in res["items"]}
        assert any("invalid month '13'" in x for x in issues["timeline/2021/13"])
        assert any("invalid day '32'" in x for x in issues["timeline/2022/02/32"])


def test_folder_structure_valid_dates_no_issues():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "timeline" / "2021" / "02" / "08").mkdir(parents=True)
        (root / "timeline" / "2021" / "02" / "08" / "note.md").write_text("hi\n")
        (root / "buchhaltung" / "2021" / "02" / "Eingangs_Rechnungen").mkdir(parents=True)
        (root / "buchhaltung" / "2021" / "02" / "Eingangs_Rechnungen" / "rechnung.md").write_text("hi\n")
        res = _structure(root)
        assert res["wrong"] == 0
