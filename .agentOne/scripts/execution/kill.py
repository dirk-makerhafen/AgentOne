from __future__ import annotations

import signal
from typing import Optional

import psutil


def kill(
    pid: Optional[int] = None,
    name: Optional[str] = None,
    signal_name: str = "SIGTERM",
) -> tuple[bool, dict]:
    '''
    Terminate a running process by PID or name.

    Use this tool when you need to:
    - Stop a long-running process started by the shell tool
    - Kill a process that is hanging or consuming too many resources
    - Clean up background processes

    Args:
        pid: The process ID to terminate.
        name: Process name to match (kills all matching processes).
        signal_name: Signal to send. Options: "SIGTERM" (default),
            "SIGKILL", "SIGHUP", "SIGINT".

    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - killed: list of terminated PIDs
            - signal: the signal sent
        On error, result contains:
            - status: "error"
            - message: error description
    '''
    try:
        if pid is None and name is None:
            return (False, {'status': 'error', 'message': 'Either pid or name must be provided'})

        sig_map = {
            'SIGTERM': signal.SIGTERM,
            'SIGKILL': signal.SIGKILL,
            'SIGHUP': signal.SIGHUP,
            'SIGINT': signal.SIGINT,
        }
        sig = sig_map.get(signal_name, signal.SIGTERM)
        killed = []

        if pid is not None:
            try:
                proc = psutil.Process(pid)
                proc.send_signal(sig)
                killed.append(pid)
            except psutil.NoSuchProcess:
                return (False, {'status': 'error', 'message': f'Process {pid} not found'})
            except psutil.AccessDenied:
                return (False, {'status': 'error', 'message': f'Access denied to process {pid}'})

        if name is not None:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] and name.lower() in proc.info['name'].lower():
                        proc.send_signal(sig)
                        killed.append(proc.info['pid'])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        if not killed:
            return (False, {'status': 'error', 'message': f'No matching processes found for name="{name}"'})

        return (True, {
            'status': 'success',
            'killed': killed,
            'signal': signal_name,
        })

    except Exception as e:
        import traceback
        return (False, {'status': 'error', 'message': f'Error killing process: {str(e)}\n{traceback.format_exc()}'})

if __name__ == '__main__':
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Terminate a running process by PID or name.')
    parser.add_argument('--pid', type=int, help='Process ID to terminate')
    parser.add_argument('--name', type=str, help='Process name to match')
    parser.add_argument('--signal', type=str, default='SIGTERM', choices=['SIGTERM', 'SIGKILL', 'SIGHUP', 'SIGINT'], help='Signal to send')
    args = parser.parse_args()

    success, result = kill(pid=args.pid, name=args.name, signal_name=args.signal)
    print(json.dumps(result, indent=2))
    exit(0 if success else 1)
