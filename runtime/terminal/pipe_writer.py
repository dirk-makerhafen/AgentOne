#!/usr/bin/env python3
"""Append tmux ``pipe-pane`` output to a log file.

tmux/psmux pipe pane bytes to this process's stdin for the lifetime of the
pane.  Stream in chunks instead of waiting for EOF so the UI can tail the log
while a command is still running.

Usage: ``python pipe_writer.py <path>``
"""
from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: pipe_writer.py <path>", file=sys.stderr)
        return 2

    target = Path(args[0]).expanduser()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        stream = sys.stdin.buffer
        read_chunk = getattr(stream, "read1", None) or stream.read
        with target.open("ab") as handle:
            while True:
                chunk = read_chunk(65536)
                if not chunk:
                    break
                handle.write(chunk)
                handle.flush()
    except OSError as exc:
        print(f"pipe_writer: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
