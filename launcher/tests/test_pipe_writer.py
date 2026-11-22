"""``pipe-pane`` log writer used by the terminal manager."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WRITER = ROOT / "runtime" / "terminal" / "pipe_writer.py"


def test_pipe_writer_appends_streamed_bytes(tmp_path):
    log = tmp_path / "logs" / "term.log"

    result = subprocess.run(
        [sys.executable, str(WRITER), str(log)],
        input=b"first\nsecond\n",
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert log.read_bytes() == b"first\nsecond\n"

    result = subprocess.run(
        [sys.executable, str(WRITER), str(log)],
        input=b"third\n",
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert log.read_bytes() == b"first\nsecond\nthird\n"


def test_pipe_writer_requires_a_path():
    result = subprocess.run([sys.executable, str(WRITER)], capture_output=True, check=False)

    assert result.returncode == 2
    assert b"usage" in result.stderr
