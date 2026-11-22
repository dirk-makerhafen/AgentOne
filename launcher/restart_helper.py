"""Detached helper invoked by :func:`launcher.restart.request_restart`.

Kept separate from the update process so a service restart can terminate that
process without killing the restart command itself.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def _write(log_file: str, message: str):
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {message}\n"
    try:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Restart the AgentOne service after an update.")
    parser.add_argument("--delay", type=int, default=3)
    parser.add_argument("--command", required=True, help="JSON array of command arguments")
    parser.add_argument("--log-file", default="")
    args = parser.parse_args(argv)

    try:
        command = json.loads(args.command)
        if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
            raise ValueError("restart command must be a JSON array of strings")
    except (ValueError, TypeError) as exc:
        _write(args.log_file, f"invalid restart command: {exc}")
        return 2

    time.sleep(max(0, args.delay))
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        _write(args.log_file, f"restart failed to start: {exc}")
        return 1

    detail = (proc.stderr or proc.stdout).strip().replace("\n", " | ")
    status = "ok" if proc.returncode == 0 else f"failed (exit {proc.returncode})"
    _write(args.log_file, f"restart {status}: {' '.join(command)} {detail}")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
