"""Test report generator — writes structured markdown reports to the test workspace.

Usage:
    from server.tests.test_reporter import TestReport

    class MyTest(TestCase):
        @classmethod
        def setUpClass(cls):
            super().setUpClass()
            cls.report = TestReport(cls)

        @classmethod
        def tearDownClass(cls):
            cls.report.write()
            super().tearDownClass()

    # Inside a test method:
    self.report.add("test_something", "PASS", "This test verifies that ...")
    # Or mark as FAIL if it unexpectedly passes/fails:
    self.report.add("test_something", "FAIL", "Expected X but got Y because ...")
"""

from __future__ import annotations

import os
from pathlib import Path

_REPORT_DIR: Path | None = None


def _ensure_report_dir() -> Path:
    global _REPORT_DIR
    if _REPORT_DIR is None:
        _REPORT_DIR = (
            Path(__file__).resolve().parent
            / "testproject"
            / "workspace"
            / "test-reports"
        )
        _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    return _REPORT_DIR


class TestReport:
    """Per-test-class report builder.

    Each test class gets one markdown file named after the module + class,
    e.g. ``test_dc_model__DataCollectionModelTest.md``.
    """

    __test__ = False  # prevent pytest from collecting this as a test class

    def __init__(self, test_class: type) -> None:
        module_name = os.path.splitext(os.path.basename(
            getattr(test_class, "__module__", "unknown")
        ))[0]
        class_name = test_class.__qualname__
        self._path = _ensure_report_dir() / f"{module_name}__{class_name}.md"
        self._entries: list[dict] = []
        self._doc = (test_class.__doc__ or "").strip()

    def add(self, method: str, status: str, explanation: str) -> None:
        """Record one test result for the report."""
        self._entries.append({
            "method": method,
            "status": status.upper(),
            "explanation": explanation,
        })

    def write(self) -> None:
        """Flush the accumulated entries to a markdown file."""
        passed = sum(1 for e in self._entries if e["status"] == "PASS")
        failed = sum(1 for e in self._entries if e["status"] == "FAIL")
        total = len(self._entries)

        lines = ["# Test Report", ""]
        if self._doc:
            lines.append(f"{self._doc}")
            lines.append("")
        lines.append(f"**Total:** {total} &nbsp;|&nbsp; **PASS:** {passed} &nbsp;|&nbsp; **FAIL:** {failed}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for i, entry in enumerate(self._entries, 1):
            badge = "✅" if entry["status"] == "PASS" else "❌"
            lines.append(f"### {i}. `{entry['method']}` {badge}")
            lines.append("")
            lines.append(f"**Status:** `{entry['status']}`")
            lines.append("")
            lines.append(f"{entry['explanation']}")
            lines.append("")
            lines.append("---")
            lines.append("")

        self._path.write_text("\n".join(lines), encoding="utf-8")
